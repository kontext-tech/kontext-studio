"""Tests for provenance flattening on persisted artifact documents."""

from __future__ import annotations

from uuid import uuid4

from kontext.common.artifacts.provenance import (
    apply_chart_provenance,
    apply_inline_data_provenance,
)
from kontext.common.jobs.trigger_actor import agent_actor
from kontext.schema import (
    ArtifactOrigin,
    ArtifactProvenance,
    ChartConfig,
    ChartDocument,
    ChartDocumentMetadata,
    InlineData,
)

_SESSION_ID = str(uuid4())


def _provenance() -> ArtifactProvenance:
    return ArtifactProvenance(
        origin=ArtifactOrigin.AGENTPYTHON,
        created_by=agent_actor("python_tool"),
        execution_run_id="56559c93-f6f0-4dbb-b6dc-39e77421b81a",
        chat_session_id=_SESSION_ID,
        identity_key="a" * 64,
    )


def test_inline_data_provenance_flattens_fields() -> None:
    inline_data = InlineData(title="t")
    apply_inline_data_provenance(inline_data, provenance=_provenance())

    metadata = inline_data.metadata
    assert metadata is not None
    assert metadata.origin == ArtifactOrigin.AGENTPYTHON
    assert metadata.created_by_type == "Agent"
    assert metadata.created_by_id == "python_tool"
    assert metadata.execution_run_id == "56559c93-f6f0-4dbb-b6dc-39e77421b81a"
    assert metadata.identity_key == "a" * 64
    assert metadata.created_at is not None


def test_chart_provenance_flattens_fields() -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    chart = ChartDocument(
        name="chart",
        config=ChartConfig.model_validate(
            {
                "chartType": "line",
                "title": "Chart",
                "xField": "x",
                "yField": "y",
                "height": 300,
            }
        ),
        metadata=ChartDocumentMetadata(created_at=now, modified_at=now, version="1.0.0"),
    )
    apply_chart_provenance(chart, provenance=_provenance())

    metadata = chart.metadata
    assert metadata is not None
    assert metadata.origin == ArtifactOrigin.AGENTPYTHON
    assert metadata.created_by_type == "Agent"
    assert metadata.created_by_id == "python_tool"
    assert metadata.execution_run_id == "56559c93-f6f0-4dbb-b6dc-39e77421b81a"
    assert metadata.identity_key == "a" * 64


def test_inline_data_provenance_keeps_adjacent_facts_unduplicated() -> None:
    inline_data = InlineData(title="t")
    apply_inline_data_provenance(
        inline_data,
        sql="SELECT 1",
        chat_session_id=_SESSION_ID,
        provenance=_provenance(),
    )

    metadata = inline_data.metadata
    assert metadata is not None
    assert metadata.sql == "SELECT 1"
    # Adjacent facts stay descriptor-level: the flatten never duplicates the
    # chat session into the provenance block.
    assert metadata.chat_session_id == _SESSION_ID


def test_provenance_from_document_metadata_roundtrips() -> None:
    """Reconstruction mirrors the flattened fields (record-level stamping)."""
    from kontext.common.artifacts.provenance import provenance_from_document_metadata

    inline_data = InlineData(title="t")
    source = _provenance()
    apply_inline_data_provenance(inline_data, chat_session_id=_SESSION_ID, provenance=source)

    reconstructed = provenance_from_document_metadata(inline_data.metadata)

    assert reconstructed is not None
    assert reconstructed.origin == source.origin
    assert source.created_by is not None
    assert reconstructed.created_by is not None
    assert reconstructed.created_by.type == source.created_by.type
    assert reconstructed.created_by.id == source.created_by.id
    assert reconstructed.execution_run_id == source.execution_run_id
    assert reconstructed.chat_session_id == _SESSION_ID
    assert reconstructed.identity_key == source.identity_key


def test_provenance_from_document_metadata_returns_none_without_origin() -> None:
    from kontext.common.artifacts.provenance import provenance_from_document_metadata

    assert provenance_from_document_metadata(None) is None
    assert provenance_from_document_metadata(InlineData(title="t").metadata) is None
