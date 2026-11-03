"""Data service for durable execution-run context."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select

from kontext.common.utils.datetime_utils import utc_now

from .base_service import ProjectDataService, ensure_uuid
from .models import ExecutionRunContext, JobRun

_UNSET = object()


class ExecutionRunContextDataService(ProjectDataService):
    """Manage durable pause/resume context for execution runs."""

    async def get_by_run_ids_async(
        self, run_ids: Sequence[UUID | str]
    ) -> dict[UUID, ExecutionRunContext]:
        normalized_run_ids = [ensure_uuid(run_id) for run_id in run_ids if run_id]
        return await asyncio.to_thread(self._get_by_run_ids_sync, normalized_run_ids)

    def _get_by_run_ids_sync(self, run_ids: Sequence[UUID]) -> dict[UUID, ExecutionRunContext]:
        if not run_ids:
            return {}

        with self._session_scope(commit=False) as session:
            stmt = select(ExecutionRunContext).where(ExecutionRunContext.run_id.in_(run_ids))
            contexts = session.execute(stmt).scalars().all()
            return {context.run_id: self._make_detached(session, context) for context in contexts}

    async def get_by_run_id_async(self, run_id: UUID | str) -> ExecutionRunContext | None:
        return await asyncio.to_thread(self._get_by_run_id_sync, ensure_uuid(run_id))

    def _get_by_run_id_sync(self, run_id: UUID) -> ExecutionRunContext | None:
        with self._session_scope(commit=False) as session:
            context = session.get(ExecutionRunContext, run_id)
            if context is None:
                return None
            return self._make_detached(session, context)

    async def get_waiting_context_for_chat_session_async(
        self,
        *,
        chat_session_id: UUID | str,
        agent_runtime_run_id: str | None = None,
    ) -> ExecutionRunContext | None:
        return await asyncio.to_thread(
            self._get_waiting_context_for_chat_session_sync,
            ensure_uuid(chat_session_id),
            agent_runtime_run_id=agent_runtime_run_id,
        )

    def _get_waiting_context_for_chat_session_sync(
        self, chat_session_id: UUID, *, agent_runtime_run_id: str | None = None
    ) -> ExecutionRunContext | None:
        with self._session_scope(commit=False) as session:
            stmt = select(ExecutionRunContext).where(
                ExecutionRunContext.chat_session_id == chat_session_id,
                ExecutionRunContext.waiting_for_input.is_(True),
            )
            if agent_runtime_run_id:
                stmt = stmt.where(ExecutionRunContext.agent_runtime_run_id == agent_runtime_run_id)
            stmt = stmt.order_by(ExecutionRunContext.updated_at.desc())
            context = session.execute(stmt).scalars().first()
            if context is None:
                return None
            return self._make_detached(session, context)

    async def list_by_root_run_id_async(self, root_run_id: UUID | str) -> list[ExecutionRunContext]:
        return await asyncio.to_thread(self._list_by_root_run_id_sync, ensure_uuid(root_run_id))

    def _list_by_root_run_id_sync(self, root_run_id: UUID) -> list[ExecutionRunContext]:
        with self._session_scope(commit=False) as session:
            stmt = (
                select(ExecutionRunContext)
                .where(ExecutionRunContext.root_run_id == root_run_id)
                .order_by(ExecutionRunContext.created_at.asc())
            )
            contexts = session.execute(stmt).scalars().all()
            return [self._make_detached(session, context) for context in contexts]

    async def upsert_context_async(
        self,
        *,
        run_id: UUID | str,
        chat_session_id: UUID | str | object | None = _UNSET,
        agent_session_id: str | object | None = _UNSET,
        agent_runtime_run_id: str | object | None = _UNSET,
        parent_run_id: UUID | str | object | None = _UNSET,
        root_run_id: UUID | str | object | None = _UNSET,
        waiting_for_input: bool | object = _UNSET,
        engine_name: str | object | None = _UNSET,
        engine_metadata_json: str | object | None = _UNSET,
    ) -> ExecutionRunContext:
        return await asyncio.to_thread(
            self._upsert_context_sync,
            ensure_uuid(run_id),
            chat_session_id=chat_session_id,
            agent_session_id=agent_session_id,
            agent_runtime_run_id=agent_runtime_run_id,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            waiting_for_input=waiting_for_input,
            engine_name=engine_name,
            engine_metadata_json=engine_metadata_json,
        )

    def _upsert_context_sync(
        self,
        run_id: UUID,
        *,
        chat_session_id: UUID | str | object | None = _UNSET,
        agent_session_id: str | object | None = _UNSET,
        agent_runtime_run_id: str | object | None = _UNSET,
        parent_run_id: UUID | str | object | None = _UNSET,
        root_run_id: UUID | str | object | None = _UNSET,
        waiting_for_input: bool | object = _UNSET,
        engine_name: str | object | None = _UNSET,
        engine_metadata_json: str | object | None = _UNSET,
    ) -> ExecutionRunContext:
        with self._session_scope() as session:
            job_run = session.get(JobRun, run_id)
            if job_run is None:
                raise ValueError(f"Job run {run_id} not found")

            context = session.get(ExecutionRunContext, run_id)
            if context is None:
                context = ExecutionRunContext(run_id=run_id)
                session.add(context)

            self._apply_if_present(
                context,
                chat_session_id=(
                    ensure_uuid(chat_session_id)  # type: ignore
                    if chat_session_id is not _UNSET and chat_session_id is not None
                    else chat_session_id
                ),
                agent_session_id=agent_session_id,
                agent_runtime_run_id=agent_runtime_run_id,
                parent_run_id=(
                    ensure_uuid(parent_run_id)  # type: ignore
                    if parent_run_id is not _UNSET and parent_run_id is not None
                    else parent_run_id
                ),
                root_run_id=(
                    ensure_uuid(root_run_id)  # type: ignore
                    if root_run_id is not _UNSET and root_run_id is not None
                    else root_run_id
                ),
                waiting_for_input=waiting_for_input,
                engine_name=engine_name,
                engine_metadata_json=engine_metadata_json,
            )
            context.updated_at = utc_now()
            session.flush()
            return self._make_detached(session, context)

    def _apply_if_present(self, context: ExecutionRunContext, **values: Any) -> None:
        for field_name, value in values.items():
            if value is _UNSET:
                continue
            setattr(context, field_name, value)
