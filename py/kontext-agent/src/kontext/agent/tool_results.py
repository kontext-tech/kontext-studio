"""Per-run tool-result sidecar: explicit-identity typed payloads.

Tools frequently produce payloads that flow between calls of the same run —
an inline SQL result promoted to a durable data table, a chart consuming the
data table it references, a notebook materializing the same data. The harness
coerces tool outputs to strings, so the typed payload needs a side channel
keyed by *explicit identity* (the transient/durable identifier a tool minted
for the result), never by content hash or free-form string keys.

The sidecar is a port so each harness adapter can provide its own store
semantics; :class:`InMemoryToolResultSidecar` is the default implementation,
scoped to a session's :class:`ToolExecutionContext` and dropped when the
session context is unregistered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolResultEntry:
    """One sidecar slot: a typed payload plus its small descriptor.

    Entries are released with the session context (per streaming turn);
    payloads live here only as long as same-run consumers may still resolve
    their handle without a durable-store round trip.
    """

    payload: Any
    artifact_type: str | None = None
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    durable_id: str | None = None


class ToolResultSidecar(Protocol):
    """Port for explicit-identity typed-result storage within a run/session.

    ``get`` resolves both direct handles and registered aliases (a handle
    promoted to a durable id resolves through its alias chain).
    """

    def put(self, key: str, entry: ToolResultEntry) -> None: ...

    def get(self, key: str) -> ToolResultEntry | None: ...

    def alias(self, alias: str, key: str) -> None: ...

    def drop_all(self) -> None: ...


class InMemoryToolResultSidecar:
    """Dict-backed sidecar: explicit keys, alias indirection, no hashing."""

    def __init__(self) -> None:
        self._entries: dict[str, ToolResultEntry] = {}
        self._aliases: dict[str, str] = {}

    def put(self, key: str, entry: ToolResultEntry) -> None:
        self._entries[key] = entry

    def get(self, key: str) -> ToolResultEntry | None:
        entry = self._entries.get(key)
        if entry is None:
            resolved_key = self._aliases.get(key)
            if resolved_key is not None:
                entry = self._entries.get(resolved_key)
        return entry

    def alias(self, alias: str, key: str) -> None:
        self._aliases[alias] = key

    def drop_all(self) -> None:
        self._entries.clear()
        self._aliases.clear()
