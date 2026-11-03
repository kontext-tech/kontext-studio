"""Neutral harness run-state persistence (`kontext-agent.SessionPersistence`).

This service is the *storage implementation* of the neutral persistence port:
agent harness adapters stay stateless compute, and the platform stores the
wire-shaped conversation snapshot plus the opaque harness-internal blob here.
See `kontext.agent.persistence` for the contract and
`docs/ai/harness-strategy.md` for the decision record.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from kontext.agent.persistence import MessageRecord

from .base_service import ProjectDataService
from .models import AgentHarnessState, AgentRunMessage


class AgentRunStateDataService(ProjectDataService):
    """Project-scoped storage implementing the neutral persistence port."""

    # ------------------------------------------------------------------
    # Message snapshot
    # ------------------------------------------------------------------

    async def replace_session_messages(
        self, session_id: str, records: Sequence[MessageRecord]
    ) -> None:
        await asyncio.to_thread(self._replace_messages_sync, session_id, records)

    async def list_messages(self, session_id: str) -> list[MessageRecord]:
        return await asyncio.to_thread(self._list_messages_sync, session_id)

    # ------------------------------------------------------------------
    # Harness-internal state (opaque blob)
    # ------------------------------------------------------------------

    async def save_harness_state(self, session_id: str, state_json: str) -> None:
        await asyncio.to_thread(self._save_harness_state_sync, session_id, state_json)

    async def load_harness_state(self, session_id: str) -> str | None:
        return await asyncio.to_thread(self._load_harness_state_sync, session_id)

    # ------------------------------------------------------------------
    # Sync internals
    # ------------------------------------------------------------------

    def _replace_messages_sync(self, session_id: str, records: Sequence[MessageRecord]) -> None:
        with self._session_scope() as session:
            session.query(AgentRunMessage).filter(AgentRunMessage.session_id == session_id).delete()
            for index, record in enumerate(records):
                session.add(
                    AgentRunMessage(
                        id=uuid4(),
                        session_id=session_id,
                        seq=record.seq if record.seq is not None else index,
                        message_json=record.message_json,
                    )
                )

    def _list_messages_sync(self, session_id: str) -> list[MessageRecord]:
        with self._session_scope() as session:
            rows = (
                session.query(AgentRunMessage)
                .filter(AgentRunMessage.session_id == session_id)
                .order_by(AgentRunMessage.seq.asc())
                .all()
            )
            return [
                MessageRecord(
                    session_id=str(row.session_id),
                    message_json=row.message_json,
                    seq=int(row.seq),
                )
                for row in rows
            ]

    def _save_harness_state_sync(self, session_id: str, state_json: str) -> None:
        with self._session_scope() as session:
            row = session.get(AgentHarnessState, session_id)
            if row is None:
                row = AgentHarnessState(session_id=session_id, state_json=state_json)
                session.add(row)
            else:
                row.state_json = state_json

    def _load_harness_state_sync(self, session_id: str) -> str | None:
        with self._session_scope() as session:
            row = session.get(AgentHarnessState, session_id)
            return row.state_json if row else None


def delete_run_state_rows(session: Any, session_id: str) -> None:
    """Delete all neutral run-state rows of a chat session in the caller's txn.

    Single point of truth for the cascade: used by `ChatSessionDataService`
    so the chat-delete path stays one transaction with the session soft-delete.
    """
    session.query(AgentRunMessage).filter(AgentRunMessage.session_id == session_id).delete(
        synchronize_session=False
    )
    harness_row = session.get(AgentHarnessState, session_id)
    if harness_row is not None:
        session.delete(harness_row)
