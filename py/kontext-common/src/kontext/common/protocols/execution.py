"""Execution run provenance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ExecutionRunProvenance:
    """Worker-facing view of an execution run's durable linkage.

    Provenance is recorded when a run is queued (by the API) and read back
    inside the worker, so linkage like the owning chat session never has to
    be serialized into job parameters (which cross the queue/process boundary).

    IDs are normalized string representations — the port's DTO convention —
    so implementations never leak their native identity types across the
    boundary.
    """

    run_id: str
    chat_session_id: str | None = None
    parent_run_id: str | None = None
    root_run_id: str | None = None


class IExecutionRunContextServiceProtocol(Protocol):
    """Protocol defining the worker's view of durable execution-run provenance."""

    async def get_run_provenance(self, run_id: UUID | str) -> ExecutionRunProvenance | None:
        """Return the provenance recorded for *run_id*, or None if unrecorded."""
        ...
