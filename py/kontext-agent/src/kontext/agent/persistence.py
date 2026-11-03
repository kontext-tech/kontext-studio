"""Neutral run-state persistence port.

Harness adapters are stateless compute: run state — the platform-facing message
snapshot and the harness-internal blob — is stored by the platform through this
port, not by harness-owned databases.

The split is deliberate and minimal. Platform reads (chat history) need the
wire-shaped message snapshot. Everything the harness needs to run its own
mechanics (paused runs, requirements, metrics, summaries) lives in one opaque
blob owned by the adapter. There is no second, platform-interpreted copy of
harness-private state.

Layout of ownership:

- This module (kontext-agent) owns the contract: the record DTO and the
  `SessionPersistence` protocol, plus an in-memory double for tests.
- `kontext-data` owns the storage implementation (project-scoped SQL tables via
  `AgentRunStateDataService`).
- Harness adapters receive an implementation through composition and never own
  a schema.

Persisted payloads are wire-shape strings (`ChatMessage.model_dump_json()`)
so the contract stays schema-stable across harness swaps.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

__all__ = [
    "InMemorySessionPersistence",
    "MessageRecord",
    "SessionPersistence",
]


@dataclass(frozen=True)
class MessageRecord:
    """One persisted conversation message in wire shape."""

    session_id: str
    message_json: str
    seq: int | None = None


@runtime_checkable
class SessionPersistence(Protocol):
    """Storage port implemented by the platform (`kontext-data`)."""

    async def replace_session_messages(
        self,
        session_id: str,
        records: Sequence[MessageRecord],
    ) -> None:
        """Replace the persisted conversation snapshot for a session.

        Full-snapshot writes keep the store idempotent: adapters persist the
        authoritative conversation after terminal events, never per delta.
        """
        ...

    async def list_messages(self, session_id: str) -> list[MessageRecord]:
        """Return the persisted messages ordered by ``seq``."""
        ...

    async def save_harness_state(self, session_id: str, state_json: str) -> None:
        """Store the harness-internal session payload (opaque JSON blob).

        Harnesses serialize private per-session state (their internal session
        and run records) wherever harness mechanics need it. The platform
        stores the blob opaquely: it never substitutes for the wire-shaped
        records above, it only keeps the harness working without owning
        storage.
        """
        ...

    async def load_harness_state(self, session_id: str) -> str | None:
        """Return the stored harness-internal payload, if any."""
        ...


@dataclass
class InMemorySessionPersistence:
    """In-memory `SessionPersistence` double for tests and conformance runs."""

    messages: dict[str, list[MessageRecord]] = field(default_factory=dict)
    harness_states: dict[str, str] = field(default_factory=dict)

    async def replace_session_messages(
        self, session_id: str, records: Sequence[MessageRecord]
    ) -> None:
        self.messages[session_id] = list(records)

    async def list_messages(self, session_id: str) -> list[MessageRecord]:
        return list(self.messages.get(session_id, ()))

    async def save_harness_state(self, session_id: str, state_json: str) -> None:
        self.harness_states[session_id] = state_json

    async def load_harness_state(self, session_id: str) -> str | None:
        return self.harness_states.get(session_id)
