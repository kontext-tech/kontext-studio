"""Helpers for translating tool results into first-class artifact stream events."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from kontext.schema import (
    ArtifactEventData,
    ArtifactEventKind,
    ChartResult,
    ChatSessionArtifactModel,
    EventData,
    NotebookBlockResult,
    NotebookMultiBlockResult,
    NotebookMutationResult,
    PythonExecutionResult,
    RunEvent,
    SimpleRunEvent,
    SqlExecutionResult,
    ToolCall,
    ToolCallResult,
)

if TYPE_CHECKING:
    from collections.abc import MutableSet

logger = logging.getLogger(__name__)


class ArtifactSessionService(Protocol):
    """Narrow artifact-read port for this module.

    Deliberately kept minimal (not the full ``IChatSessionProtocol``) so test
    doubles and alternative chat persistence implementations only need to
    satisfy the single operation used here.
    """

    async def list_artifacts(self, session_id: str) -> list[ChatSessionArtifactModel]: ...


def _unwrap_tool_result(result: ToolCallResult | None) -> object | None:
    if result is None:
        return None
    return result.root if hasattr(result, "root") else result


def _extract_artifact_ids(result: ToolCallResult | None) -> list[str]:
    """Collect artifact ids referenced by a tool result (primary first).

    Python results may reference more than one artifact: the notebook when
    present, followed by any tables persisted via ``kontext.save_table``.
    """
    actual = _unwrap_tool_result(result)
    if actual is None or isinstance(actual, str):
        return []

    if isinstance(
        actual,
        NotebookMutationResult | NotebookBlockResult | NotebookMultiBlockResult,
    ):
        artifact_id = getattr(actual, "notebook_id", None)
        return [artifact_id] if artifact_id else []
    if isinstance(actual, ChartResult):
        artifact_id = getattr(actual, "chart_id", None)
        return [artifact_id] if artifact_id else []
    if isinstance(actual, SqlExecutionResult):
        data_ref = getattr(actual, "data_ref", None)
        artifact_id = getattr(data_ref, "data_id", None) if data_ref is not None else None
        return [artifact_id] if artifact_id else []
    if isinstance(actual, PythonExecutionResult):
        artifact_ids: list[str] = []
        notebook_id = getattr(actual, "notebook_id", None)
        if notebook_id:
            artifact_ids.append(notebook_id)
        for table in getattr(actual, "saved_tables", None) or []:
            data_table_id = getattr(table, "data_table_id", None)
            if data_table_id:
                artifact_ids.append(data_table_id)
        return artifact_ids
    return []


async def build_artifact_stream_events(
    *,
    session_id: str,
    tool_call: ToolCall,
    chat_session_service: ArtifactSessionService,
    known_artifact_ids: MutableSet[str],
) -> list[SimpleRunEvent]:
    """Translate a completed tool call into zero or more ArtifactEvent items."""
    artifact_ids = _extract_artifact_ids(tool_call.result)
    if not artifact_ids:
        return []

    actual = _unwrap_tool_result(tool_call.result)
    actions = (
        getattr(actual, "actions", None)
        if actual is not None and not isinstance(actual, str)
        else None
    )

    try:
        artifacts = await chat_session_service.list_artifacts(session_id)
    except Exception:
        logger.exception("Failed to load chat session artifacts for artifact stream event")
        return []

    events: list[SimpleRunEvent] = []
    for index, artifact_id in enumerate(dict.fromkeys(artifact_ids)):
        artifact = next(
            (entry for entry in artifacts if str(entry.artifact_id) == str(artifact_id)),
            None,
        )
        if artifact is None:
            logger.warning(
                "Skipping artifact stream event because artifact %s was not linked to chat session %s",
                artifact_id,
                session_id,
            )
            continue

        kind = (
            ArtifactEventKind.CREATED
            if artifact_id not in known_artifact_ids
            else ArtifactEventKind.UPDATED
        )
        known_artifact_ids.add(artifact_id)

        # Mutation actions belong to the primary artifact (e.g. the notebook a
        # tool updated); side artifacts such as saved tables carry none.
        artifact_actions = actions if index == 0 else None

        # UPDATED events must carry recorded mutation actions. Read-only tool
        # results (e.g. ``get_chart`` previews) and artifact relinks produce a
        # result with the artifact id but nothing changed server-side; emitting
        # them would bump viewers' refresh tokens and re-render artifacts that
        # did not change.
        if kind == ArtifactEventKind.UPDATED and not artifact_actions:
            continue

        events.append(
            SimpleRunEvent(
                event_type=RunEvent.ARTIFACTEVENT,
                event_data=EventData(
                    root=ArtifactEventData(
                        kind=kind,
                        artifact=ChatSessionArtifactModel.model_validate(artifact),
                        actions=artifact_actions or [],
                        source_tool_call_id=tool_call.tool_call_id,
                    )
                ),
            )
        )

    return events
