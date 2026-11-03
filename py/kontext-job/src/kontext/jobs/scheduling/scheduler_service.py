"""Job scheduler service for evaluating CRON triggers and creating job runs.

This is a pure business logic module - hosting is handled externally.

Architecture:
This service uses sync SQLAlchemy sessions internally but provides an async
interface for FastAPI compatibility. The underlying data services execute
database operations via asyncio.to_thread() to avoid blocking the event loop.
"""

import json
import logging
from datetime import datetime
from uuid import UUID

from kontext.common.jobs.scheduling import CronParser
from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.common.messaging import IQueueClient
from kontext.common.utils.datetime_utils import utc_now
from kontext.data import (
    Job,
    JobDataService,
    JobRun,
    JobRunDataService,
    JobTrigger,
    JobTriggerDataService,
)
from kontext.schema import JobTriggerType, TriggerActorModel

from ..dispatch import build_job_execution_message

logger = logging.getLogger(__name__)


class JobSchedulerService:
    """Service for scheduling jobs based on CRON triggers.

    This service contains all business logic for:
    - Evaluating which triggers are due
    - Creating job runs for due triggers
    - Queuing job execution messages
    - Updating trigger last run times
    """

    def __init__(self, queue_client: IQueueClient | None = None) -> None:
        """Initialize the scheduler service.

        Args:
            queue_client: Optional queue client for sending job execution messages.
        """
        self._queue_client = queue_client

    async def evaluate_triggers_for_project_async(self, project_id: UUID) -> list[UUID]:
        """Evaluate all CRON triggers for a project and schedule due jobs.

        Args:
            project_id: Project ID for queue message routing.

        Returns:
            List of created job run IDs.
        """
        trigger_service = JobTriggerDataService(project_id=project_id)
        run_service = JobRunDataService(project_id=project_id)

        created_run_ids: list[UUID] = []
        now = utc_now()

        # Get all active scheduled triggers (entities for relationship access)
        triggers = await trigger_service._get_scheduled_trigger_entities_async()

        for trigger in triggers:
            if not self._is_trigger_due(trigger, now):
                continue

            job = trigger.job
            if not job or not job.is_enabled or job.is_deleted:
                continue

            try:
                # Create job run (using entity method for scheduler internals)
                job_run = await run_service._create_run_entity_async(
                    job_id=job.id, parameters=job.parameters, trigger_id=trigger.id
                )
                created_run_ids.append(job_run.id)

                # Queue for execution
                if self._queue_client:
                    await self._queue_job_execution_async(
                        job_run=job_run,
                        job=job,
                        project_id=project_id,
                    )

                # Update last scheduled run time
                await trigger_service.update_last_scheduled_run_async(trigger.id, now)

                logger.info(
                    "Scheduled job %s (run %s) from trigger %s",
                    job.name,
                    job_run.id,
                    trigger.id,
                )

            except Exception:
                logger.exception("Failed to schedule job for trigger %s", trigger.id)

        return created_run_ids

    async def schedule_job_manually_async(
        self,
        job_id: UUID,
        project_id: UUID,
        parameters: str | None = None,
        triggered_by: TriggerActorModel | None = None,
        execution_id: str | None = None,
    ) -> JobRun:
        """Manually schedule a job for execution.

        Args:
            job_id: The job to schedule.
            project_id: Project ID for queue message routing.
            parameters: Optional JSON parameters to override defaults.
            triggered_by: Structured actor/artifact that triggered the job.
            execution_id: Optional queue message/execution ID.

        Returns:
            The created JobRun entity.

        Raises:
            ValueError: If the job is not found or not enabled.
        """
        job_service = JobDataService(project_id=project_id)
        run_service = JobRunDataService(project_id=project_id)
        trigger_service = JobTriggerDataService(project_id=project_id)

        # Get job view model for validation
        job_vm = await job_service.get_job_by_id_async(job_id)
        if job_vm is None:
            raise ValueError(f"Job {job_id} not found")
        if not job_vm.is_enabled:
            raise ValueError(f"Job {job_id} is disabled")

        # Use provided parameters or fall back to job defaults
        run_parameters = parameters or job_vm.parameters

        # Get or create a manual trigger record (using entity method)
        trigger = await trigger_service._get_or_create_trigger_entity_async(
            job_id=job_id,
            trigger_type=JobTriggerType.MANUAL,
            configuration=json.dumps({"triggered_by": format_trigger_actor(triggered_by)}),
            triggered_by=triggered_by,
        )

        # Create job run (using entity method)
        job_run = await run_service._create_run_entity_async(
            job_id=job_id,
            parameters=run_parameters,
            trigger_id=trigger.id,
            execution_id=execution_id,
        )

        # Queue for execution - need Job entity for queue message
        if self._queue_client:
            # Get job entity for queue message details
            job_entity = await job_service._get_job_entity_async(job_id)
            if job_entity:
                await self._queue_job_execution_async(
                    job_run=job_run,
                    job=job_entity,
                    project_id=project_id,
                )

        logger.info(
            "Manually scheduled job %s (run %s) by %s",
            job_vm.name,
            job_run.id,
            format_trigger_actor(triggered_by) or "unknown",
        )

        return job_run

    def _is_trigger_due(self, trigger: JobTrigger, now: datetime) -> bool:
        """Check if a trigger is due for execution.

        Args:
            trigger: The trigger to check.
            now: Current time for comparison.

        Returns:
            True if the trigger is due, False otherwise.
        """
        if trigger.is_paused or trigger.is_deleted:
            return False

        # Get CRON expression from trigger configuration
        config = self._parse_trigger_config(trigger.configuration)
        cron_expression = config.get("schedule")

        if not cron_expression:
            return False

        return CronParser.is_due(cron_expression, trigger.last_scheduled_run_at, now)

    def _parse_trigger_config(self, config_json: str) -> dict:
        """Parse trigger configuration JSON.

        Args:
            config_json: JSON configuration string.

        Returns:
            Parsed configuration dictionary.
        """
        try:
            return json.loads(config_json) if config_json else {}
        except json.JSONDecodeError:
            return {}

    async def _queue_job_execution_async(
        self,
        job_run: JobRun,
        job: Job,
        project_id: UUID,
    ) -> None:
        """Queue a self-contained job execution message.

        Sends a JobExecutionMessage to the queue with all information needed
        for the worker to execute the job without requiring database lookups.

        Args:
            job_run: The job run to execute.
            job: The parent job definition.
            project_id: Project ID for routing to local SQLite database.
        """
        if self._queue_client is None:
            return

        # Parse parameters from job run if present
        parameters: dict = {}
        if job_run.parameters:
            try:
                parameters = json.loads(job_run.parameters)
            except json.JSONDecodeError:
                logger.warning("Failed to parse job run parameters for %s", job_run.id)

        # Build self-contained message with all job execution context
        # Convert timeout from seconds to minutes (min 1 minute, default 5 min)
        timeout_minutes = max(1, (job.timeout or 300) // 60)
        message = build_job_execution_message(
            job_run_id=job_run.id,
            execution_id=job_run.execution_id,
            project_id=project_id,
            job_type=job.type,
            job_name=job.name,
            timeout_minutes=timeout_minutes,
            parameters=parameters,
            priority=5,
        )

        logger.debug(
            "Queueing job execution: JobRunId=%s, JobType=%s, TimeoutMinutes=%d, ProjectId=%s",
            job_run.id,
            job.type,
            message.timeout_minutes,
            project_id,
        )

        # Serialize with camelCase aliases and send to queue
        await self._queue_client.send_message(message.to_json())

    def calculate_next_run(self, trigger: JobTrigger) -> datetime | None:
        """Calculate the next run time for a trigger.

        Args:
            trigger: The trigger to calculate for.

        Returns:
            Next scheduled run time or None if not calculable.
        """
        config = self._parse_trigger_config(trigger.configuration)
        cron_expression = config.get("schedule")

        if not cron_expression or not CronParser.is_valid(cron_expression):
            return None

        base_time = trigger.last_scheduled_run_at or utc_now()
        return CronParser.get_next_run(cron_expression, base_time)
