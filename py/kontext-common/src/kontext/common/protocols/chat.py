"""Chat session contracts."""

from __future__ import annotations

from typing import Any, Protocol

from kontext.schema import (
    ArtifactType,
    ChatSessionArtifactModel,
    ChatSessionModel,
    CreateChatSessionRequest,
    UpdateChatSessionRequest,
)


class IChatSessionProtocol(Protocol):
    """Protocol defining the interface for chat session persistence."""

    async def create_session(
        self, request: CreateChatSessionRequest, user_id: str | None
    ) -> ChatSessionModel: ...

    async def get_session(self, session_id: str) -> ChatSessionModel | None: ...

    async def update_session(
        self, session_id: str, request: UpdateChatSessionRequest, user_id: str | None
    ) -> ChatSessionModel: ...

    async def delete_session(self, session_id: str, user_id: str | None) -> None: ...

    async def list_artifacts(self, session_id: str) -> list[ChatSessionArtifactModel]: ...

    async def add_artifact(
        self, session_id: str, artifact: ChatSessionArtifactModel
    ) -> ChatSessionArtifactModel: ...

    async def upsert_artifact(
        self,
        session_id: str,
        artifact_id: str,
        artifact_type: ArtifactType,
        title: str | None,
        meta: dict[str, Any] | None = None,
    ) -> ChatSessionArtifactModel: ...

    async def update_token_usage(
        self, session_id: str, tokens_inbound: int, tokens_outbound: int
    ) -> None: ...
