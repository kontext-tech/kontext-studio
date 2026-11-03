from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

from kontext.data.chat_session_service import (
    ChatSessionDataService,
    _attachment_context_to_response,
    _chat_session_to_response,
)
from kontext.data.models import ChatSession, ChatSessionArtifact, ChatSessionAttachmentContext
from kontext.schema import (
    ArtifactType,
    ChatAttachmentContext,
    ChatAttachmentContextFile,
    ChatAttachmentContextTable,
    CreateChatSessionRequest,
    FileFormatType,
    PythonExecutionApprovalMode,
    UpdateChatSessionRequest,
)


def test_get_session_resolved_model_config_coerces_string_session_id_to_uuid():
    service = ChatSessionDataService("c1658a20-3558-4f89-b719-9573ef5e271b")
    captured = {}

    class FakeResult:
        def scalar_one_or_none(self):
            return {"provider_model_name": "test-model"}

    class FakeSession:
        def execute(self, stmt):
            captured["stmt"] = stmt
            return FakeResult()

    @contextmanager
    def fake_session_scope(*, commit: bool = True):
        yield FakeSession()

    service._session_scope = fake_session_scope  # type: ignore[method-assign]

    result = service._get_session_resolved_model_config_sync("c5dcdeff-aba0-43e0-95a4-b60074a01381")

    assert result == {"provider_model_name": "test-model"}

    criteria = list(captured["stmt"]._where_criteria)
    session_id_clause = next(
        criterion for criterion in criteria if getattr(criterion.left, "name", None) == "id"
    )
    project_id_clause = next(
        criterion for criterion in criteria if getattr(criterion.left, "name", None) == "project_id"
    )

    assert isinstance(session_id_clause.right.value, UUID)
    assert isinstance(project_id_clause.right.value, UUID)


def test_chat_session_to_response_includes_python_execution_approval_mode():
    session = ChatSession(
        id="c5dcdeff-aba0-43e0-95a4-b60074a01381",
        project_id="c1658a20-3558-4f89-b719-9573ef5e271b",
        session_name="Session",
        python_execution_approval_mode="auto_approve",
        is_deleted=False,
    )

    model = _chat_session_to_response(session)

    assert model.python_execution_approval_mode == PythonExecutionApprovalMode.AUTOAPPROVE


def test_create_session_infers_engine_type_from_catalog_connection():
    project_id = "c1658a20-3558-4f89-b719-9573ef5e271b"
    connection_id = "c5dcdeff-aba0-43e0-95a4-b60074a01381"
    service = ChatSessionDataService(project_id)

    class FakeResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeSession:
        def __init__(self):
            self.created = None

        def execute(self, stmt):
            if "catalog_connections" in str(stmt):
                return FakeResult("oracle_external")
            return FakeResult(None)

        def add(self, entity):
            if entity.id is None:
                entity.id = uuid4()
            self.created = entity

        def flush(self):
            return None

        def expunge(self, _entity):
            return None

    @contextmanager
    def fake_session_scope(*, commit: bool = True):
        _ = commit
        yield FakeSession()

    service._session_scope = fake_session_scope  # type: ignore[method-assign]

    session = service._create_session_sync(
        CreateChatSessionRequest(
            project_id=project_id,
            session_name="Oracle chat",
            default_catalog_connection_id=connection_id,
        ),
        user_id=None,
    )

    assert session.engine_type == "Oracle"


def test_update_session_infers_engine_type_when_connection_changes():
    project_id = "c1658a20-3558-4f89-b719-9573ef5e271b"
    chat_session_id = "c5dcdeff-aba0-43e0-95a4-b60074a01381"
    connection_id = "8b86be1f-31d9-4d5f-9cd9-b174542fab6d"
    service = ChatSessionDataService(project_id)
    persisted = ChatSession(
        id=UUID(chat_session_id),
        project_id=UUID(project_id),
        session_name="Existing",
        engine_type="DuckDB",
        is_deleted=False,
    )

    class FakeResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeSession:
        def execute(self, stmt):
            if "catalog_connections" in str(stmt):
                return FakeResult("teradata_external")
            return FakeResult(persisted)

        def flush(self):
            return None

        def expunge(self, _entity):
            return None

    @contextmanager
    def fake_session_scope(*, commit: bool = True):
        _ = commit
        yield FakeSession()

    service._session_scope = fake_session_scope  # type: ignore[method-assign]

    updated = service._update_session_sync(
        chat_session_id,
        UpdateChatSessionRequest(default_catalog_connection_id=connection_id),
        user_id=None,
    )

    assert updated.engine_type == "Teradata"


def _artifact_upsert_service(existing: ChatSessionArtifact):
    service = ChatSessionDataService("c1658a20-3558-4f89-b719-9573ef5e271b")

    class FakeResult:
        def scalar_one_or_none(self):
            return existing

    class FakeSession:
        def execute(self, _stmt):
            return FakeResult()

        def add(self, entity):
            raise AssertionError("should not add a new artifact when one exists")

        def flush(self):
            return None

        def expunge(self, _entity):
            return None

    @contextmanager
    def fake_session_scope(*, commit: bool = True):
        _ = commit
        yield FakeSession()

    service._session_scope = fake_session_scope  # type: ignore[method-assign]
    return service


def test_upsert_artifact_preserves_existing_title_and_meta_when_none():
    session_id = uuid4()
    artifact_id = uuid4()
    existing = ChatSessionArtifact(
        id=uuid4(),
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=ArtifactType.DATATABLE.value,
        title="Transactions by type",
        meta={"sql": "SELECT 1"},
    )
    service = _artifact_upsert_service(existing)

    updated = service.upsert_artifact_sync(
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=ArtifactType.DATATABLE.value,
        title=None,
        meta=None,
    )

    assert updated.title == "Transactions by type"
    assert updated.meta == {"sql": "SELECT 1"}


def test_upsert_artifact_overwrites_title_and_meta_when_provided():
    session_id = uuid4()
    artifact_id = uuid4()
    existing = ChatSessionArtifact(
        id=uuid4(),
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=ArtifactType.DATATABLE.value,
        title="old",
        meta={"sql": "SELECT old"},
    )
    service = _artifact_upsert_service(existing)

    updated = service.upsert_artifact_sync(
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=ArtifactType.DATATABLE.value,
        title="new",
        meta={"sql": "SELECT new"},
    )

    assert updated.title == "new"
    assert updated.meta == {"sql": "SELECT new"}


def test_attachment_context_round_trips_through_data_service():
    project_id = "c1658a20-3558-4f89-b719-9573ef5e271b"
    chat_session_id = "c5dcdeff-aba0-43e0-95a4-b60074a01381"
    service = ChatSessionDataService(project_id)
    persisted_by_id: dict[UUID, ChatSessionAttachmentContext] = {}

    class FakeSession:
        def get(self, model, key):
            if model is ChatSessionAttachmentContext:
                return persisted_by_id.get(key)
            return None

        def add(self, entity):
            persisted_by_id[entity.chat_session_id] = entity

        def flush(self):
            return None

    @contextmanager
    def fake_session_scope(*, commit: bool = True):
        _ = commit
        yield FakeSession()

    service._session_scope = fake_session_scope  # type: ignore[method-assign]

    context = ChatAttachmentContext(
        upload_preparation_run_id="8b86be1f-31d9-4d5f-9cd9-b174542fab6d",
        internal_catalog_connection_id="ca723b78-0874-44c7-b15f-47a57b31bebb",
        files=[
            ChatAttachmentContextFile(
                file_id="8d7b4a5b-c7eb-44af-91da-7d80fca792e7",
                file_name="Financial Sample.xlsx",
                file_type=FileFormatType.EXCEL,
            )
        ],
        tables=[
            ChatAttachmentContextTable(
                file_id="8d7b4a5b-c7eb-44af-91da-7d80fca792e7",
                entity_id="6bb19f25-411f-469a-b953-b3992e8b1f8c",
                namespace_name="bronze",
                entity_name="Financial_Sample_Sheet1",
                row_count=700,
                column_names=["Segment", "Country", "Product"],
            )
        ],
    )

    saved = service._upsert_attachment_context_sync(chat_session_id, context)
    loaded = service._get_attachment_context_sync(chat_session_id)

    assert saved == context
    assert loaded == context
    record = persisted_by_id[UUID(chat_session_id)]
    assert _attachment_context_to_response(record) == context
