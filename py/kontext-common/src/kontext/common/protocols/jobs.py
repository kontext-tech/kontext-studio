"""Job run service contracts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from kontext.schema import JobRunStatus, LogLevel

if TYPE_CHECKING:
    from kontext.schema import JobModel, JobRunModel


@dataclass(frozen=True)
class JobRunLogEntry:
    """A single durable log record for a job run."""

    level: LogLevel
    message: str
    data: dict[str, Any] | None = None


class IJobRunServiceProtocol(Protocol):
    """Protocol defining the interface for job run services.

    This is the worker's view of a job run: status, progress, worker
    assignment, and logs. Run *creation* and *execution* are owned by the
    durable run layer, not this service, so they are not part of the contract.

    Delivery semantics (all operations):

    - Operations are delivered **at-least-once** by callers: a worker that is
      unsure whether an update landed retries it. Implementations must
      therefore be *idempotent* — repeating an identical ``update_status``
      must leave the run's observable state unchanged and must not repeat
      transition side effects (workflow advancement, notifications, ...).
    - Retryable infrastructure failures must surface as
      :class:`~kontext.common.exceptions.TransientServiceError`; every other
      error is treated as permanent by callers.
    """

    async def get_job_run(self, run_id: str, project_id: str) -> JobRunModel | None: ...

    async def get_job(self, job_id: str, project_id: str) -> JobModel | None: ...

    async def update_status(
        self,
        run_id: str,
        project_id: str,
        status: JobRunStatus,
        error_message: str | None = None,
        result_data: dict[str, Any] | None = None,
    ) -> None: ...

    async def update_progress(self, run_id: str, project_id: str, progress: int) -> None: ...

    async def update_worker(self, run_id: str, project_id: str, worker: str) -> None: ...

    async def renew_lease(self, run_id: str, project_id: str, worker: str) -> bool:
        """Renew the claim lease for a run this worker still owns.

        The lease (``lease_expires_at``) is the DB-poll analogue of a queue
        visibility timeout: a claiming worker stamps it at claim time and must
        renew it periodically so the reaper does not reclaim the run while this
        worker is alive but quiet. Implementations must verify the run is still
        claimed by *worker* and only then extend the lease.

        Returns:
            False when the run is no longer claimed by *worker* (reclaimed
            after a lapsed lease, re-claimed elsewhere, or no longer in a
            claimable state). The caller must treat that as lease loss and
            abort execution.
        """
        ...

    async def add_log(
        self,
        run_id: str,
        project_id: str,
        level: LogLevel,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None: ...

    async def add_log_batch(
        self,
        run_id: str,
        project_id: str,
        entries: Sequence[JobRunLogEntry],
    ) -> None:
        """Persist multiple log entries for a run all-or-nothing.

        The batch is atomic: either every entry lands or none does. Combined
        with the at-least-once delivery contract above this makes a replayed
        batch safe — it can never produce duplicate entries. Remote
        implementations should map the batch onto a single transport call so
        chatty logging does not translate into chatty networking.
        """
        ...
