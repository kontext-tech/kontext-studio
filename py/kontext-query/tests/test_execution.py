from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from kontext.common.messaging import IQueueClient, QueueMessage
from kontext.query.execution import (
    _create_query_execution_run,
    _upsert_query_execution_context,
)
from kontext.schema import (
    QueryEngineType,
    QueryExecRequest,
    QuerySessionModel,
    QuerySessionStatus,
)


class _QueueClientStub:
    def __init__(self) -> None:
        self.send_message = AsyncMock(return_value="message-id")

    def receive_messages(
        self, max_messages: int, visibility_timeout: int
    ) -> AsyncIterator[QueueMessage]:
        _ = (max_messages, visibility_timeout)

        async def _empty() -> AsyncIterator[QueueMessage]:
            if False:
                yield QueueMessage(message_id="", body="", receipt_handle="")

        return _empty()

    async def delete_message(self, message_id: str, receipt_handle: str) -> None:
        _ = (message_id, receipt_handle)

    async def update_message(
        self, message_id: str, receipt_handle: str, visibility_timeout: int
    ) -> str:
        _ = (message_id, receipt_handle, visibility_timeout)
        return "updated"

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_upsert_query_execution_context_stores_chat_and_parent_linkage() -> None:
    project_id = uuid4()
    job_run_id = uuid4()
    parent_run_id = uuid4()
    root_run_id = uuid4()
    chat_session_id = str(uuid4())
    context_service = SimpleNamespace(
        get_by_run_id_async=AsyncMock(return_value=SimpleNamespace(root_run_id=root_run_id)),
        upsert_context_async=AsyncMock(),
    )

    with patch(
        "kontext.query.execution.ExecutionRunContextDataService",
        return_value=context_service,
    ):
        await _upsert_query_execution_context(
            project_id=project_id,
            job_run_id=job_run_id,
            chat_session_id=chat_session_id,
            parent_run_id=str(parent_run_id),
        )

    context_service.get_by_run_id_async.assert_awaited_once_with(str(parent_run_id))
    context_service.upsert_context_async.assert_awaited_once_with(
        run_id=job_run_id,
        chat_session_id=chat_session_id,
        parent_run_id=str(parent_run_id),
        root_run_id=root_run_id,
    )


@pytest.mark.asyncio
async def test_upsert_query_execution_context_falls_back_to_parent_as_root() -> None:
    project_id = uuid4()
    job_run_id = uuid4()
    parent_run_id = uuid4()
    context_service = SimpleNamespace(
        get_by_run_id_async=AsyncMock(return_value=None),
        upsert_context_async=AsyncMock(),
    )

    with patch(
        "kontext.query.execution.ExecutionRunContextDataService",
        return_value=context_service,
    ):
        await _upsert_query_execution_context(
            project_id=project_id,
            job_run_id=job_run_id,
            chat_session_id=None,
            parent_run_id=str(parent_run_id),
        )

    context_service.upsert_context_async.assert_awaited_once_with(
        run_id=job_run_id,
        chat_session_id=None,
        parent_run_id=str(parent_run_id),
        root_run_id=parent_run_id,
    )


@pytest.mark.asyncio
async def test_create_query_execution_run_includes_session_scope() -> None:
    project_id = uuid4()
    user_id = uuid4()
    session_id = uuid4()
    catalog_connection_id = uuid4()
    default_entity_id = uuid4()
    queue_client = cast(IQueueClient, _QueueClientStub())
    created_job = SimpleNamespace(id=uuid4())
    created_run = SimpleNamespace(id=uuid4())
    job_service = SimpleNamespace(
        get_or_create_job_for_owner_async=AsyncMock(return_value=created_job)
    )
    job_run_service = SimpleNamespace(create_run_async=AsyncMock(return_value=created_run))
    message = SimpleNamespace(to_json=lambda: '{"ok":true}')

    with (
        patch("kontext.data.JobDataService", return_value=job_service),
        patch("kontext.jobs.job_run_dispatch.JobRunDataService", return_value=job_run_service),
        patch("kontext.jobs.dispatch.build_job_execution_message", return_value=message),
        patch("kontext.query.execution._upsert_query_execution_context", new=AsyncMock()),
    ):
        await _create_query_execution_run(
            request=QueryExecRequest(
                project_id=str(project_id),
                session_id=str(session_id),
                sql_query="SELECT 1",
                query_timeout_seconds=30,
                store_result_as_resource=False,
            ),
            project_id=project_id,
            session=QuerySessionModel.model_construct(
                id=str(session_id),
                session_name="Session",
                project_id=str(project_id),
                catalog_connection_id=str(catalog_connection_id),
                default_namespace="sales",
                default_entity_id=str(default_entity_id),
                engine_type=QueryEngineType.SQLSERVER,
                status=QuerySessionStatus.ACTIVE,
                created_at=datetime.now(UTC),
            ),
            engine_type=QueryEngineType.SQLSERVER.value,
            user_id=user_id,
            actor_label=None,
            queue_client=queue_client,
        )

    create_run_kwargs = job_run_service.create_run_async.await_args.kwargs
    payload = json.loads(create_run_kwargs["parameters"])
    assert payload["catalogConnectionId"] == str(catalog_connection_id)
    assert payload["defaultNamespace"] == "sales"
    assert payload["defaultEntityId"] == str(default_entity_id)
    assert payload["engineType"] == QueryEngineType.SQLSERVER.value
