"""Worker-side contract for claiming queued job runs.

A *claim* reserves one queued run for one worker. Local mode claims by polling
the relational store; a hosted deployment would claim from a message queue.
Both are implementations of :class:`IJobRunClaimTransport`, and the worker /
supervisor depends only on this contract, so the same supervisor runs in either
deployment without knowing how work is discovered.

This is deliberately separate from :class:`~kontext.common.messaging.IQueueClient`:
the queue is a *message* transport, whereas this abstracts *claiming* (finding
and atomically reserving a unit of work).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class JobRunClaim:
    """A reserved job run handed to a worker for execution."""

    run_id: str
    project_id: str


class IJobRunClaimTransport(Protocol):
    """Source of claimable job runs for a worker process."""

    async def claim_next(self, *, worker_identifier: str) -> JobRunClaim | None:
        """Reserve the next queued run and return it, or ``None`` if idle.

        Implementations must be atomic: two workers calling concurrently must
        never receive the same run.
        """
        ...
