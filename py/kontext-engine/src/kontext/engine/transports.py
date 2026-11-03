"""Local claim-transport implementation backed by the relational store.

This is the local analogue of a queue consumer: instead of a broker pushing a
message, the worker polls for the next ``Queued`` run and claims it with a
single atomic conditional ``UPDATE`` (see
:meth:`kontext.data.JobRunDataService.claim_next_queued_run_sync`).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from kontext.common.jobs.transport import IJobRunClaimTransport, JobRunClaim


class LocalDbJobRunClaimTransport(IJobRunClaimTransport):
    """Claim queued runs by polling the local database.

    The set of projects to scan is provided by a callable so this stays
    decoupled from how projects are enumerated (which is deployment-specific).
    """

    def __init__(self, project_ids_provider) -> None:
        self._project_ids_provider = project_ids_provider

    async def claim_next(self, *, worker_identifier: str) -> JobRunClaim | None:
        from kontext.data import JobRunDataService

        for project_id in await self._project_ids_provider():
            run_service = JobRunDataService(project_id=project_id)
            claimed = await asyncio.to_thread(
                run_service.claim_next_queued_run_sync,
                worker_identifier=worker_identifier,
            )
            if claimed is not None:
                return JobRunClaim(run_id=str(claimed.id), project_id=str(project_id))
        return None


@dataclass(frozen=True)
class StaticProjectIds:
    """Trivial project-id provider for tests and single-project supervisors."""

    project_ids: tuple[str, ...]

    async def __call__(self) -> list[str]:
        return list(self.project_ids)
