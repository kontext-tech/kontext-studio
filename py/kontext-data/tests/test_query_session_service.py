from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID

from kontext.data.query_session_service import QuerySessionDataService
from kontext.schema import CreateQuerySessionRequest, QueryEngineType


def test_create_session_infers_engine_type_from_catalog_connection() -> None:
    project_id = "c1658a20-3558-4f89-b719-9573ef5e271b"
    connection_id = "c5dcdeff-aba0-43e0-95a4-b60074a01381"
    service = QuerySessionDataService(project_id)

    class FakeResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeSession:
        def __init__(self):
            self.created = None

        def execute(self, stmt):
            sql = str(stmt)
            if "catalog_connections" in sql:
                return FakeResult("sqlserver_external")
            return FakeResult(None)

        def add(self, entity):
            self.created = entity

        def flush(self):
            return None

        def refresh(self, _entity):
            return None

        def expunge(self, _entity):
            return None

    fake_session = FakeSession()

    @contextmanager
    def fake_session_scope(*, commit: bool = True):
        _ = commit
        yield fake_session

    service._session_scope = fake_session_scope  # type: ignore[method-assign]

    session = service.create_session(
        CreateQuerySessionRequest(
            project_id=project_id,
            catalog_connection_id=connection_id,
            session_name="SQL Server session",
        ),
        user_id=None,
    )

    assert session.engine_type == QueryEngineType.SQLSERVER
    assert fake_session.created is not None
    assert fake_session.created.project_id == UUID(project_id)
