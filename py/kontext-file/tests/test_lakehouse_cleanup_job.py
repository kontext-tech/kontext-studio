from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from kontext.file.jobs.lakehouse_cleanup_job import (
    LakehouseCleanupJob,
    LakehouseCleanupParams,
)


@pytest.mark.asyncio
async def test_cleanup_job_uses_single_catalog_refresh_path():
    expected_project_id = str(uuid4())
    file_id = str(uuid4())
    invalidated_session_id = uuid4()

    class FakeCatalogService:
        async def remove_file_entities(self, received_file_id: str):
            assert received_file_id == file_id
            return ["entity-1"]

        async def ensure_default_internal_connection(self):
            return SimpleNamespace(id="internal-connection")

        async def list_entities(self, *, connection_id=None, namespace_name=None):
            assert connection_id == "internal-connection"
            assert namespace_name is None
            return [
                SimpleNamespace(id="remaining-1"),
                SimpleNamespace(id="remaining-2"),
            ]

        async def sync_connection(self, connection_id: str):
            raise AssertionError(f"sync_connection should not be called again: {connection_id}")

    class FakeQuerySessionService:
        async def invalidate_sessions_for_catalog_connection(
            self, project_id, connection_id, *, reason
        ):
            assert project_id == expected_project_id
            assert connection_id == "internal-connection"
            assert reason == "Lakehouse tables changed"
            return [invalidated_session_id]

    fake_context = SimpleNamespace(
        get_catalog_service=lambda: FakeCatalogService(),
        get_query_session_service=lambda: FakeQuerySessionService(),
    )

    result = await LakehouseCleanupJob().execute_job(
        fake_context,
        LakehouseCleanupParams(project_id=expected_project_id, file_id=file_id),
    )

    assert result.success is True
    assert result.data == {
        "deleted_entity_ids": ["entity-1"],
        "entity_count": 2,
        "invalidated_session_ids": [str(invalidated_session_id)],
    }
