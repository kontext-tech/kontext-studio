"""Regression tests for the in-process query session service.

Concurrency contract: the service holds the process-wide session lock while a
query runs, so the query must stay bounded (an unbounded query would silently
block every later query on the same session, e.g. parallel agent tool calls),
and disposal must stop the orphaned query before closing the connection.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from kontext.common.constants import QueryConstants
from kontext.query.in_process_query_session_service import InProcessQuerySessionService
from kontext.schema import DataTable, QuerySessionStatus

_PROJECT_ID = str(uuid.uuid4())


class _HangingEngine:
    """Engine whose fetch never returns until it is interrupted."""

    def __init__(self) -> None:
        self.interrupted = False
        self.disposed = False
        self._released = asyncio.Event()

    async def connect(self) -> None:
        return None

    async def fetch_data_table(self, sql: str, max_rows: int):
        del sql, max_rows
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._released.wait(), timeout=60)

    async def interrupt(self) -> None:
        self.interrupted = True
        self._released.set()

    async def dispose(self) -> None:
        self.disposed = True

    def get_session_file_size(self) -> None:
        return None


def _resolve_engine_side_effect(engine: Any) -> Any:
    async def _resolve(**kwargs: Any) -> Any:
        del kwargs
        return engine

    return _resolve


def _make_service(*, session_update: AsyncMock) -> InProcessQuerySessionService:
    service = InProcessQuerySessionService(_PROJECT_ID, runtime_provider=cast(Any, object()))
    service._service = cast(
        Any,
        SimpleNamespace(
            get_query_session=AsyncMock(return_value=None),
            create_session_async=AsyncMock(return_value=SimpleNamespace(id=str(uuid.uuid4()))),
            update_query_session=session_update,
        ),
    )
    service._data_service = cast(
        Any, SimpleNamespace(list_sessions_by_status=lambda *args, **kwargs: ([], None))
    )
    service._catalog_data_service = cast(Any, SimpleNamespace())
    return service


@pytest.mark.asyncio
@patch("kontext.query.in_process_query_session_service.resolve_engine_for_session")
async def test_query_timeout_stops_in_flight_query_and_releases_lock(resolve_engine: Any) -> None:
    engine = _HangingEngine()
    resolve_engine.side_effect = _resolve_engine_side_effect(engine)

    session_update = AsyncMock(return_value=None)
    service = _make_service(session_update=session_update)
    response = await service.execute_sql_with_session_management(
        project_id=_PROJECT_ID,
        sql_query="SELECT 1",
        query_timeout_seconds=1,
    )

    assert response.success is False
    assert "timed out" in (response.error_message or "")
    assert engine.interrupted is True
    assert engine.disposed is True
    # The failed execution is surfaced on the session record.
    error_call = session_update.await_args
    assert error_call is not None
    assert error_call.kwargs["status"] == QuerySessionStatus.ERROR


@pytest.mark.asyncio
@patch("kontext.query.in_process_query_session_service.resolve_engine_for_session")
async def test_query_without_explicit_timeout_uses_default_guard(
    resolve_engine: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _HangingEngine()
    resolve_engine.side_effect = _resolve_engine_side_effect(engine)

    monkeypatch.setattr(QueryConstants, "DEFAULT_QUERY_TIMEOUT_SECONDS", 1, raising=True)

    session_update = AsyncMock(return_value=None)
    service = _make_service(session_update=session_update)
    response = await service.execute_sql_with_session_management(
        project_id=_PROJECT_ID,
        sql_query="SELECT 1",
    )

    assert response.success is False
    assert engine.interrupted is True
    assert engine.disposed is True


@pytest.mark.asyncio
@patch("kontext.query.in_process_query_session_service.resolve_engine_for_session")
async def test_happy_path_does_not_call_interrupt(resolve_engine: Any) -> None:
    table = DataTable(columns=[], rows=[], row_count=0)
    engine_interrupt = AsyncMock(return_value=None)
    engine = SimpleNamespace(
        connect=AsyncMock(),
        fetch_data_table=AsyncMock(return_value=table),
        interrupt=engine_interrupt,
        dispose=AsyncMock(),
        get_session_file_size=lambda: None,
    )
    resolve_engine.side_effect = _resolve_engine_side_effect(engine)

    session_update = AsyncMock(return_value=None)
    service = _make_service(session_update=session_update)
    response = await service.execute_sql_with_session_management(
        project_id=_PROJECT_ID,
        sql_query="SELECT 1",
        query_timeout_seconds=5,
    )

    assert response.success is True
    engine.dispose.assert_awaited_once()
    engine_interrupt.assert_not_awaited()
    success_call = session_update.await_args
    assert success_call is not None
    assert success_call.kwargs["status"] == QuerySessionStatus.ACTIVE
