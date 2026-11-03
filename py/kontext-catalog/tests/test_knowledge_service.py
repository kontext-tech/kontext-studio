"""Tests for the durable OKF knowledge curation service."""

from __future__ import annotations

import uuid

import pytest

from kontext.catalog.indexing.embedding import LocalHashEmbedding
from kontext.catalog.indexing.lancedb_index import LanceDBKnowledgeIndex
from kontext.catalog.knowledge_service import (
    ACTIVE_STATUS,
    PROPOSED_STATUS,
    OKFKnowledgeService,
)
from kontext.okf import OkfConceptStore
from kontext.schema import OkfConcept


@pytest.fixture
def service(tmp_path, monkeypatch):
    store = OkfConceptStore(tmp_path / "okf")
    monkeypatch.setattr(
        "kontext.okf.store.OkfConceptStore.for_project",
        classmethod(lambda cls, project_id: store),
    )
    svc = OKFKnowledgeService(str(uuid.uuid4()))
    # Point the index at a temp vector dir so no real project storage is touched.
    svc._index_service._knowledge_index = LanceDBKnowledgeIndex(
        str(tmp_path / "vector"),
        embedding_provider=LocalHashEmbedding(),
    )
    return svc


@pytest.mark.asyncio
async def test_upsert_and_get_concept(service):
    concept = OkfConcept(id="metrics/revenue", type="Metric", title="Revenue")
    saved = await service.upsert_concept(concept)
    assert saved.id == "metrics/revenue"
    fetched = await service.get_concept("metrics/revenue")
    assert fetched is not None
    assert fetched.title == "Revenue"


@pytest.mark.asyncio
async def test_propose_creates_hidden_proposal_then_approve_activates(service):
    draft = OkfConcept(id="", type="Metric", title="Weekly Active Users", body="WAU = ...")
    proposal = await service.propose_concept(
        draft=draft, proposed_by="agent", chat_session_id="chat-1"
    )
    assert proposal.status == PROPOSED_STATUS
    assert proposal.attestation is not None
    assert proposal.attestation.generated is not None
    assert proposal.attestation.generated.by == "agent"

    proposals = await service.list_proposals()
    assert [p.id for p in proposals] == [proposal.id]

    # A proposal must not surface through retrieval until approved.
    hidden = await service.search_concepts("Weekly Active Users")
    assert all(c.id != proposal.id for c in hidden)

    approved = await service.approve_concept(proposal.id, approved_by="User:abc")
    assert approved is not None
    assert approved.status == ACTIVE_STATUS
    assert approved.attestation is not None
    assert approved.attestation.verified
    # "User:<id>" is normalized to the OKF ``human:<id>`` actor convention.
    assert approved.attestation.verified[0].by == "human:abc"

    assert await service.list_proposals() == []


@pytest.mark.asyncio
async def test_delete_concept_removes_from_store(service):
    concept = OkfConcept(id="notes/tmp", type="Note", title="Temporary")
    await service.upsert_concept(concept)
    assert await service.delete_concept("notes/tmp") is True
    assert await service.get_concept("notes/tmp") is None
    assert await service.delete_concept("notes/tmp") is False
