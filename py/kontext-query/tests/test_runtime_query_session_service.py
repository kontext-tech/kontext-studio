from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from kontext.query.context import QueryAccessContext
from kontext.query.runtime_query_session_service import (
    AuthorizedRuntimeQuerySessionService,
)
from kontext.schema import (
    QueryEngineType,
    QueryResponse,
    QuerySessionModel,
    QuerySessionStatus,
)


def _access_context() -> QueryAccessContext:
    return QueryAccessContext(
        project_id=uuid4(),
        user_id=uuid4(),
        actor_label="User:test",
        effective_owner_id=uuid4(),
        project_scope=False,
    )


def _session(
    *,
    project_id: str,
    session_id: str | None = None,
    status: QuerySessionStatus = QuerySessionStatus.ACTIVE,
    engine_type: QueryEngineType = QueryEngineType.DUCKDB,
    catalog_connection_id: str | None = None,
    default_namespace: str | None = None,
    default_entity_id: str | None = None,
) -> QuerySessionModel:
    return QuerySessionModel.model_construct(
        id=session_id or str(uuid4()),
        project_id=project_id,
        owner_id=str(uuid4()),
        session_name="Session",
        status=status,
        engine_type=engine_type,
        catalog_connection_id=catalog_connection_id,
        default_namespace=default_namespace,
        default_entity_id=default_entity_id,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_get_or_create_session_reuses_compatible_session() -> None:
    access_context = _access_context()
    session_id = str(uuid4())
    connection_id = str(uuid4())
    entity_id = str(uuid4())
    session = _session(
        project_id=str(access_context.project_id),
        session_id=session_id,
        engine_type=QueryEngineType.SQLSERVER,
        catalog_connection_id=connection_id,
        default_namespace="sales",
        default_entity_id=entity_id,
    )
    data_service = MagicMock()
    data_service.get_session.return_value = session
    data_service.get_catalog_revision_async = AsyncMock(return_value=None)

    with patch(
        "kontext.query.runtime_query_session_service.QuerySessionDataService",
        return_value=data_service,
    ):
        service = AuthorizedRuntimeQuerySessionService(
            access_context=access_context,
            queue_client=MagicMock(),
        )

    with (
        patch(
            "kontext.query.runtime_query_session_service.create_query_session",
            new=AsyncMock(),
        ) as create_session_mock,
        patch(
            "kontext.query.runtime_query_session_service.initialize_session_sync",
            new=AsyncMock(),
        ) as init_mock,
    ):
        result = await service.get_or_create_session(
            project_id=access_context.project_id,
            session_id=session_id,
            catalog_connection_id=connection_id,
            default_namespace="sales",
            default_entity_id=entity_id,
            engine_type=QueryEngineType.SQLSERVER,
        )

    assert result == session_id
    create_session_mock.assert_not_awaited()
    init_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_or_create_session_repairs_broken_live_sql_session() -> None:
    access_context = _access_context()
    connection_id = str(uuid4())
    broken_session_id = str(uuid4())
    repaired_session_id = str(uuid4())
    broken_session = _session(
        project_id=str(access_context.project_id),
        session_id=broken_session_id,
        status=QuerySessionStatus.ACTIVE,
        engine_type=QueryEngineType.SQLSERVER,
        catalog_connection_id=None,
        default_namespace="sales",
    )
    repaired_session = _session(
        project_id=str(access_context.project_id),
        session_id=repaired_session_id,
        status=QuerySessionStatus.INITIALIZING,
        engine_type=QueryEngineType.SQLSERVER,
        catalog_connection_id=connection_id,
        default_namespace="sales",
    )
    data_service = MagicMock()
    data_service.get_session.side_effect = [broken_session, repaired_session]
    data_service.list_sessions_by_status.return_value = ([], 0)
    data_service.get_catalog_revision_async = AsyncMock(return_value=None)

    with patch(
        "kontext.query.runtime_query_session_service.QuerySessionDataService",
        return_value=data_service,
    ):
        service = AuthorizedRuntimeQuerySessionService(
            access_context=access_context,
            queue_client=MagicMock(),
        )

    with (
        patch(
            "kontext.query.runtime_query_session_service.create_query_session",
            new=AsyncMock(return_value=repaired_session),
        ) as create_session_mock,
        patch(
            "kontext.query.runtime_query_session_service.initialize_session_sync",
            new=AsyncMock(return_value=SimpleNamespace(success=True, error_message=None)),
        ) as init_mock,
    ):
        result = await service.get_or_create_session(
            project_id=access_context.project_id,
            session_id=broken_session_id,
            catalog_connection_id=connection_id,
            default_namespace="sales",
            session_name="Agent Session",
            engine_type=QueryEngineType.SQLSERVER,
        )

    assert result == repaired_session_id
    create_session_mock.assert_awaited_once()
    init_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_sql_with_session_management_uses_canonical_execution_path() -> None:
    access_context = _access_context()
    data_service = MagicMock()

    with patch(
        "kontext.query.runtime_query_session_service.QuerySessionDataService",
        return_value=data_service,
    ):
        service = AuthorizedRuntimeQuerySessionService(
            access_context=access_context,
            queue_client=MagicMock(),
        )

    expected_response = QueryResponse(
        success=True,
        data_id="550e8400-e29b-41d4-a716-446655440099",
    )

    with (
        patch.object(
            service,
            "get_or_create_session",
            new=AsyncMock(return_value="550e8400-e29b-41d4-a716-446655440000"),
        ),
        patch(
            "kontext.query.runtime_query_session_service.execute_query_sync",
            new=AsyncMock(return_value=expected_response),
        ) as execute_mock,
    ):
        response = await service.execute_sql_with_session_management(
            project_id=access_context.project_id,
            sql_query="SELECT 1",
            chat_session_id="550e8400-e29b-41d4-a716-446655440001",
            parent_run_id="550e8400-e29b-41d4-a716-446655440002",
            store_result_as_resource=True,
        )

    assert response is expected_response
    assert execute_mock.await_args is not None
    execute_request = execute_mock.await_args.kwargs["request"]
    assert execute_request.chat_session_id == "550e8400-e29b-41d4-a716-446655440001"
    assert execute_request.parent_run_id == "550e8400-e29b-41d4-a716-446655440002"
    assert execute_request.session_id == "550e8400-e29b-41d4-a716-446655440000"
