"""Session-kernel identity.

A session kernel is keyed by an opaque string. Platform sessions are
namespaced so the supervisor can map a kernel back to its owning record when
reconciling deletions:

* ``chat:<uuid>``  — a chat session
* ``query:<uuid>`` — a query session
* ``<uuid>``       — a notebook file id (no namespace)

Run-scoped executions use any unique id that no session will reuse; they are
marked ephemeral and torn down by the runner, so their form does not matter.

Keep construction and parsing together: the supervisor's liveness check parses
these ids, so the format must have a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass

CHAT_PREFIX = "chat:"
QUERY_PREFIX = "query:"


def chat_session_kernel_id(chat_session_id: str) -> str:
    return f"{CHAT_PREFIX}{chat_session_id}"


def query_session_kernel_id(query_session_id: str) -> str:
    return f"{QUERY_PREFIX}{query_session_id}"


@dataclass(frozen=True)
class SessionKernelRef:
    """A parsed session-kernel id."""

    namespace: str  # "chat", "query", or "notebook"
    record_id: str


def parse_session_kernel_id(session_id: str) -> SessionKernelRef:
    """Parse a session-kernel id into its namespace and underlying record id."""
    if session_id.startswith(CHAT_PREFIX):
        return SessionKernelRef("chat", session_id[len(CHAT_PREFIX) :])
    if session_id.startswith(QUERY_PREFIX):
        return SessionKernelRef("query", session_id[len(QUERY_PREFIX) :])
    return SessionKernelRef("notebook", session_id)
