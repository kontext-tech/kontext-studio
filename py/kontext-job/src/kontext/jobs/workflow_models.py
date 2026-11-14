"""Workflow DTO models and durable execution-context metadata shaping.

Split out of ``workflows.py`` (M8.1): this module owns the workflow pydantic
models, execution-status constants, and the pure metadata helpers; the
orchestration service lives in ``workflows.py``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.data import ExecutionRunContext
from kontext.schema import (
    ExecutionRunStatus,
    JobRunModel,
    JobRunStatus,
    JobTriggerType,
    LogLevel,
    TriggerActorModel,
)

logger = logging.getLogger(__name__)

WORKFLOW_ENGINE_NAME = "workflow"

_WORKFLOW_METADATA_KEY = "workflow"
_WORKFLOW_ROOT_JOB_TYPE_PREFIX = "python.workflow"
_STEP_STATUS_PENDING = "pending"
_STEP_STATUS_SKIPPED = "skipped"
_RUN_STATUS_QUEUED = ExecutionRunStatus.QUEUED.value
_RUN_STATUS_STARTING = ExecutionRunStatus.STARTING.value
_RUN_STATUS_RUNNING = ExecutionRunStatus.RUNNING.value
_RUN_STATUS_WAITING_INPUT = ExecutionRunStatus.WAITINGINPUT.value
_RUN_STATUS_SUCCEEDED = ExecutionRunStatus.SUCCEEDED.value
_RUN_STATUS_FAILED = ExecutionRunStatus.FAILED.value
_RUN_STATUS_CANCELLED = ExecutionRunStatus.CANCELLED.value
_RUN_STATUS_TIMED_OUT = ExecutionRunStatus.TIMEDOUT.value
_ACTIVE_STEP_STATUSES = {
    _RUN_STATUS_QUEUED,
    _RUN_STATUS_STARTING,
    _RUN_STATUS_RUNNING,
    _RUN_STATUS_WAITING_INPUT,
}
_TERMINAL_STEP_STATUSES = {
    _RUN_STATUS_SUCCEEDED,
    _RUN_STATUS_FAILED,
    _RUN_STATUS_CANCELLED,
    _RUN_STATUS_TIMED_OUT,
    _STEP_STATUS_SKIPPED,
}
_FAILURE_STEP_STATUSES = {
    _RUN_STATUS_FAILED,
    _RUN_STATUS_CANCELLED,
    _RUN_STATUS_TIMED_OUT,
    _STEP_STATUS_SKIPPED,
}
_TERMINAL_JOB_STATUSES = {
    JobRunStatus.SUCCEEDED,
    JobRunStatus.FAILED,
    JobRunStatus.CANCELED,
    JobRunStatus.TIMEDOUT,
    JobRunStatus.DEADLETTERED,
}
_CANCELLABLE_JOB_STATUSES = {
    JobRunStatus.QUEUED,
    JobRunStatus.DISPATCHED,
    JobRunStatus.RUNNING,
}


class _WorkflowModel(BaseModel):
    """Base model for internal workflow state stored in execution metadata."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )


class _WorkflowCamelModel(_WorkflowModel):
    """Base model for workflow payloads exposed in camelCase JSON."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        alias_generator=to_camel,
    )


class WorkflowJobStepDefinition(_WorkflowModel):
    """A single job-backed workflow step."""

    key: str
    name: str
    job_type: str
    job_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    job_id: str | None = None
    job_description: str | None = None
    timeout_seconds: int | None = None
    priority: int = 5


class WorkflowStartRequest(_WorkflowModel):
    """Definition for a lightweight workflow run."""

    workflow_key: str
    workflow_name: str
    steps: list[WorkflowJobStepDefinition]
    description: str | None = None
    triggered_by: TriggerActorModel | None = None
    trigger_type: JobTriggerType = JobTriggerType.MANUAL
    trigger_configuration: dict[str, Any] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class WorkflowStepDispatch(_WorkflowModel):
    """Dispatch configuration persisted for a workflow step."""

    job_id: str | None = None
    job_type: str
    job_name: str
    job_description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int | None = None
    priority: int = 5


class WorkflowStepState(_WorkflowModel):
    """Durable state tracked for a workflow step."""

    key: str
    name: str
    depends_on: list[str] = Field(default_factory=list)
    run_id: str | None = None
    status: str = _STEP_STATUS_PENDING
    attempt_count: int = 0
    completed_at: str | None = None
    error_message: str | None = None
    dispatch: WorkflowStepDispatch

    @classmethod
    def from_definition(cls, step: WorkflowJobStepDefinition) -> WorkflowStepState:
        return cls(
            key=step.key,
            name=step.name,
            depends_on=list(step.depends_on),
            dispatch=WorkflowStepDispatch(
                job_id=step.job_id,
                job_type=step.job_type,
                job_name=step.job_name,
                job_description=step.job_description,
                parameters=dict(step.parameters),
                timeout_seconds=step.timeout_seconds,
                priority=step.priority,
            ),
        )


class WorkflowRootState(_WorkflowModel):
    """Root workflow metadata persisted in execution-run context."""

    workflow_key: str
    workflow_name: str
    workflow_description: str | None = None
    requested_by: str | None = None
    trigger_actor: TriggerActorModel | None = None
    is_workflow_root: bool = True
    steps: list[WorkflowStepState] = Field(default_factory=list)

    @classmethod
    def from_request(cls, workflow: WorkflowStartRequest) -> WorkflowRootState:
        return cls(
            workflow_key=workflow.workflow_key,
            workflow_name=workflow.workflow_name,
            workflow_description=workflow.description,
            requested_by=format_trigger_actor(workflow.triggered_by),
            trigger_actor=workflow.triggered_by,
            steps=[WorkflowStepState.from_definition(step) for step in workflow.steps],
        )

    def find_step(self, step_key: str) -> WorkflowStepState | None:
        return next((step for step in self.steps if step.key == step_key), None)


class WorkflowStepContextMetadata(_WorkflowModel):
    """Per-step workflow lineage attached to child execution contexts."""

    workflow_key: str
    step_key: str
    is_workflow_root: bool = False


class WorkflowDependencyTriggerConfiguration(_WorkflowCamelModel):
    """Trigger configuration when a workflow step dispatches a dependency job."""

    workflow_key: str
    root_run_id: str
    step_key: str


class WorkflowLogData(_WorkflowCamelModel):
    """Structured workflow log payload shared across workflow lifecycle events."""

    workflow_key: str
    step_key: str | None = None
    root_run_id: str | None = None
    step_run_id: str | None = None
    previous_run_id: str | None = None
    new_run_id: str | None = None
    requested_by: str | None = None
    status: str | None = None
    reason: str | None = None
    error_message: str | None = None
    job_type: str | None = None
    step_count: int | None = None


class WorkflowResultStep(_WorkflowCamelModel):
    """Compact step summary exposed on workflow result payloads."""

    key: str
    name: str
    status: str | None = None
    run_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    error_message: str | None = None


class WorkflowResultData(_WorkflowCamelModel):
    """Execution result payload for workflow root runs."""

    kind: str = "workflow"
    status: str
    workflow_key: str
    workflow_name: str
    step_count: int
    completed_step_count: int
    successful_step_count: int
    failed_step_count: int
    steps: list[WorkflowResultStep] = Field(default_factory=list)

    @classmethod
    def from_state(
        cls,
        workflow_state: WorkflowRootState,
        *,
        status: str,
    ) -> WorkflowResultData:
        return cls(
            status=status,
            workflow_key=workflow_state.workflow_key,
            workflow_name=workflow_state.workflow_name,
            step_count=len(workflow_state.steps),
            completed_step_count=sum(
                1 for step in workflow_state.steps if step.status in _TERMINAL_STEP_STATUSES
            ),
            successful_step_count=sum(
                1 for step in workflow_state.steps if step.status == _RUN_STATUS_SUCCEEDED
            ),
            failed_step_count=sum(
                1
                for step in workflow_state.steps
                if step.status in {_RUN_STATUS_FAILED, _RUN_STATUS_CANCELLED, _RUN_STATUS_TIMED_OUT}
            ),
            steps=[
                WorkflowResultStep(
                    key=step.key,
                    name=step.name,
                    status=step.status,
                    run_id=step.run_id,
                    depends_on=list(step.depends_on),
                    error_message=step.error_message,
                )
                for step in workflow_state.steps
            ],
        )


class WorkflowProjectionMetadata(_WorkflowModel):
    """Workflow lineage surfaced into execution run and log projections."""

    workflow_key: str | None = None
    step_key: str | None = None
    is_workflow_root: bool | None = None
    workflow_state: WorkflowRootState | None = None


def parse_engine_metadata_json(engine_metadata_json: str | None) -> dict[str, Any]:
    """Parse engine metadata into a dictionary, tolerating malformed JSON."""
    if not engine_metadata_json:
        return {}

    try:
        payload = json.loads(engine_metadata_json)
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def get_workflow_metadata(
    engine_metadata_json: str | None,
) -> dict[str, Any] | None:
    """Return stored workflow metadata when present."""
    metadata = parse_engine_metadata_json(engine_metadata_json)
    workflow_metadata = metadata.get(_WORKFLOW_METADATA_KEY)
    return workflow_metadata if isinstance(workflow_metadata, dict) else None


def upsert_workflow_metadata_json(
    engine_metadata_json: str | None,
    *,
    workflow_metadata: BaseModel | dict[str, Any],
) -> str:
    """Merge workflow metadata into existing engine metadata JSON."""
    metadata = parse_engine_metadata_json(engine_metadata_json)
    metadata[_WORKFLOW_METADATA_KEY] = _dump_workflow_metadata(workflow_metadata)
    return json.dumps(metadata, default=str, sort_keys=True)


def extract_workflow_projection_metadata(
    context: ExecutionRunContext | None,
) -> WorkflowProjectionMetadata:
    """Extract workflow projection fields from a run context."""
    if context is None:
        return WorkflowProjectionMetadata()

    workflow_metadata = get_workflow_metadata(context.engine_metadata_json)
    if workflow_metadata is None:
        return WorkflowProjectionMetadata()

    if workflow_metadata.get("is_workflow_root"):
        workflow_state = _parse_workflow_model(
            workflow_metadata,
            WorkflowRootState,
        )
        if workflow_state is None:
            return WorkflowProjectionMetadata()

        return WorkflowProjectionMetadata(
            workflow_key=workflow_state.workflow_key,
            is_workflow_root=workflow_state.is_workflow_root,
            workflow_state=workflow_state,
        )

    step_metadata = _parse_workflow_model(
        workflow_metadata,
        WorkflowStepContextMetadata,
    )
    if step_metadata is None:
        return WorkflowProjectionMetadata()

    return WorkflowProjectionMetadata(
        workflow_key=step_metadata.workflow_key,
        step_key=step_metadata.step_key,
        is_workflow_root=step_metadata.is_workflow_root,
    )


def _build_root_job_type(workflow_key: str) -> str:
    normalized_key = workflow_key.replace(" ", "_").replace("-", "_")
    return f"{_WORKFLOW_ROOT_JOB_TYPE_PREFIX}.{normalized_key}.Root"


def _build_root_workflow_metadata(
    workflow: WorkflowStartRequest,
) -> WorkflowRootState:
    return WorkflowRootState.from_request(workflow)


def _build_step_workflow_metadata(
    *,
    workflow_key: str,
    step_key: str,
) -> WorkflowStepContextMetadata:
    return WorkflowStepContextMetadata(
        workflow_key=workflow_key,
        step_key=step_key,
    )


def _load_root_workflow_state(
    context: ExecutionRunContext | None,
) -> WorkflowRootState | None:
    if context is None:
        return None

    workflow_state = get_workflow_metadata(context.engine_metadata_json)
    if not workflow_state or not workflow_state.get("is_workflow_root"):
        return None

    return _parse_workflow_model(workflow_state, WorkflowRootState)


def _find_step(
    workflow_state: WorkflowRootState,
    step_key: str,
) -> WorkflowStepState | None:
    return workflow_state.find_step(step_key)


def _has_active_steps(workflow_state: WorkflowRootState) -> bool:
    return any(step.status in _ACTIVE_STEP_STATUSES for step in workflow_state.steps)


def _is_step_ready_to_dispatch(
    workflow_state: WorkflowRootState,
    step: WorkflowStepState,
) -> bool:
    if step.status != _STEP_STATUS_PENDING:
        return False

    steps_by_key = {workflow_step.key: workflow_step for workflow_step in workflow_state.steps}
    for dependency_key in step.depends_on:
        dependency = steps_by_key.get(dependency_key)
        if dependency is None or dependency.status != _RUN_STATUS_SUCCEEDED:
            return False
    return True


def _mark_blocked_steps_as_skipped(
    workflow_state: WorkflowRootState,
) -> list[WorkflowStepState]:
    steps = workflow_state.steps
    steps_by_key = {step.key: step for step in steps}
    skipped_steps: list[WorkflowStepState] = []

    for step in steps:
        if step.status != _STEP_STATUS_PENDING:
            continue

        blocked_by = [
            dependency_key
            for dependency_key in step.depends_on
            if (dependency := steps_by_key.get(dependency_key))
            and dependency.status in _FAILURE_STEP_STATUSES
        ]
        if not blocked_by:
            continue

        step.status = _STEP_STATUS_SKIPPED
        step.error_message = "Blocked by failed dependency: " + ", ".join(sorted(blocked_by))
        skipped_steps.append(step)

    return skipped_steps


def _reset_skipped_descendants(
    workflow_state: WorkflowRootState,
    retried_step_key: str,
) -> None:
    steps = workflow_state.steps
    descendants_to_reset = {retried_step_key}
    changed = True
    while changed:
        changed = False
        for step in steps:
            if step.status != _STEP_STATUS_SKIPPED:
                continue
            dependencies = set(step.depends_on)
            if not dependencies.intersection(descendants_to_reset):
                continue
            step.status = _STEP_STATUS_PENDING
            step.run_id = None
            step.completed_at = None
            step.error_message = None
            descendants_to_reset.add(step.key)
            changed = True


def _determine_terminal_status(workflow_state: WorkflowRootState) -> str:
    step_statuses = [step.status for step in workflow_state.steps]
    if not step_statuses:
        return _RUN_STATUS_SUCCEEDED

    if all(status == _RUN_STATUS_SUCCEEDED for status in step_statuses):
        return _RUN_STATUS_SUCCEEDED
    if any(status == _RUN_STATUS_TIMED_OUT for status in step_statuses):
        return _RUN_STATUS_TIMED_OUT
    if any(status == _RUN_STATUS_FAILED for status in step_statuses):
        return _RUN_STATUS_FAILED
    if any(status == _RUN_STATUS_CANCELLED for status in step_statuses):
        return _RUN_STATUS_CANCELLED
    return _RUN_STATUS_FAILED


def _build_terminal_error_message(workflow_state: WorkflowRootState) -> str | None:
    for step in workflow_state.steps:
        if step.status in {
            _RUN_STATUS_TIMED_OUT,
            _RUN_STATUS_FAILED,
            _RUN_STATUS_CANCELLED,
        }:
            error_message = _coerce_optional_str(step.error_message)
            if error_message:
                return error_message
            return f"Workflow step '{step.name}' {step.status}"
    return None


def _job_run_to_step_status(job_run: JobRunModel) -> str:
    if job_run.status == JobRunStatus.SUCCEEDED:
        return _RUN_STATUS_SUCCEEDED
    if job_run.status in {JobRunStatus.FAILED, JobRunStatus.DEADLETTERED}:
        return _RUN_STATUS_FAILED
    if job_run.status == JobRunStatus.CANCELED:
        return _RUN_STATUS_CANCELLED
    if job_run.status == JobRunStatus.TIMEDOUT:
        return _RUN_STATUS_TIMED_OUT
    if job_run.status == JobRunStatus.QUEUED:
        return _RUN_STATUS_QUEUED
    if job_run.status == JobRunStatus.DISPATCHED:
        return _RUN_STATUS_STARTING
    return _RUN_STATUS_RUNNING


def _calculate_progress(workflow_state: WorkflowRootState) -> int:
    steps = workflow_state.steps
    if not steps:
        return 100
    completed_count = sum(1 for step in steps if step.status in _TERMINAL_STEP_STATUSES)
    return int((completed_count / len(steps)) * 100)


def _build_workflow_result_data(
    workflow_state: WorkflowRootState,
    *,
    status: str,
) -> WorkflowResultData:
    return WorkflowResultData.from_state(workflow_state, status=status)


def _dump_workflow_metadata(
    workflow_metadata: BaseModel | dict[str, Any],
) -> dict[str, Any]:
    if isinstance(workflow_metadata, BaseModel):
        return workflow_metadata.model_dump()
    return workflow_metadata


def _parse_workflow_model[TWorkflowModel: BaseModel](
    payload: dict[str, Any],
    model_type: type[TWorkflowModel],
) -> TWorkflowModel | None:
    try:
        return model_type.model_validate(payload)
    except ValidationError:
        logger.warning("Failed to parse workflow payload as %s", model_type.__name__)
        return None


def _root_job_status_from_run_status(run_status: str) -> str:
    if run_status == _RUN_STATUS_SUCCEEDED:
        return JobRunStatus.SUCCEEDED.value
    if run_status == _RUN_STATUS_CANCELLED:
        return JobRunStatus.CANCELED.value
    if run_status == _RUN_STATUS_TIMED_OUT:
        return JobRunStatus.TIMEDOUT.value
    return JobRunStatus.FAILED.value


def _status_to_log_level(status: str) -> LogLevel:
    if status == _RUN_STATUS_SUCCEEDED:
        return LogLevel.INFORMATION
    if status in {_RUN_STATUS_CANCELLED, _STEP_STATUS_SKIPPED}:
        return LogLevel.WARNING
    return LogLevel.ERROR


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
