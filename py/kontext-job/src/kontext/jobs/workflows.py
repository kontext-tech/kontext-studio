"""Lightweight workflow orchestration built on durable execution run contexts."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.common.messaging import IQueueClient
from kontext.data import (
    ExecutionRunContextDataService,
    JobRunDataService,
    JobRunLogDataService,
)
from kontext.jobs.service import JobService
from kontext.schema import (
    JobRunStatus,
    JobTriggerType,
    LogLevel,
    TriggerActorModel,
)

from .job_run_dispatch import (
    create_queued_job_run_and_maybe_dispatch,
    dispatch_job_run_if_configured,
)
from .workflow_models import (
    _CANCELLABLE_JOB_STATUSES,
    _RUN_STATUS_CANCELLED,
    _RUN_STATUS_FAILED,
    _RUN_STATUS_QUEUED,
    _RUN_STATUS_RUNNING,
    _RUN_STATUS_SUCCEEDED,
    _STEP_STATUS_PENDING,
    _STEP_STATUS_SKIPPED,
    _TERMINAL_JOB_STATUSES,
    _TERMINAL_STEP_STATUSES,
    WORKFLOW_ENGINE_NAME,
    WorkflowDependencyTriggerConfiguration,
    WorkflowJobStepDefinition,
    WorkflowLogData,
    WorkflowProjectionMetadata,
    WorkflowRootState,
    WorkflowStartRequest,
    WorkflowStepState,
    _build_root_job_type,
    _build_root_workflow_metadata,
    _build_step_workflow_metadata,
    _build_terminal_error_message,
    _build_workflow_result_data,
    _calculate_progress,
    _coerce_optional_str,
    _determine_terminal_status,
    _find_step,
    _has_active_steps,
    _is_step_ready_to_dispatch,
    _job_run_to_step_status,
    _load_root_workflow_state,
    _mark_blocked_steps_as_skipped,
    _reset_skipped_descendants,
    _root_job_status_from_run_status,
    _status_to_log_level,
    extract_workflow_projection_metadata,
    get_workflow_metadata,
    parse_engine_metadata_json,
    upsert_workflow_metadata_json,
)

logger = logging.getLogger(__name__)

__all__ = [
    "WORKFLOW_ENGINE_NAME",
    "_CANCELLABLE_JOB_STATUSES",
    "_RUN_STATUS_CANCELLED",
    "_RUN_STATUS_FAILED",
    "_RUN_STATUS_QUEUED",
    "_RUN_STATUS_RUNNING",
    "_RUN_STATUS_SUCCEEDED",
    "_STEP_STATUS_PENDING",
    "_STEP_STATUS_SKIPPED",
    "_TERMINAL_JOB_STATUSES",
    "_TERMINAL_STEP_STATUSES",
    "WorkflowDependencyTriggerConfiguration",
    "WorkflowJobStepDefinition",
    "WorkflowLogData",
    "WorkflowOrchestrationService",
    "WorkflowProjectionMetadata",
    "WorkflowRootState",
    "WorkflowStartRequest",
    "WorkflowStepState",
    "_build_root_job_type",
    "_build_root_workflow_metadata",
    "_build_step_workflow_metadata",
    "_build_terminal_error_message",
    "_build_workflow_result_data",
    "_calculate_progress",
    "_coerce_optional_str",
    "_determine_terminal_status",
    "_find_step",
    "_has_active_steps",
    "_is_step_ready_to_dispatch",
    "_job_run_to_step_status",
    "_load_root_workflow_state",
    "_mark_blocked_steps_as_skipped",
    "_reset_skipped_descendants",
    "_root_job_status_from_run_status",
    "_status_to_log_level",
    "extract_workflow_projection_metadata",
    "get_workflow_metadata",
    "parse_engine_metadata_json",
    "upsert_workflow_metadata_json",
]


class WorkflowOrchestrationService:
    """Minimal DAG orchestration over existing job-run persistence."""

    async def start_workflow_async(
        self,
        *,
        project_id: UUID,
        workflow: WorkflowStartRequest,
        queue_client: IQueueClient | None,
    ) -> UUID:
        self._validate_definition(workflow)

        job_service = JobService(project_id=project_id)
        run_service = JobRunDataService(project_id)
        root_job = await job_service.ensure_job_exists_async(
            job_type=_build_root_job_type(workflow.workflow_key),
            name=workflow.workflow_name,
            description=workflow.description or f"Workflow root for {workflow.workflow_name}",
            timeout=3600,
            created_by=format_trigger_actor(workflow.triggered_by),
        )
        if root_job is None or root_job.id is None:
            raise ValueError(f"Unable to create workflow root job for {workflow.workflow_key}")

        root_parameters = dict(workflow.parameters)
        root_parameters.setdefault("workflowKey", workflow.workflow_key)
        root_parameters.setdefault("stepCount", len(workflow.steps))
        root_run = await run_service.create_run_async(
            job_id=root_job.id,
            parameters=json.dumps(root_parameters, default=str),
            status=JobRunStatus.QUEUED.value,
            triggered_by=workflow.triggered_by,
            trigger_type=workflow.trigger_type,
            trigger_configuration=(
                json.dumps(workflow.trigger_configuration, default=str)
                if workflow.trigger_configuration
                else None
            ),
        )
        if root_run.id is None:
            raise ValueError(
                f"Workflow root run for {workflow.workflow_key} was created without an ID"
            )

        root_run_id = UUID(str(root_run.id))
        workflow_state = _build_root_workflow_metadata(workflow)
        await self._save_root_workflow_state_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
        )
        await self._set_root_running_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
        )
        await self._append_log_async(
            project_id=project_id,
            run_id=root_run_id,
            message=f"Workflow '{workflow.workflow_name}' started",
            data=WorkflowLogData(
                workflow_key=workflow.workflow_key,
                step_count=len(workflow.steps),
            ),
        )
        await self._drive_workflow_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
            queue_client=queue_client,
        )
        return root_run_id

    async def handle_run_status_change_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        queue_client: IQueueClient | None,
    ) -> None:
        context_service = ExecutionRunContextDataService(project_id)
        run_context = await context_service.get_by_run_id_async(run_id)
        if run_context is None or run_context.root_run_id is None:
            return

        root_run_id = UUID(str(run_context.root_run_id))
        if root_run_id == run_id:
            return

        projection = extract_workflow_projection_metadata(run_context)
        if not projection.workflow_key or not projection.step_key:
            return

        root_context = await context_service.get_by_run_id_async(root_run_id)
        workflow_state = _load_root_workflow_state(root_context)
        if workflow_state is None:
            return

        step = _find_step(workflow_state, projection.step_key)
        if step is None:
            return

        current_run_id = _coerce_optional_str(step.run_id)
        if current_run_id and current_run_id != str(run_id):
            return

        run_service = JobRunDataService(project_id)
        job_run = await run_service.get_run_by_id_async(
            run_id, include_job=False, include_trigger=False
        )
        if job_run is None or job_run.status not in _TERMINAL_JOB_STATUSES:
            return

        next_status = _job_run_to_step_status(job_run)
        if next_status not in _TERMINAL_STEP_STATUSES:
            return

        if (
            step.status == next_status
            and _coerce_optional_str(step.completed_at)
            and current_run_id == str(run_id)
        ):
            return

        step.status = next_status
        step.run_id = str(run_id)
        step.completed_at = job_run.completed_at.isoformat() if job_run.completed_at else None
        step.error_message = job_run.error_message

        await self._append_log_async(
            project_id=project_id,
            run_id=root_run_id,
            message=f"Workflow step '{step.name}' {next_status}",
            level=_status_to_log_level(next_status),
            data=WorkflowLogData(
                workflow_key=workflow_state.workflow_key,
                step_key=step.key,
                step_run_id=str(run_id),
                status=next_status,
                error_message=job_run.error_message,
            ),
        )
        await self._drive_workflow_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
            queue_client=queue_client,
        )

    async def cancel_workflow_async(
        self,
        *,
        project_id: UUID,
        root_run_id: UUID,
        requested_by: TriggerActorModel,
        reason: str | None = None,
    ) -> None:
        requested_by_label = format_trigger_actor(requested_by) or "System"
        context_service = ExecutionRunContextDataService(project_id)
        root_context = await context_service.get_by_run_id_async(root_run_id)
        workflow_state = _load_root_workflow_state(root_context)
        if workflow_state is None:
            return

        run_service = JobRunDataService(project_id)
        child_contexts = await context_service.list_by_root_run_id_async(root_run_id)
        child_run_ids = [
            UUID(str(context.run_id))
            for context in child_contexts
            if context.run_id and UUID(str(context.run_id)) != root_run_id
        ]
        child_runs = await run_service.get_runs_by_ids_async(
            child_run_ids, include_job=False, include_trigger=False
        )
        child_runs_by_id = {
            str(child_run.id): child_run for child_run in child_runs if child_run.id
        }

        for step in workflow_state.steps:
            run_id = _coerce_optional_str(step.run_id)
            if run_id and run_id in child_runs_by_id:
                child_run = child_runs_by_id[run_id]
                if child_run.status in _CANCELLABLE_JOB_STATUSES:
                    await run_service.update_status_async(
                        UUID(run_id),
                        status=JobRunStatus.CANCELED.value,
                        error_message=reason or f"Cancelled by {requested_by_label}",
                    )
                    await self._append_log_async(
                        project_id=project_id,
                        run_id=UUID(run_id),
                        message="Workflow step cancelled",
                        level=LogLevel.WARNING,
                        data=WorkflowLogData(
                            workflow_key=workflow_state.workflow_key,
                            step_key=step.key,
                            reason=reason,
                        ),
                    )

            if step.status not in _TERMINAL_STEP_STATUSES:
                step.status = _RUN_STATUS_CANCELLED
                step.error_message = reason or f"Cancelled by {requested_by_label}"

        await self._save_root_workflow_state_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
        )
        await self._finalize_root_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
            terminal_status=_RUN_STATUS_CANCELLED,
            error_message=reason or f"Cancelled by {requested_by_label}",
            completion_message=(f"Workflow '{workflow_state.workflow_name}' cancelled"),
        )

    async def retry_workflow_async(
        self,
        *,
        project_id: UUID,
        root_run_id: UUID,
        requested_by: TriggerActorModel,
        reason: str,
        queue_client: IQueueClient | None,
    ) -> UUID | None:
        context_service = ExecutionRunContextDataService(project_id)
        root_context = await context_service.get_by_run_id_async(root_run_id)
        workflow_state = _load_root_workflow_state(root_context)
        if workflow_state is None:
            return None

        retry_request = WorkflowStartRequest(
            workflow_key=workflow_state.workflow_key,
            workflow_name=workflow_state.workflow_name,
            description=workflow_state.workflow_description,
            triggered_by=requested_by,
            trigger_type=JobTriggerType.RETRY,
            trigger_configuration={
                "originalWorkflowRunId": str(root_run_id),
                "reason": reason,
            },
            parameters={
                "workflowKey": workflow_state.workflow_key,
                "retryOfRunId": str(root_run_id),
            },
            steps=[
                WorkflowJobStepDefinition(
                    key=step.key,
                    name=step.name,
                    job_type=step.dispatch.job_type,
                    job_name=step.dispatch.job_name,
                    parameters=dict(step.dispatch.parameters),
                    depends_on=list(step.depends_on),
                    job_id=_coerce_optional_str(step.dispatch.job_id),
                    job_description=_coerce_optional_str(step.dispatch.job_description),
                    timeout_seconds=step.dispatch.timeout_seconds,
                    priority=int(step.dispatch.priority or 5),
                )
                for step in workflow_state.steps
            ],
        )
        new_root_run_id = await self.start_workflow_async(
            project_id=project_id,
            workflow=retry_request,
            queue_client=queue_client,
        )
        await self._append_log_async(
            project_id=project_id,
            run_id=root_run_id,
            message=(f"Workflow manually retried. New retry attempt created: {new_root_run_id}"),
            data={"reason": reason},
        )
        return new_root_run_id

    async def rebind_step_retry_async(
        self,
        *,
        project_id: UUID,
        previous_run_id: UUID,
        new_run_id: UUID,
        requested_by: TriggerActorModel,
        reason: str,
    ) -> bool:
        context_service = ExecutionRunContextDataService(project_id)
        previous_context = await context_service.get_by_run_id_async(previous_run_id)
        if previous_context is None or previous_context.root_run_id is None:
            return False

        root_run_id = UUID(str(previous_context.root_run_id))
        if root_run_id == previous_run_id:
            return False

        projection = extract_workflow_projection_metadata(previous_context)
        if not projection.workflow_key or not projection.step_key:
            return False

        root_context = await context_service.get_by_run_id_async(root_run_id)
        workflow_state = _load_root_workflow_state(root_context)
        if workflow_state is None:
            return False

        step = _find_step(workflow_state, projection.step_key)
        if step is None:
            return False

        step.run_id = str(new_run_id)
        step.status = _RUN_STATUS_QUEUED
        step.completed_at = None
        step.error_message = None
        step.attempt_count = int(step.attempt_count or 0) + 1
        _reset_skipped_descendants(workflow_state, projection.step_key)

        await context_service.upsert_context_async(
            run_id=new_run_id,
            parent_run_id=previous_context.parent_run_id or root_run_id,
            root_run_id=root_run_id,
            waiting_for_input=False,
            engine_metadata_json=upsert_workflow_metadata_json(
                None,
                workflow_metadata=_build_step_workflow_metadata(
                    workflow_key=projection.workflow_key,
                    step_key=projection.step_key,
                ),
            ),
        )
        await self._save_root_workflow_state_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
        )
        await self._set_root_running_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
        )
        await self._append_log_async(
            project_id=project_id,
            run_id=root_run_id,
            message=f"Workflow step '{step.name}' queued for retry",
            data=WorkflowLogData(
                workflow_key=projection.workflow_key,
                step_key=projection.step_key,
                previous_run_id=str(previous_run_id),
                new_run_id=str(new_run_id),
                requested_by=format_trigger_actor(requested_by),
                reason=reason,
            ),
        )
        return True

    def _validate_definition(self, workflow: WorkflowStartRequest) -> None:
        if not workflow.workflow_key.strip():
            raise ValueError("Workflow key cannot be empty")
        if not workflow.workflow_name.strip():
            raise ValueError("Workflow name cannot be empty")

        seen_keys: set[str] = set()
        for step in workflow.steps:
            if not step.key.strip():
                raise ValueError("Workflow step key cannot be empty")
            if step.key in seen_keys:
                raise ValueError(f"Workflow step key '{step.key}' is duplicated")
            seen_keys.add(step.key)

        for step in workflow.steps:
            missing_dependencies = [
                dependency for dependency in step.depends_on if dependency not in seen_keys
            ]
            if missing_dependencies:
                raise ValueError(
                    f"Workflow step '{step.key}' references unknown dependencies: "
                    f"{', '.join(missing_dependencies)}"
                )

    async def _drive_workflow_async(
        self,
        *,
        project_id: UUID,
        root_run_id: UUID,
        workflow_state: WorkflowRootState,
        queue_client: IQueueClient | None,
    ) -> None:
        await self._dispatch_ready_steps_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
            queue_client=queue_client,
        )
        if _has_active_steps(workflow_state):
            await self._save_root_workflow_state_async(
                project_id=project_id,
                root_run_id=root_run_id,
                workflow_state=workflow_state,
            )
            await self._set_root_running_async(
                project_id=project_id,
                root_run_id=root_run_id,
                workflow_state=workflow_state,
            )
            return

        skipped_steps = _mark_blocked_steps_as_skipped(workflow_state)
        for step in skipped_steps:
            await self._append_log_async(
                project_id=project_id,
                run_id=root_run_id,
                message=f"Workflow step '{step.name}' skipped",
                level=LogLevel.WARNING,
                data=WorkflowLogData(
                    workflow_key=workflow_state.workflow_key,
                    step_key=step.key,
                    reason=step.error_message,
                ),
            )

        pending_steps = [
            step for step in workflow_state.steps if step.status == _STEP_STATUS_PENDING
        ]
        if pending_steps:
            for step in pending_steps:
                step.status = _STEP_STATUS_SKIPPED
                step.error_message = "Workflow could not make further progress"
            await self._save_root_workflow_state_async(
                project_id=project_id,
                root_run_id=root_run_id,
                workflow_state=workflow_state,
            )
            await self._finalize_root_async(
                project_id=project_id,
                root_run_id=root_run_id,
                workflow_state=workflow_state,
                terminal_status=_RUN_STATUS_FAILED,
                error_message="Workflow could not make further progress",
                completion_message=(f"Workflow '{workflow_state.workflow_name}' failed"),
            )
            return

        terminal_status = _determine_terminal_status(workflow_state)
        await self._save_root_workflow_state_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
        )
        if terminal_status == _RUN_STATUS_SUCCEEDED:
            await self._finalize_root_async(
                project_id=project_id,
                root_run_id=root_run_id,
                workflow_state=workflow_state,
                terminal_status=terminal_status,
                error_message=None,
                completion_message=(f"Workflow '{workflow_state.workflow_name}' completed"),
            )
            return

        await self._finalize_root_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
            terminal_status=terminal_status,
            error_message=_build_terminal_error_message(workflow_state),
            completion_message=f"Workflow '{workflow_state.workflow_name}' failed",
        )

    async def _dispatch_ready_steps_async(
        self,
        *,
        project_id: UUID,
        root_run_id: UUID,
        workflow_state: WorkflowRootState,
        queue_client: IQueueClient | None,
    ) -> None:
        for step in workflow_state.steps:
            if not _is_step_ready_to_dispatch(workflow_state, step):
                continue

            try:
                await self._dispatch_step_async(
                    project_id=project_id,
                    root_run_id=root_run_id,
                    workflow_state=workflow_state,
                    step=step,
                    queue_client=queue_client,
                )
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.exception(
                    "Failed to dispatch workflow step %s for workflow %s",
                    step.key,
                    workflow_state.workflow_key,
                )
                step.status = _RUN_STATUS_FAILED
                step.error_message = str(exc)
                await self._append_log_async(
                    project_id=project_id,
                    run_id=root_run_id,
                    message=f"Failed to queue workflow step '{step.name}'",
                    level=LogLevel.ERROR,
                    data=WorkflowLogData(
                        workflow_key=workflow_state.workflow_key,
                        step_key=step.key,
                        error_message=str(exc),
                    ),
                )

    async def _dispatch_step_async(
        self,
        *,
        project_id: UUID,
        root_run_id: UUID,
        workflow_state: WorkflowRootState,
        step: WorkflowStepState,
        queue_client: IQueueClient | None,
    ) -> None:
        dispatch = step.dispatch
        job_id = _coerce_optional_str(dispatch.job_id)
        if job_id is None:
            job_service = JobService(project_id=project_id)
            job_entity = await job_service.ensure_job_exists_async(
                job_type=dispatch.job_type,
                name=dispatch.job_name,
                description=_coerce_optional_str(dispatch.job_description),
                timeout=int(dispatch.timeout_seconds or 300),
                created_by=workflow_state.requested_by,
            )
            if job_entity is None or job_entity.id is None:
                raise ValueError(f"Unable to resolve job for workflow step '{step.key}'")
            job_id = str(job_entity.id)
            dispatch.job_id = job_id

        job_run, _ = await create_queued_job_run_and_maybe_dispatch(
            project_id=project_id,
            queue_client=None,
            job_id=job_id,
            parameters=dict(dispatch.parameters),
            job_type=dispatch.job_type,
            job_name=dispatch.job_name,
            timeout_seconds=dispatch.timeout_seconds,
            triggered_by=workflow_state.trigger_actor,
            trigger_type=JobTriggerType.DEPENDENCY,
            trigger_configuration=json.dumps(
                WorkflowDependencyTriggerConfiguration(
                    workflow_key=workflow_state.workflow_key,
                    root_run_id=str(root_run_id),
                    step_key=step.key,
                ).model_dump(by_alias=True),
                default=str,
            ),
            attempt_count=int(step.attempt_count or 0),
            priority=int(dispatch.priority or 5),
        )
        if job_run.id is None:
            raise ValueError(f"Workflow step '{step.key}' was created without a run ID")

        step_run_id = UUID(str(job_run.id))
        step.run_id = str(step_run_id)
        step.status = _RUN_STATUS_QUEUED
        step.error_message = None
        step.completed_at = None
        step.attempt_count = int(step.attempt_count or 0) + 1

        await ExecutionRunContextDataService(project_id).upsert_context_async(
            run_id=step_run_id,
            parent_run_id=root_run_id,
            root_run_id=root_run_id,
            waiting_for_input=False,
            engine_metadata_json=upsert_workflow_metadata_json(
                None,
                workflow_metadata=_build_step_workflow_metadata(
                    workflow_key=workflow_state.workflow_key,
                    step_key=step.key,
                ),
            ),
        )
        await self._save_root_workflow_state_async(
            project_id=project_id,
            root_run_id=root_run_id,
            workflow_state=workflow_state,
        )
        await dispatch_job_run_if_configured(
            queue_client=queue_client,
            project_id=project_id,
            job_run_id=step_run_id,
            job_type=dispatch.job_type,
            job_name=dispatch.job_name,
            timeout_seconds=dispatch.timeout_seconds,
            parameters=dict(dispatch.parameters),
            priority=int(dispatch.priority or 5),
        )
        await self._append_log_async(
            project_id=project_id,
            run_id=root_run_id,
            message=f"Queued workflow step '{step.name}'",
            data=WorkflowLogData(
                workflow_key=workflow_state.workflow_key,
                step_key=step.key,
                step_run_id=str(step_run_id),
                job_type=dispatch.job_type,
            ),
        )
        await self._append_log_async(
            project_id=project_id,
            run_id=step_run_id,
            message="Workflow step queued",
            data=WorkflowLogData(
                workflow_key=workflow_state.workflow_key,
                root_run_id=str(root_run_id),
                step_key=step.key,
            ),
        )

    async def _save_root_workflow_state_async(
        self,
        *,
        project_id: UUID,
        root_run_id: UUID,
        workflow_state: WorkflowRootState,
    ) -> None:
        context_service = ExecutionRunContextDataService(project_id)
        existing_context = await context_service.get_by_run_id_async(root_run_id)
        await context_service.upsert_context_async(
            run_id=root_run_id,
            root_run_id=root_run_id,
            waiting_for_input=False,
            engine_name=WORKFLOW_ENGINE_NAME,
            engine_metadata_json=upsert_workflow_metadata_json(
                existing_context.engine_metadata_json if existing_context else None,
                workflow_metadata=workflow_state,
            ),
        )

    async def _set_root_running_async(
        self,
        *,
        project_id: UUID,
        root_run_id: UUID,
        workflow_state: WorkflowRootState,
    ) -> None:
        run_service = JobRunDataService(project_id)
        await run_service.update_progress_async(
            root_run_id, progress=_calculate_progress(workflow_state)
        )
        await run_service.update_status_async(
            root_run_id,
            status=JobRunStatus.RUNNING.value,
            error_message="",
            result_data=json.dumps(
                _build_workflow_result_data(
                    workflow_state,
                    status=_RUN_STATUS_RUNNING,
                ).model_dump(by_alias=True),
                default=str,
            ),
        )

    async def _finalize_root_async(
        self,
        *,
        project_id: UUID,
        root_run_id: UUID,
        workflow_state: WorkflowRootState,
        terminal_status: str,
        error_message: str | None,
        completion_message: str,
    ) -> None:
        run_service = JobRunDataService(project_id)
        await run_service.update_progress_async(root_run_id, progress=100)
        await run_service.update_status_async(
            root_run_id,
            status=_root_job_status_from_run_status(terminal_status),
            error_message=error_message,
            result_data=json.dumps(
                _build_workflow_result_data(
                    workflow_state,
                    status=terminal_status,
                ).model_dump(by_alias=True),
                default=str,
            ),
        )
        await self._append_log_async(
            project_id=project_id,
            run_id=root_run_id,
            message=completion_message,
            level=_status_to_log_level(terminal_status),
            data=WorkflowLogData(
                workflow_key=workflow_state.workflow_key,
                status=terminal_status,
                error_message=error_message,
            ),
        )

    async def _append_log_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        message: str,
        level: LogLevel = LogLevel.INFORMATION,
        data: BaseModel | dict[str, Any] | None = None,
    ) -> None:
        if isinstance(data, BaseModel):
            data_json = json.dumps(
                data.model_dump(by_alias=True, exclude_none=True),
                default=str,
            )
        else:
            data_json = json.dumps(data, default=str) if data is not None else None

        await JobRunLogDataService(project_id).add_log_async(
            job_run_id=run_id,
            level=level,
            message=message,
            data=data_json,
        )
