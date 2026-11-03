"""Local (direct-access) service adapter implementations."""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Iterator, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.exc import OperationalError

from kontext.common.exceptions import TransientServiceError
from kontext.common.protocols import (
    ExecutionRunProvenance,
    IChatSessionProtocol,
    IExecutionRunContextServiceProtocol,
    IJobRunServiceProtocol,
    JobRunLogEntry,
)
from kontext.common.utils.enum_utils import safe_enum_conversion
from kontext.schema import (
    ArtifactType,
    JobRunStatus,
    LogLevel,
)

logger = logging.getLogger(__name__)

# Statuses from which a run never transitions again; side effects (workflow
# advancement) must fire exactly once, on entry into one of these.
_TERMINAL_JOB_RUN_STATUSES: frozenset[JobRunStatus] = frozenset(
    {
        JobRunStatus.SUCCEEDED,
        JobRunStatus.FAILED,
        JobRunStatus.CANCELED,
        JobRunStatus.TIMEDOUT,
        JobRunStatus.DEADLETTERED,
    }
)


@contextlib.contextmanager
def _translate_transient_db_errors() -> Iterator[None]:
    """Surface retryable SQLite lock contention as :class:`TransientServiceError`.

    The port contract promises transient failures as TransientServiceError so
    callers (workers) can retry; everything else is treated as permanent.
    """
    try:
        yield
    except OperationalError as exc:
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            raise TransientServiceError(
                f"Job run storage is temporarily unavailable: {exc}",
                problem_type="transient",
            ) from exc
        raise


class LocalJobRunService(IJobRunServiceProtocol):
    """Local adapter for job run operations."""

    def __init__(
        self,
        project_id: str,
        *,
        on_terminal_status: Any | None = None,
    ) -> None:
        """``on_terminal_status(project_id, run_id)`` fires side effects when a
        run first enters a terminal state. The engine never imports the
        orchestration layer; composition supplies the hook
        (:func:`kontext.execution.scheduling.handle_run_status_change_hook`)."""
        from kontext.data import (
            JobDataService,
            JobRunDataService,
            JobRunLogDataService,
        )

        self._project_id = str(project_id)
        self._on_terminal_status = on_terminal_status
        self._run_service = JobRunDataService(project_id=self._project_id)
        self._job_service = JobDataService(project_id=self._project_id)
        self._log_service = JobRunLogDataService(project_id=self._project_id)

    def _validate_project_id(self, project_id: str) -> None:
        if str(project_id) != self._project_id:
            raise ValueError(f"Project ID mismatch: {project_id} != {self._project_id}")

    async def get_job_run(self, run_id: str, project_id: str):
        self._validate_project_id(project_id)
        return await self._run_service.get_run_by_id_async(run_id)

    async def get_job(self, job_id: str, project_id: str):
        self._validate_project_id(project_id)
        return await self._job_service.get_job_by_id_async(job_id)

    async def update_status(
        self,
        run_id: str,
        project_id: str,
        status: JobRunStatus,
        error_message: str | None = None,
        result_data: dict | None = None,
    ) -> None:
        self._validate_project_id(project_id)
        normalized_status = safe_enum_conversion(JobRunStatus, status, None)
        status_value = status.value if hasattr(status, "value") else str(status)
        result_payload = json.dumps(result_data) if result_data is not None else None

        # Idempotency: callers deliver updates at-least-once and may replay a
        # terminal update. Side effects fire only on the *transition* into a
        # terminal status, so a replayed update never advances workflows twice.
        with _translate_transient_db_errors():
            current_run = await self._run_service.get_run_by_id_async(run_id)
            previous_status = (
                safe_enum_conversion(JobRunStatus, current_run.status, None)
                if current_run is not None
                else None
            )
            await self._run_service.update_status_async(
                UUID(run_id),
                status=status_value,
                error_message=error_message,
                result_data=result_payload,
            )

        transitions_to_terminal = normalized_status in _TERMINAL_JOB_RUN_STATUSES and (
            previous_status is None or previous_status not in _TERMINAL_JOB_RUN_STATUSES
        )
        if transitions_to_terminal and self._on_terminal_status is not None:
            await self._on_terminal_status(UUID(project_id), UUID(run_id))

    async def update_progress(self, run_id: str, project_id: str, progress: int) -> None:
        self._validate_project_id(project_id)
        with _translate_transient_db_errors():
            await self._run_service.update_progress_async(UUID(run_id), progress=progress)

    async def update_worker(self, run_id: str, project_id: str, worker: str) -> None:
        self._validate_project_id(project_id)
        with _translate_transient_db_errors():
            await self._run_service.update_worker_async(UUID(run_id), worker=worker)

    async def renew_lease(self, run_id: str, project_id: str, worker: str) -> bool:
        self._validate_project_id(project_id)
        with _translate_transient_db_errors():
            return await self._run_service.renew_run_lease_async(UUID(run_id), worker=worker)

    async def add_log(
        self,
        run_id: str,
        project_id: str,
        level: LogLevel,
        message: str,
        data: dict | None = None,
    ) -> None:
        self._validate_project_id(project_id)
        payload = json.dumps(data) if data is not None else None
        with _translate_transient_db_errors():
            await self._log_service.add_log_async(
                job_run_id=UUID(run_id), level=level, message=message, data=payload
            )

    async def add_log_batch(
        self,
        run_id: str,
        project_id: str,
        entries: Sequence[JobRunLogEntry],
    ) -> None:
        """Persist multiple log entries all-or-nothing.

        Atomicity (one transaction at the storage layer) plus the protocol's
        at-least-once delivery contract means a replayed batch can never
        produce duplicate entries. Remote adapters map this onto a single
        transport call.
        """
        self._validate_project_id(project_id)
        with _translate_transient_db_errors():
            await self._log_service.add_logs_async(job_run_id=UUID(run_id), entries=entries)


class LocalExecutionRunContextService(IExecutionRunContextServiceProtocol):
    """Local adapter for durable execution-run provenance."""

    def __init__(self, project_id: str) -> None:
        from kontext.data import ExecutionRunContextDataService

        self._project_id = str(project_id)
        self._service = ExecutionRunContextDataService(project_id)

    async def get_run_provenance(self, run_id: UUID | str) -> ExecutionRunProvenance | None:
        context = await self._service.get_by_run_id_async(run_id)
        if context is None:
            return None
        return ExecutionRunProvenance(
            run_id=str(context.run_id),
            chat_session_id=str(context.chat_session_id) if context.chat_session_id else None,
            parent_run_id=str(context.parent_run_id) if context.parent_run_id else None,
            root_run_id=str(context.root_run_id) if context.root_run_id else None,
        )


class LocalChatSessionService(IChatSessionProtocol):
    """Local adapter for chat session persistence."""

    def __init__(self, project_id: str) -> None:
        from kontext.data import ChatSessionDataService

        self._service = ChatSessionDataService(project_id=project_id)

    async def create_session(self, request, user_id: str | None):
        return await self._service.create_session_async(request, user_id)

    async def get_session(self, session_id: str):
        return await self._service.get_session_by_id_async(session_id)

    async def update_session(self, session_id: str, request, user_id: str | None):
        return await self._service.update_session_async(session_id, request, user_id)

    async def delete_session(self, session_id: str, user_id: str | None) -> None:
        await self._service.delete_session_async(session_id, user_id)

    async def list_artifacts(self, session_id: str):
        return await self._service.get_session_artifacts_async(session_id)

    async def add_artifact(self, session_id: str, artifact):
        return await self.upsert_artifact(
            session_id=session_id,
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            title=artifact.title,
            meta=artifact.meta,
        )

    async def upsert_artifact(
        self,
        session_id: str,
        artifact_id: str,
        artifact_type: ArtifactType,
        title: str | None,
        meta: dict[str, Any] | None = None,
    ):
        return await self._service.upsert_artifact_async(
            session_id=session_id,
            artifact_id=artifact_id,
            artifact_type=artifact_type.value,
            title=title,
            meta=meta,
        )

    async def update_token_usage(
        self, session_id: str, tokens_inbound: int, tokens_outbound: int
    ) -> None:
        await self._service.update_token_usage_async(
            session_id=session_id,
            tokens_inbound=tokens_inbound,
            tokens_outbound=tokens_outbound,
        )
