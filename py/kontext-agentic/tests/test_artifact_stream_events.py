from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from kontext.agentic.artifact_stream_events import build_artifact_stream_events
from kontext.schema import (
    ArtifactAction,
    ArtifactEventData,
    ArtifactEventKind,
    ArtifactType,
    ChartResult,
    ChatSessionArtifactModel,
    CodeLanguage,
    DataRef,
    NotebookMutationResult,
    NotebookUpdateMetadataAction,
    NotebookUpdateMetadataActionPayload,
    PythonExecutionResult,
    PythonSavedTable,
    RunEvent,
    SqlExecutionResult,
    ToolCall,
    ToolCallResult,
)


def _title_action() -> ArtifactAction:
    return ArtifactAction(
        root=NotebookUpdateMetadataAction(
            sequence=1,
            action_type="updateMetadata",
            payload=NotebookUpdateMetadataActionPayload(var_field="title", value="Renamed"),
        )
    )


class _ChatSessionService:
    def __init__(self, artifact: ChatSessionArtifactModel) -> None:
        self.artifact = artifact

    async def list_artifacts(self, session_id: str) -> list[ChatSessionArtifactModel]:
        assert session_id == self.artifact.session_id
        return [self.artifact]


def _artifact_model(
    *,
    session_id: str,
    artifact_id: str,
    artifact_type: ArtifactType,
    title: str,
) -> ChatSessionArtifactModel:
    timestamp = datetime(2026, 5, 8, tzinfo=UTC)
    return ChatSessionArtifactModel(
        id=str(uuid.uuid4()),
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        title=title,
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_result", "artifact_type"),
    [
        (
            NotebookMutationResult(
                success=True,
                message="created",
                notebook_id=str(uuid.uuid4()),
            ),
            ArtifactType.NOTEBOOK,
        ),
        (
            ChartResult(
                success=True,
                message="updated",
                chart_id=str(uuid.uuid4()),
            ),
            ArtifactType.CHART,
        ),
        (
            SqlExecutionResult(
                success=True,
                message="queried",
                data_ref=DataRef(
                    data_id=str(uuid.uuid4()),
                    code="select 1",
                    language=CodeLanguage.SQL,
                ),
            ),
            ArtifactType.DATATABLE,
        ),
        (
            PythonExecutionResult(
                success=True,
                message="executed",
                notebook_id=str(uuid.uuid4()),
            ),
            ArtifactType.NOTEBOOK,
        ),
    ],
)
async def test_build_artifact_stream_events_supports_artifact_tool_results(
    tool_result,
    artifact_type,
) -> None:
    session_id = str(uuid.uuid4())
    artifact_id = (
        tool_result.notebook_id
        if hasattr(tool_result, "notebook_id")
        else tool_result.chart_id
        if hasattr(tool_result, "chart_id")
        else tool_result.data_ref.data_id
    )
    artifact = _artifact_model(
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        title="Artifact",
    )
    service = _ChatSessionService(artifact)

    events = await build_artifact_stream_events(
        session_id=session_id,
        tool_call=ToolCall(
            tool_call_id="tool-1",
            tool_name="tool",
            result=ToolCallResult(root=tool_result),
        ),
        chat_session_service=service,
        known_artifact_ids=set(),
    )

    assert len(events) == 1
    assert events[0].event_type == RunEvent.ARTIFACTEVENT
    assert events[0].event_data is not None
    artifact_event = events[0].event_data.root
    assert isinstance(artifact_event, ArtifactEventData)
    assert artifact_event.kind.value == "created"
    assert artifact_event.artifact.artifact_id == artifact_id
    assert artifact_event.artifact.artifact_type == artifact_type


@pytest.mark.asyncio
async def test_build_artifact_stream_events_marks_existing_artifacts_as_updated() -> None:
    session_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    artifact = _artifact_model(
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=ArtifactType.NOTEBOOK,
        title="Notebook",
    )
    service = _ChatSessionService(artifact)

    events = await build_artifact_stream_events(
        session_id=session_id,
        tool_call=ToolCall(
            tool_call_id="tool-2",
            tool_name="update_notebook",
            result=ToolCallResult(
                root=NotebookMutationResult(
                    success=True,
                    message="updated",
                    notebook_id=artifact_id,
                    actions=[_title_action()],
                )
            ),
        ),
        chat_session_service=service,
        known_artifact_ids={artifact_id},
    )

    assert len(events) == 1
    assert events[0].event_data is not None
    artifact_event = events[0].event_data.root
    assert isinstance(artifact_event, ArtifactEventData)
    assert artifact_event.kind.value == "updated"
    assert artifact_event.artifact.artifact_id == artifact_id


@pytest.mark.asyncio
async def test_build_artifact_stream_events_skips_updates_without_actions() -> None:
    """Read-only results must not refresh viewers of unchanged artifacts."""
    session_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    artifact = _artifact_model(
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=ArtifactType.CHART,
        title="Chart",
    )
    service = _ChatSessionService(artifact)

    events = await build_artifact_stream_events(
        session_id=session_id,
        tool_call=ToolCall(
            tool_call_id="tool-3",
            tool_name="get_chart",
            result=ToolCallResult(
                root=ChartResult(
                    success=True,
                    message=f"Successfully retrieved chart '{artifact_id}'",
                    chart_id=artifact_id,
                )
            ),
        ),
        chat_session_service=service,
        known_artifact_ids={artifact_id},
    )

    assert events == []


class _MultiArtifactChatSessionService:
    def __init__(self, artifacts: list[ChatSessionArtifactModel]) -> None:
        self.artifacts = artifacts

    async def list_artifacts(self, session_id: str) -> list[ChatSessionArtifactModel]:
        return [a for a in self.artifacts if a.session_id == session_id]


async def test_build_artifact_stream_events_emits_created_for_saved_tables() -> None:
    """``PythonExecutionResult.savedTables`` surface as CREATED artifact events."""
    session_id = str(uuid.uuid4())
    table_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    artifacts = [
        _artifact_model(
            session_id=session_id,
            artifact_id=table_id,
            artifact_type=ArtifactType.DATATABLE,
            title=f"Saved {index}",
        )
        for index, table_id in enumerate(table_ids)
    ]
    known: set[str] = set()

    events = await build_artifact_stream_events(
        session_id=session_id,
        tool_call=ToolCall(
            tool_call_id="tool-saved",
            tool_name="execute_python_script",
            result=ToolCallResult(
                root=PythonExecutionResult(
                    success=True,
                    message="executed",
                    saved_tables=[
                        PythonSavedTable(data_table_id=table_ids[0], title="Saved 0", row_count=2),
                        PythonSavedTable(data_table_id=table_ids[1], title="Saved 1", row_count=3),
                    ],
                )
            ),
        ),
        chat_session_service=_MultiArtifactChatSessionService(artifacts),
        known_artifact_ids=known,
    )

    assert len(events) == 2
    kinds: list[ArtifactEventKind] = []
    artifact_ids: list[str] = []
    for event in events:
        assert event.event_data is not None
        event_data = event.event_data.root
        assert isinstance(event_data, ArtifactEventData)
        kinds.append(event_data.kind)
        artifact_ids.append(event_data.artifact.artifact_id)

    assert all(kind == ArtifactEventKind.CREATED for kind in kinds)
    assert artifact_ids == table_ids
    assert known == set(table_ids)
