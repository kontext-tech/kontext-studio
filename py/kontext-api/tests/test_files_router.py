from __future__ import annotations

import uuid
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from kontext.api.dependencies import AuthContext
from kontext.api.main import app
from kontext.api.routers.files import FILE_CREATE_AUTH, FILE_READ_AUTH, FILE_UPDATE_AUTH
from kontext.common.jobs.trigger_actor import notebook_actor
from kontext.common.pagination import PaginatedResult
from kontext.schema import (
    AccessLevel,
    ArtifactOrigin,
    ArtifactProvenance,
    FileFormatType,
    ProjectConfiguration,
    ProjectModel,
    PythonExecutionMode,
    PythonExecutionResult,
)


def _mock_auth(project_id: str) -> AuthContext:
    user_id = str(uuid.uuid4())
    project = ProjectModel(
        access_level=AccessLevel.PRIVATE,
        date_created=datetime.now(UTC),
        id=project_id,
        project_name="Test Project",
        project_code="TEST",
        owner_id=str(uuid.uuid4()),
        is_deleted=False,
        configuration=ProjectConfiguration(
            allowed_file_types=[],
            max_file_bytes_size=0,
            total_storage_allocation_bytes=0,
            features=[],
        ),
    )
    return AuthContext(
        user=MagicMock(id=user_id),
        project=project,
        resource=object(),
    )


def test_execute_notebook_python_block_route_uses_shared_service(monkeypatch):
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    block_id = str(uuid.uuid4())
    recorded: dict[str, object] = {}
    auth_context = _mock_auth(project_id)

    class FakeNotebookPythonExecutionService:
        def __init__(
            self,
            *,
            file_service,
            python_execution_service=None,
            logger_=None,
        ):
            recorded["file_service"] = file_service
            recorded["python_execution_service"] = python_execution_service
            recorded["logger"] = logger_

        async def execute_notebook_code_async(self, **kwargs):
            recorded["kwargs"] = kwargs
            return PythonExecutionResult(
                success=True,
                message="ok",
                notebook_id=kwargs["notebook_id"],
                execution_run_id="run-route",
                execution_mode=PythonExecutionMode.PERSISTED,
                outputs=[],
            )

    fake_file_service = object()

    def fake_get_file_service(pid):
        recorded["project_id"] = pid
        return fake_file_service

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        fake_get_file_service,
    )
    monkeypatch.setattr(
        "kontext.api.routers.files.NotebookPythonExecutionService",
        FakeNotebookPythonExecutionService,
    )

    app.dependency_overrides[FILE_UPDATE_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.post(
        f"/file/{file_id}/notebook/blocks/{block_id}/execute-python",
        params={"projectId": project_id},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["notebookId"] == file_id
    assert body["executionRunId"] == "run-route"
    assert body["executionMode"] == "persisted"
    assert recorded["project_id"] == uuid.UUID(project_id)
    assert recorded["kwargs"] == {
        "project_id": project_id,
        "notebook_id": file_id,
        "block_id": block_id,
        "code_override": None,
        "persist_notebook_state": True,
        "owner_id": auth_context.user_id,
        "triggered_by": notebook_actor(file_id),
        "run_id": None,
    }


def test_execute_notebook_python_block_route_passes_code_override_for_draft_runs(
    monkeypatch,
):
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    block_id = str(uuid.uuid4())
    recorded: dict[str, object] = {}

    class FakeNotebookPythonExecutionService:
        def __init__(
            self,
            *,
            file_service,
            python_execution_service=None,
            logger_=None,
        ):
            recorded["file_service"] = file_service

        async def execute_notebook_code_async(self, **kwargs):
            recorded["kwargs"] = kwargs
            return PythonExecutionResult(
                success=True,
                message="ok",
                notebook_id=kwargs["notebook_id"],
                execution_run_id="run-draft-route",
                execution_mode=PythonExecutionMode.DRAFT,
                outputs=[],
            )

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        lambda pid: object(),
    )
    monkeypatch.setattr(
        "kontext.api.routers.files.NotebookPythonExecutionService",
        FakeNotebookPythonExecutionService,
    )

    auth_context = _mock_auth(project_id)
    app.dependency_overrides[FILE_UPDATE_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.post(
        f"/file/{file_id}/notebook/blocks/{block_id}/execute-python",
        params={"projectId": project_id},
        json={"codeOverride": "print('draft')"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["executionRunId"] == "run-draft-route"
    assert body["executionMode"] == "draft"
    assert recorded["kwargs"] == {
        "project_id": project_id,
        "notebook_id": file_id,
        "block_id": block_id,
        "code_override": "print('draft')",
        "persist_notebook_state": False,
        "owner_id": auth_context.user_id,
        "triggered_by": notebook_actor(file_id),
        "run_id": None,
    }


def test_execute_notebook_python_block_route_forwards_client_run_id(monkeypatch):
    """A client-supplied runId lets the caller cancel deterministically."""
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    block_id = str(uuid.uuid4())
    client_run_id = str(uuid.uuid4())
    recorded: dict[str, object] = {}

    class FakeNotebookPythonExecutionService:
        def __init__(self, *, file_service, python_execution_service=None, logger_=None):
            recorded["file_service"] = file_service

        async def execute_notebook_code_async(self, **kwargs):
            recorded["kwargs"] = kwargs
            return PythonExecutionResult(
                success=True,
                message="ok",
                notebook_id=kwargs["notebook_id"],
                execution_run_id=str(kwargs["run_id"]),
                execution_mode=PythonExecutionMode.PERSISTED,
                outputs=[],
            )

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        lambda pid: object(),
    )
    monkeypatch.setattr(
        "kontext.api.routers.files.NotebookPythonExecutionService",
        FakeNotebookPythonExecutionService,
    )

    auth_context = _mock_auth(project_id)
    app.dependency_overrides[FILE_UPDATE_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.post(
        f"/file/{file_id}/notebook/blocks/{block_id}/execute-python",
        params={"projectId": project_id},
        json={"runId": client_run_id},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    forwarded_kwargs = recorded["kwargs"]
    assert isinstance(forwarded_kwargs, dict)
    assert forwarded_kwargs["run_id"] == uuid.UUID(client_run_id)
    assert response.json()["executionRunId"] == client_run_id


def test_list_files_route_forwards_include_system_prefixes(monkeypatch):
    project_id = str(uuid.uuid4())
    recorded: dict[str, dict[str, object]] = {}
    auth_context = _mock_auth(project_id)

    class FakeFileService:
        async def list_files(self, **kwargs):
            recorded["kwargs"] = kwargs
            return PaginatedResult(items=[], total_count=0, page=1, page_size=10)

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        lambda pid: FakeFileService(),
    )

    app.dependency_overrides[FILE_READ_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.get(
        "/file",
        params={
            "projectId": project_id,
            "prefix": "",
            "includeSystemPrefixes": "false",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert recorded["kwargs"].get("include_system_prefixes") is False


def test_check_file_exists_returns_true_when_present(monkeypatch):
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    auth_context = _mock_auth(project_id)
    auth_context.resource = None

    class FakeFileService:
        async def exists_by_id(self, *, project_id, file_id):
            return True

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        lambda pid: FakeFileService(),
    )

    app.dependency_overrides[FILE_READ_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.get(
        f"/file/{file_id}/exists",
        params={"projectId": project_id},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() is True


def test_check_file_exists_surfaces_lookup_errors(monkeypatch):
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    auth_context = _mock_auth(project_id)
    auth_context.resource = None

    class FakeFileService:
        async def exists_by_id(self, *, project_id, file_id):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        lambda pid: FakeFileService(),
    )

    app.dependency_overrides[FILE_READ_AUTH.dependency] = lambda: auth_context

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        f"/file/{file_id}/exists",
        params={"projectId": project_id},
    )

    app.dependency_overrides.clear()

    # A lookup failure is not "does not exist"; it must not be a 200 false.
    # Unhandled failures now flow to the central problem+json 500 handler.
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    payload = response.json()
    assert payload["type"] == "InternalServerError"
    assert payload["status"] == 500


def test_download_file_declares_verified_content_length(monkeypatch):
    """A stale DB row size must not lie about the response body length.

    Regression: the download response declared Content-Length from the file
    record while agent tool calls were concurrently persisting into the same
    storage object, producing browser ERR_CONTENT_LENGTH_MISMATCH aborts (and
    empty notebook viewers).
    """
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    auth_context = _mock_auth(project_id)
    auth_context.resource = None

    stale_record = SimpleNamespace(
        id=file_id,
        name="notebook.kontext",
        uri="file:///tmp/notebook.kontext",
        size=6223,
        content_type="application/json",
    )
    body = b'{"title": "replaced while download ran"}'

    class FakeFileService:
        async def get_file_for_download(self, _file_id):
            return stale_record

        async def download_file_stream(self, _uri):
            return BytesIO(body)

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        lambda pid: FakeFileService(),
    )

    app.dependency_overrides[FILE_READ_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.get(
        f"/file/{file_id}/download",
        params={"projectId": project_id},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-length"] == str(len(body))
    assert response.content == body


def test_download_file_range_serves_verified_length_from_actual_bytes(monkeypatch):
    """A short range read must not declare the requested length."""
    project_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    auth_context = _mock_auth(project_id)
    auth_context.resource = None

    stale_record = SimpleNamespace(
        id=file_id,
        name="notebook.kontext",
        uri="file:///tmp/notebook.kontext",
        size=6223,
        content_type="application/json",
    )
    body = b"partial"

    class FakeFileService:
        async def get_file_for_download(self, _file_id):
            return stale_record

        async def download_file_range(self, _uri, _offset, _length):
            return BytesIO(body)

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        lambda pid: FakeFileService(),
    )

    app.dependency_overrides[FILE_READ_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.get(
        f"/file/{file_id}/download",
        params={"projectId": project_id},
        headers={"Range": "bytes=0-6222"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 206
    assert response.headers["content-length"] == str(len(body))
    assert response.headers["content-range"] == f"bytes 0-{len(body) - 1}/6223"
    assert response.content == body


def test_upload_file_stamps_upload_provenance(monkeypatch):
    """Uploads are stamped at the route: origin=upload, actor=requester."""
    project_id = str(uuid.uuid4())
    auth_context = _mock_auth(project_id)
    recorded: dict[str, object] = {}

    class FakeFileService:
        async def upload_single_file(self, **kwargs):
            recorded.update(kwargs)
            return SimpleNamespace(
                id=uuid.uuid4(),
                project_id=project_id,
                name="data.csv",
                prefix="",
                uri=f"projects/{project_id}/data.csv",
                file_type=FileFormatType.TEXT,
                content_type="text/csv",
                size=8,
                schema_definition=None,
                statistics_data=None,
                column_count=None,
                row_count=None,
                last_schema_update=None,
                last_stats_update=None,
                owner_id=uuid.UUID(str(auth_context.user_id)),
                date_created=datetime.now(UTC),
                modified_by_user_id=None,
                date_modified=None,
                is_deleted=False,
                date_deleted=None,
                provenance=None,
            )

    monkeypatch.setattr(
        "kontext.api.routers.files.create_file_service",
        lambda pid, queue=None: FakeFileService(),
    )
    app.dependency_overrides[FILE_CREATE_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.post(
        "/file/upload",
        params={"projectId": project_id},
        files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201, response.text
    provenance = recorded["provenance"]
    assert isinstance(provenance, ArtifactProvenance)
    assert provenance.origin == ArtifactOrigin.UPLOAD
    assert provenance.created_by is not None
    assert str(provenance.created_by.id) == str(auth_context.user_id)
    # The shared service also receives the actor used for job attribution.
    assert recorded["triggered_by"] == auth_context.trigger_actor
