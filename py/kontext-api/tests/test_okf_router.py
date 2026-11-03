"""Tests for the OKF v0.2 export/import endpoints."""

from __future__ import annotations

import io
import tarfile
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from kontext.api.dependencies import AuthContext
from kontext.api.main import app
from kontext.api.routers.okf import CATALOG_READ_AUTH, CATALOG_WRITE_AUTH
from kontext.okf import OkfConcept, OkfConceptStore
from kontext.schema import (
    AccessLevel,
    ProjectConfiguration,
    ProjectModel,
    UserType,
    UserWithRolesModel,
)


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Ensure FastAPI dependency overrides never leak between tests."""
    yield
    app.dependency_overrides.clear()


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
    user = UserWithRolesModel(
        id=user_id,
        first_name="Test",
        last_name="User",
        user_type=UserType.USER,
        roles=[],
        permission_claims=[],
        project_roles={},
    )
    return AuthContext(project=project, user=user)


def test_export_returns_tar_gz_with_concept_markdown(monkeypatch, tmp_path):
    project_id = str(uuid.uuid4())
    store = OkfConceptStore(tmp_path / "okf")
    store.upsert_concepts(
        [
            OkfConcept(
                id="metrics/revenue",
                type="Metric",
                title="Revenue definition",
                description="Recognized revenue.",
                status="stable",
            ),
            OkfConcept(
                id="glossary/wau",
                type="Reference",
                title="WAU",
                description="Weekly active users.",
            ),
        ]
    )
    monkeypatch.setattr(
        "kontext.api.routers.okf.OkfConceptStore.for_project",
        lambda project_id: store,
    )
    app.dependency_overrides[CATALOG_READ_AUTH.dependency] = lambda: _mock_auth(project_id)

    client = TestClient(app)
    response = client.get("/catalog/okf/export", params={"projectId": project_id})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"
    assert "attachment" in response.headers["content-disposition"]

    # The body is a tar.gz; extract and confirm it contains the concept files
    # plus generated index.md files (OKF §8).
    buf = io.BytesIO(response.content)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        names = tar.getnames()
        concept_files = [n for n in names if n.endswith(".md") and not n.endswith("index.md")]
        assert len(concept_files) == 2, names
        assert any(n.endswith("bundle/index.md") for n in names), names
        # The root index declares the targeted OKF version (§12).
        index_member = next(n for n in names if n.endswith("bundle/index.md"))
        index_file = tar.extractfile(index_member)
        assert index_file is not None
        index_text = index_file.read().decode("utf-8")
        assert 'okf_version: "0.2"' in index_text


def test_import_validates_bundle_and_reports_concept_count(monkeypatch, tmp_path):
    project_id = str(uuid.uuid4())
    store = OkfConceptStore(tmp_path / "okf")
    # Build a minimal valid bundle: one concept markdown file.
    concept_md = "---\nid: glossary/test\ntype: Reference\ntitle: Test concept\n---\nBody text.\n"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="bundle/glossary/test.md")
        data = concept_md.encode("utf-8")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    buf.seek(0)

    monkeypatch.setattr(
        "kontext.api.routers.okf.OkfConceptStore.for_project",
        lambda project_id: store,
    )
    app.dependency_overrides[CATALOG_WRITE_AUTH.dependency] = lambda: _mock_auth(project_id)

    client = TestClient(app)
    response = client.post(
        "/catalog/okf/import",
        params={"projectId": project_id},
        files={"file": ("okf.tar.gz", buf, "application/gzip")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["projectId"] == project_id
    assert body["importedConceptCount"] == 1
    assert body["conceptIds"] == ["glossary/test"]
    assert body["conformanceWarnings"] == []
    assert store.get_concept("glossary/test") is not None


def test_import_surfaces_conformance_warnings(monkeypatch, tmp_path):
    """A structurally off bundle imports but reports §11 rule-3 warnings."""
    project_id = str(uuid.uuid4())
    store = OkfConceptStore(tmp_path / "okf")
    concept_md = "---\ntype: Reference\ntitle: Test\n---\nBody.\n"
    bad_log = "# Log\n\n## June 1\n* init\n"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in [
            ("bundle/glossary/test.md", concept_md),
            ("bundle/log.md", bad_log),
        ]:
            info = tarfile.TarInfo(name=name)
            data = content.encode("utf-8")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    buf.seek(0)

    monkeypatch.setattr(
        "kontext.api.routers.okf.OkfConceptStore.for_project",
        lambda project_id: store,
    )
    app.dependency_overrides[CATALOG_WRITE_AUTH.dependency] = lambda: _mock_auth(project_id)

    client = TestClient(app)
    response = client.post(
        "/catalog/okf/import",
        params={"projectId": project_id},
        files={"file": ("okf.tar.gz", buf, "application/gzip")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["importedConceptCount"] == 1
    assert any("log.md" in warning for warning in body["conformanceWarnings"])


def test_import_rejects_non_tar_gz(monkeypatch, tmp_path):
    project_id = str(uuid.uuid4())
    store = OkfConceptStore(tmp_path / "okf")
    monkeypatch.setattr(
        "kontext.api.routers.okf.OkfConceptStore.for_project",
        lambda project_id: store,
    )
    app.dependency_overrides[CATALOG_WRITE_AUTH.dependency] = lambda: _mock_auth(project_id)

    client = TestClient(app)
    response = client.post(
        "/catalog/okf/import",
        params={"projectId": project_id},
        files={"file": ("not-a-zip.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


class _FakeKnowledgeService:
    """In-memory knowledge service double for routing tests."""

    def __init__(self, concepts):
        self._concepts = {c.id: c for c in concepts}

    async def list_concepts(self):
        return list(self._concepts.values())

    async def search_concepts(self, query, limit=10):
        return [c for c in self._concepts.values() if query.lower() in c.title.lower()][:limit]

    async def get_concept(self, concept_id):
        return self._concepts.get(concept_id)

    async def list_proposals(self):
        return [c for c in self._concepts.values() if c.status in {"draft", "proposed"}]

    async def approve_concept(self, concept_id, *, approved_by):
        concept = self._concepts.get(concept_id)
        if concept is None:
            return None
        approved = concept.model_copy(update={"status": "stable"})
        self._concepts[concept_id] = approved
        return approved

    async def upsert_concept(self, concept):
        self._concepts[concept.id] = concept
        return concept

    async def delete_concept(self, concept_id):
        return self._concepts.pop(concept_id, None) is not None


def _patch_knowledge_service(monkeypatch, concepts):
    fake = _FakeKnowledgeService(concepts)

    async def _fake_service(auth_context):
        return fake

    monkeypatch.setattr("kontext.api.routers.okf._service", _fake_service)
    return fake


def test_list_and_search_concepts(monkeypatch):
    project_id = str(uuid.uuid4())
    _patch_knowledge_service(
        monkeypatch,
        [
            OkfConcept(id="metrics/revenue", type="Metric", title="Revenue definition"),
            OkfConcept(id="glossary/wau", type="Reference", title="Weekly Active Users"),
        ],
    )
    app.dependency_overrides[CATALOG_READ_AUTH.dependency] = lambda: _mock_auth(project_id)
    client = TestClient(app)

    listed = client.get("/catalog/okf/concepts", params={"projectId": project_id})
    assert listed.status_code == 200
    assert {c["id"] for c in listed.json()} == {"metrics/revenue", "glossary/wau"}

    searched = client.get(
        "/catalog/okf/concepts/search",
        params={"projectId": project_id, "query": "weekly"},
    )
    assert searched.status_code == 200
    assert [c["id"] for c in searched.json()] == ["glossary/wau"]


def test_get_unknown_concept_returns_404(monkeypatch):
    project_id = str(uuid.uuid4())
    _patch_knowledge_service(monkeypatch, [])
    app.dependency_overrides[CATALOG_READ_AUTH.dependency] = lambda: _mock_auth(project_id)
    client = TestClient(app)

    response = client.get(
        "/catalog/okf/concepts/missing/concept",
        params={"projectId": project_id},
    )
    assert response.status_code == 404


def test_proposal_approve_flow(monkeypatch):
    project_id = str(uuid.uuid4())
    _patch_knowledge_service(
        monkeypatch,
        [OkfConcept(id="concepts/wau", type="Metric", title="WAU", status="proposed")],
    )
    app.dependency_overrides[CATALOG_READ_AUTH.dependency] = lambda: _mock_auth(project_id)
    app.dependency_overrides[CATALOG_WRITE_AUTH.dependency] = lambda: _mock_auth(project_id)
    client = TestClient(app)

    proposals = client.get("/catalog/okf/proposals", params={"projectId": project_id})
    assert proposals.status_code == 200
    assert [c["id"] for c in proposals.json()] == ["concepts/wau"]

    approved = client.post(
        "/catalog/okf/proposals/concepts/wau/approve",
        params={"projectId": project_id},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "stable"
