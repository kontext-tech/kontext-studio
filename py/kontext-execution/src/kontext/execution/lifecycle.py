"""Execution lifecycle services shared across API and domain orchestrators."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID

from kontext.common.constants import ModelEnvVars
from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.data import (
    ExecutionRunContextDataService,
    JobDataService,
    JobRunDataService,
    JobRunLogDataService,
)
from kontext.schema import (
    CreateJobRequest,
    EventData,
    ExecutionRunInputRequest,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    JobRetryStrategy,
    JobRunModel,
    JobTriggerType,
    LogLevel,
    RunEvent,
    RunPausedEventData,
    SimpleRunEvent,
    TriggerActorModel,
)

from .runs import ExecutionRunService, project_execution_run
from .workflows import WorkflowOrchestrationService, upsert_workflow_metadata_json

logger = logging.getLogger(__name__)

_RUN_KIND_AGENT = ExecutionRunKind("agent")
_RUN_STATUS_WAITING_INPUT = ExecutionRunStatus("waiting_input")
# Persistence alias for interactive agent chat runs, not a registered @job:
# no worker claims this type to execute code. It exists so an agent run shares
# the job-run projection (status, events, logs) with scheduled jobs; anything
# enumerating *registered* job types must exclude it.
_AGENT_CHAT_JOB_TYPE = "python.agent.ChatSessionRun"
_AGENT_CHAT_JOB_NAME = "Agent Chat Session Run"
# Harness that runs agent chat jobs. The default is resolved from
# KONTEXT_AGENT_FRAMEWORK so the recorded engine label follows the configured
# harness rather than hardcoding a framework here.
_DEFAULT_AGENT_ENGINE_NAME = "agno"


def _resolve_agent_engine_name() -> str:
    return os.getenv(ModelEnvVars.AGENT_FRAMEWORK, _DEFAULT_AGENT_ENGINE_NAME)


@dataclass(slots=True)
class ResolvedExecutionRunInput:
    run: ExecutionRunModel
    chat_session_id: UUID
    paused_run_id: str | None


class ExecutionRunInputValidationError(Exception):
    """Raised when a run-input submission is invalid for resume."""

    def __init__(self, *, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ExecutionLifecycleService:
    """Own execution lifecycle mutations while reusing job-run persistence."""

    async def create_agent_execution_run_async(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        chat_session_id: UUID,
        triggered_by: TriggerActorModel | None,
        engine_type: str | None = None,
        parent_run_id: UUID | None = None,
        root_run_id: UUID | None = None,
        workflow_key: str | None = None,
        step_key: str | None = None,
    ) -> ExecutionRunModel:
        job_service = JobDataService(project_id)
        run_service = JobRunDataService(project_id)
        log_service = JobRunLogDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)

        job = await job_service.get_or_create_job_for_owner_async(
            job_type=_AGENT_CHAT_JOB_TYPE,
            owner_id=owner_id,
            request=CreateJobRequest(
                name=_AGENT_CHAT_JOB_NAME,
                type=_AGENT_CHAT_JOB_TYPE,
                description="Interactive agent execution attached to a chat session",
                timeout=3600,
                is_enabled=True,
                retry_strategy=JobRetryStrategy.NONE,
                retry_limit=0,
            ),
            created_by=format_trigger_actor(triggered_by),
        )

        job_run = await run_service.create_run_async(
            job_id=UUID(str(job.id)),
            parameters=json.dumps({"chatSessionId": str(chat_session_id)}),
            status="Queued",
            triggered_by=triggered_by,
            trigger_type=JobTriggerType.INTERACTIVE,
        )
        platform_run_id = UUID(str(job_run.id))
        workflow_root_run_id = root_run_id or platform_run_id
        engine_metadata_json = json.dumps({"engineType": engine_type})
        if workflow_key:
            engine_metadata_json = upsert_workflow_metadata_json(
                engine_metadata_json,
                workflow_metadata={
                    "workflow_key": workflow_key,
                    "step_key": step_key,
                    "is_workflow_root": False,
                },
            )

        await run_service.update_status_async(
            platform_run_id,
            status="Running",
            error_message="",
            result_data=json.dumps(
                {
                    "status": "running",
                    "chatSessionId": str(chat_session_id),
                    "platformRunId": str(platform_run_id),
                }
            ),
        )
        await context_service.upsert_context_async(
            run_id=platform_run_id,
            chat_session_id=chat_session_id,
            agent_session_id=str(chat_session_id),
            parent_run_id=parent_run_id,
            root_run_id=workflow_root_run_id,
            waiting_for_input=False,
            engine_name=_resolve_agent_engine_name(),
            engine_metadata_json=engine_metadata_json,
        )
        await log_service.add_log_async(
            job_run_id=platform_run_id,
            level=LogLevel.INFORMATION,
            message="Agent execution run started",
            data=json.dumps({"chatSessionId": str(chat_session_id)}),
        )

        service = ExecutionRunService()
        run = await service.get_run_async(project_id=project_id, run_id=platform_run_id)
        if not run:
            raise RuntimeError(f"Execution run {platform_run_id} was not created")
        return run

    async def mark_agent_execution_running_async(
        self,
        *,
        project_id: UUID,
        platform_run_id: UUID,
        chat_session_id: UUID,
        agent_runtime_run_id: str | None = None,
        message: str = "Agent execution running",
    ) -> None:
        run_service = JobRunDataService(project_id)
        log_service = JobRunLogDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)

        payload = {
            "status": "running",
            "chatSessionId": str(chat_session_id),
            "platformRunId": str(platform_run_id),
        }
        if agent_runtime_run_id:
            payload["runId"] = agent_runtime_run_id

        await run_service.update_status_async(
            platform_run_id,
            status="Running",
            error_message="",
            result_data=json.dumps(payload),
        )
        await context_service.upsert_context_async(
            run_id=platform_run_id,
            chat_session_id=chat_session_id,
            agent_session_id=str(chat_session_id),
            agent_runtime_run_id=agent_runtime_run_id,
            waiting_for_input=False,
        )
        await log_service.add_log_async(
            job_run_id=platform_run_id,
            level=LogLevel.INFORMATION,
            message=message,
            data=json.dumps(payload),
        )

    async def resolve_waiting_agent_execution_run_id_async(
        self,
        *,
        project_id: UUID,
        chat_session_id: UUID,
        agent_runtime_run_id: str | None = None,
    ) -> UUID | None:
        context_service = ExecutionRunContextDataService(project_id)
        context = await context_service.get_waiting_context_for_chat_session_async(
            chat_session_id=chat_session_id,
            agent_runtime_run_id=agent_runtime_run_id,
        )
        if context is None:
            return None
        return UUID(str(context.run_id))

    async def persist_agent_execution_event_async(
        self,
        *,
        project_id: UUID,
        platform_run_id: UUID,
        chat_session_id: UUID,
        event: SimpleRunEvent,
    ) -> SimpleRunEvent:
        run_service = JobRunDataService(project_id)
        log_service = JobRunLogDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)

        if event.event_type == RunEvent.RUNPAUSED:
            pause_data = _as_run_paused_event_data(event)
            payload = {
                "status": "waiting_input",
                "is_paused": True,
                "chatSessionId": str(chat_session_id),
                "platformRunId": str(platform_run_id),
            }
            if pause_data:
                payload.update(pause_data.to_dict())

            await run_service.update_status_async(
                platform_run_id,
                status="Running",
                error_message="Waiting for input",
                result_data=json.dumps(payload),
            )
            await context_service.upsert_context_async(
                run_id=platform_run_id,
                chat_session_id=chat_session_id,
                agent_session_id=str(chat_session_id),
                agent_runtime_run_id=pause_data.run_id if pause_data else None,
                waiting_for_input=True,
            )
            await log_service.add_log_async(
                job_run_id=platform_run_id,
                level=LogLevel.WARNING,
                message=event.content or "Execution run paused for external input",
                data=json.dumps(payload),
            )
            return _with_platform_run_id(event, platform_run_id)

        if event.event_type == RunEvent.RUNCOMPLETED:
            payload = {
                "status": "succeeded",
                "content": event.content,
                "chatSessionId": str(chat_session_id),
                "platformRunId": str(platform_run_id),
            }
            await run_service.update_status_async(
                platform_run_id,
                status="Succeeded",
                error_message="",
                result_data=json.dumps(payload),
            )
            await context_service.upsert_context_async(
                run_id=platform_run_id,
                waiting_for_input=False,
                agent_runtime_run_id=None,
            )
            await log_service.add_log_async(
                job_run_id=platform_run_id,
                level=LogLevel.INFORMATION,
                message="Execution run completed",
                data=json.dumps(payload),
            )
            await WorkflowOrchestrationService().handle_run_status_change_async(
                project_id=project_id,
                run_id=platform_run_id,
                queue_client=None,
            )
            return event

        if event.event_type == RunEvent.RUNERROR:
            payload = {
                "status": "failed",
                "chatSessionId": str(chat_session_id),
                "platformRunId": str(platform_run_id),
                "errorDetails": event.error_details,
            }
            await run_service.update_status_async(
                platform_run_id,
                status="Failed",
                error_message=event.error_details or event.content or "Run failed",
                result_data=json.dumps(payload),
            )
            await context_service.upsert_context_async(
                run_id=platform_run_id,
                waiting_for_input=False,
            )
            await log_service.add_log_async(
                job_run_id=platform_run_id,
                level=LogLevel.ERROR,
                message=event.error_details or event.content or "Execution run failed",
                data=json.dumps(payload),
            )
            await WorkflowOrchestrationService().handle_run_status_change_async(
                project_id=project_id,
                run_id=platform_run_id,
                queue_client=None,
            )
            return event

        if event.event_type == RunEvent.RUNCANCELLED:
            payload = {
                "status": "cancelled",
                "chatSessionId": str(chat_session_id),
                "platformRunId": str(platform_run_id),
            }
            await run_service.update_status_async(
                platform_run_id,
                status="Canceled",
                error_message=event.error_details or "Run cancelled",
                result_data=json.dumps(payload),
            )
            await context_service.upsert_context_async(
                run_id=platform_run_id,
                waiting_for_input=False,
            )
            await log_service.add_log_async(
                job_run_id=platform_run_id,
                level=LogLevel.WARNING,
                message="Execution run cancelled",
                data=json.dumps(payload),
            )
            await WorkflowOrchestrationService().handle_run_status_change_async(
                project_id=project_id,
                run_id=platform_run_id,
                queue_client=None,
            )
            return event

        return event

    async def validate_run_input_request_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        request: ExecutionRunInputRequest,
        user_id: UUID,
        get_chat_session: Callable[..., Awaitable[SimpleNamespace | object]],
    ) -> ResolvedExecutionRunInput:
        if not request.tool_outputs:
            raise ExecutionRunInputValidationError(
                status_code=400,
                detail="toolOutputs are required to resume a paused run",
            )

        service = ExecutionRunService()
        run = await service.get_run_async(project_id=project_id, run_id=run_id)
        if not run:
            raise ExecutionRunInputValidationError(
                status_code=404,
                detail=f"Run {run_id} not found",
            )

        if run.kind != _RUN_KIND_AGENT:
            raise ExecutionRunInputValidationError(
                status_code=400,
                detail=(
                    f"Run {run_id} has kind '{run.kind.value}' and does not support "
                    "platform input handling yet"
                ),
            )

        if run.status != _RUN_STATUS_WAITING_INPUT:
            raise ExecutionRunInputValidationError(
                status_code=409,
                detail=(
                    f"Run {run_id} is in status '{run.status.value}' and is not waiting for input"
                ),
            )

        context_service = ExecutionRunContextDataService(project_id)
        run_context = await context_service.get_by_run_id_async(run_id)
        resolved_chat_session_id = (
            UUID(str(request.chat_session_id))
            if request.chat_session_id
            else (
                UUID(str(run_context.chat_session_id))
                if run_context and run_context.chat_session_id
                else None
            )
        )
        if resolved_chat_session_id is None and isinstance(run.result_data, dict):
            persisted_session_id = run.result_data.get("chatSessionId")
            if persisted_session_id:
                resolved_chat_session_id = UUID(str(persisted_session_id))

        if resolved_chat_session_id is None:
            raise ExecutionRunInputValidationError(
                status_code=400,
                detail=(
                    "chatSessionId is required until the execution run has a persisted "
                    "chat-session binding"
                ),
            )

        paused_run_id = run_context.agent_runtime_run_id if run_context else None
        if paused_run_id is None and isinstance(run.result_data, dict):
            paused_run_id = run.result_data.get("runId")

        session = await get_chat_session(
            project_id=project_id,
            session_id=resolved_chat_session_id,
        )
        session_owner_id = getattr(session, "owner_id", None)
        if session_owner_id and str(session_owner_id) != str(user_id):
            raise ExecutionRunInputValidationError(
                status_code=403,
                detail="You do not own this chat session",
            )

        return ResolvedExecutionRunInput(
            run=run,
            chat_session_id=resolved_chat_session_id,
            paused_run_id=paused_run_id,
        )

    async def mark_execution_resumed_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        chat_session_id: UUID,
        paused_run_id: str | None,
    ) -> None:
        payload = {
            "status": "running",
            "chatSessionId": str(chat_session_id),
            "runId": paused_run_id,
            "platformRunId": str(run_id),
        }
        await self._update_run_status(
            project_id=project_id,
            run_id=run_id,
            status_value="Running",
            error_message="",
            result_data=payload,
        )
        await ExecutionRunContextDataService(project_id).upsert_context_async(
            run_id=run_id,
            chat_session_id=chat_session_id,
            agent_session_id=str(chat_session_id),
            agent_runtime_run_id=paused_run_id,
            waiting_for_input=False,
        )
        await self._append_run_log(
            project_id=project_id,
            run_id=run_id,
            message="Execution run resumed from external input",
            data={"chatSessionId": str(chat_session_id)},
        )

    async def apply_resumed_agent_event_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        chat_session_id: UUID,
        event: SimpleRunEvent,
    ) -> None:
        run_service = JobRunDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)

        if event.event_type == RunEvent.RUNPAUSED:
            event_data = event.event_data.root if event.event_data else None
            payload = {"status": "waiting_input", "is_paused": True}
            if event_data and hasattr(event_data, "to_dict"):
                payload.update(event_data.to_dict())
            payload["chatSessionId"] = str(chat_session_id)

            await run_service.update_status_async(
                run_id,
                status="Running",
                error_message="Waiting for input",
                result_data=json.dumps(payload, default=str),
            )
            await context_service.upsert_context_async(
                run_id=run_id,
                chat_session_id=chat_session_id,
                agent_session_id=str(chat_session_id),
                agent_runtime_run_id=(
                    event_data.run_id if isinstance(event_data, RunPausedEventData) else None
                ),
                waiting_for_input=True,
            )
            await self._append_run_log(
                project_id=project_id,
                run_id=run_id,
                message=event.content or "Execution run paused for external input",
                level=LogLevel.WARNING,
                data=payload,
            )
        elif event.event_type == RunEvent.RUNCOMPLETED:
            payload = {
                "status": "succeeded",
                "content": event.content,
                "chatSessionId": str(chat_session_id),
            }
            await run_service.update_status_async(
                run_id,
                status="Succeeded",
                error_message="",
                result_data=json.dumps(payload, default=str),
            )
            await context_service.upsert_context_async(
                run_id=run_id,
                waiting_for_input=False,
                agent_runtime_run_id=None,
            )
            await self._append_run_log(
                project_id=project_id,
                run_id=run_id,
                message="Execution run completed after external input",
                data=payload,
            )
            await WorkflowOrchestrationService().handle_run_status_change_async(
                project_id=project_id,
                run_id=run_id,
                queue_client=None,
            )
        elif event.event_type == RunEvent.RUNERROR:
            payload = {
                "status": "failed",
                "chatSessionId": str(chat_session_id),
                "errorDetails": event.error_details,
            }
            await run_service.update_status_async(
                run_id,
                status="Failed",
                error_message=event.error_details or event.content or "Run failed",
                result_data=json.dumps(payload, default=str),
            )
            await context_service.upsert_context_async(
                run_id=run_id,
                waiting_for_input=False,
            )
            await self._append_run_log(
                project_id=project_id,
                run_id=run_id,
                message=event.error_details or event.content or "Execution run failed",
                level=LogLevel.ERROR,
                data=payload,
            )
            await WorkflowOrchestrationService().handle_run_status_change_async(
                project_id=project_id,
                run_id=run_id,
                queue_client=None,
            )
        elif event.event_type == RunEvent.RUNCANCELLED:
            payload = {
                "status": "cancelled",
                "chatSessionId": str(chat_session_id),
            }
            await run_service.update_status_async(
                run_id,
                status="Canceled",
                error_message=event.error_details or "Run cancelled",
                result_data=json.dumps(payload, default=str),
            )
            await context_service.upsert_context_async(
                run_id=run_id,
                waiting_for_input=False,
            )
            await self._append_run_log(
                project_id=project_id,
                run_id=run_id,
                message="Execution run cancelled after external input",
                level=LogLevel.WARNING,
                data=payload,
            )
            await WorkflowOrchestrationService().handle_run_status_change_async(
                project_id=project_id,
                run_id=run_id,
                queue_client=None,
            )

    async def mark_resume_failed_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        chat_session_id: UUID,
        paused_run_id: str | None,
        error: Exception,
    ) -> None:
        payload = {
            "status": "failed",
            "chatSessionId": str(chat_session_id),
            "runId": paused_run_id,
            "platformRunId": str(run_id),
        }
        await self._update_run_status(
            project_id=project_id,
            run_id=run_id,
            status_value="Failed",
            error_message=str(error),
            result_data=payload,
        )
        await ExecutionRunContextDataService(project_id).upsert_context_async(
            run_id=run_id,
            waiting_for_input=False,
        )
        await self._append_run_log(
            project_id=project_id,
            run_id=run_id,
            message=f"Failed to resume execution run from input: {error}",
            level=LogLevel.ERROR,
            data={"chatSessionId": str(chat_session_id)},
        )
        await WorkflowOrchestrationService().handle_run_status_change_async(
            project_id=project_id,
            run_id=run_id,
            queue_client=None,
        )

    async def process_resumed_agent_stream_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        chat_session_id: UUID,
        raw_events: AsyncIterable[str],
        parse_event: Callable[[str], SimpleRunEvent | None],
    ) -> None:
        async for event_json in raw_events:
            event = parse_event(event_json)
            if event is None:
                logger.warning("Skipping empty agent event while resuming execution run")
                continue

            await self.apply_resumed_agent_event_async(
                project_id=project_id,
                run_id=run_id,
                chat_session_id=chat_session_id,
                event=event,
            )

    def project_job_run(self, job_run: JobRunModel) -> ExecutionRunModel:
        return project_execution_run(job_run)

    async def _append_run_log(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        message: str,
        level: LogLevel = LogLevel.INFORMATION,
        data: dict | None = None,
    ) -> None:
        try:
            await JobRunLogDataService(project_id).add_log_async(
                job_run_id=run_id,
                level=level,
                message=message,
                data=json.dumps(data) if data is not None else None,
            )
        except Exception:
            logger.exception("Failed to append run log for %s", run_id)

    async def _update_run_status(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        status_value: str,
        error_message: str | None = None,
        result_data: dict | None = None,
    ) -> None:
        try:
            await JobRunDataService(project_id).update_status_async(
                run_id,
                status=status_value,
                error_message=error_message,
                result_data=(
                    json.dumps(result_data, default=str) if result_data is not None else None
                ),
            )
        except Exception:
            logger.exception("Failed to update run status for %s", run_id)


def _as_run_paused_event_data(event: SimpleRunEvent) -> RunPausedEventData | None:
    if not event.event_data:
        return None

    event_data = event.event_data.root
    if isinstance(event_data, RunPausedEventData):
        return event_data
    return None


def _with_platform_run_id(event: SimpleRunEvent, platform_run_id: UUID) -> SimpleRunEvent:
    pause_data = _as_run_paused_event_data(event)
    if pause_data is None:
        return event

    return SimpleRunEvent(
        event_type=event.event_type,
        content=event.content,
        event_id=event.event_id,
        event_data=EventData(
            RunPausedEventData(
                model=pause_data.model,
                run_id=pause_data.run_id,
                platform_run_id=str(platform_run_id),
                active_requirements=pause_data.active_requirements,
                tool_calls=pause_data.tool_calls,
            )
        ),
        done=event.done,
        error_details=event.error_details,
        reasoning=event.reasoning,
    )
