"""Framework-neutral artifact helpers backed by the shared session store."""

from __future__ import annotations

import logging
from typing import Any

from kontext.agent.shared_session_store import (
    SharedSessionStore,
)
from kontext.common.protocols import IChatSessionProtocol
from kontext.schema import ArtifactProvenance, ArtifactType

logger = logging.getLogger(__name__)


def add_artifact_to_state(
    session_state: dict[str, Any] | None,
    artifact_id: str,
    artifact_type: ArtifactType,
    title: str,
) -> None:
    """Add or update a durable artifact descriptor in shared session state."""
    store = SharedSessionStore.from_session_state(session_state)
    if store is None:
        return
    store.upsert_artifact_descriptor(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        title=title,
    )


async def link_artifact_to_session(
    project_id: str,
    session_id: str | None,
    artifact_id: str,
    artifact_type: ArtifactType,
    title: str | None = None,
    meta: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    chat_session_service: IChatSessionProtocol | None = None,
    register_shared_descriptor: bool = False,
    provenance: ArtifactProvenance | None = None,
) -> bool:
    """Persist an artifact link for a chat session and optionally register shared metadata.

    ``provenance`` is embedded into the persisted artifact meta (``meta["provenance"]``)
    so artifact surfaces can render origin/actor badges without re-resolving result
    envelopes.
    """
    if provenance is not None:
        meta = {
            **(meta or {}),
            "provenance": provenance.model_dump(by_alias=True, exclude_none=True),
        }
    if not project_id:
        logger.warning("project_id is missing, skipping artifact linking.")
        return False

    if register_shared_descriptor:
        add_artifact_to_state(
            session_state=session_state,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title or "Untitled",
        )

    if not session_id or not chat_session_service:
        return False

    from contextlib import suppress

    with suppress(Exception):
        # Pass title/meta through unchanged: the persistence layer treats
        # ``None`` as "keep the existing value", so a secondary link cannot
        # clobber a descriptive title or provenance recorded at creation.
        await chat_session_service.upsert_artifact(
            session_id=session_id,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title,
            meta=meta,
        )
        return True

    return False
