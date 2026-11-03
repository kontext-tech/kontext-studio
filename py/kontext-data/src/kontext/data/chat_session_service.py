"""
Chat session data service for managing chat session database operations.

This service encapsulates all database operations for chat sessions,
separating data access logic from API endpoint logic.

Architecture:
    This service uses sync SQLAlchemy sessions internally but provides an async
    interface for FastAPI compatibility. Database operations are executed via
    asyncio.to_thread() to avoid blocking the event loop while maintaining
    clean separation between I/O phases.
"""

import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select

from kontext.common.catalog.connector_specs import get_catalog_connector_spec
from kontext.common.utils.datetime_utils import normalize_datetime_utc, utc_now
from kontext.common.utils.json_compat import model_validate_stored
from kontext.schema import (
    ArtifactType,
    ChatAttachmentContext,
    ChatAttachmentContextFile,
    ChatAttachmentContextTable,
    ChatSessionArtifactModel,
    ChatSessionModel,
    CreateChatSessionRequest,
    PaginatedChatSessionResponse,
    PythonExecutionApprovalMode,
    TokenUsageDailyStatsModel,
    TokenUsageStatsModel,
    UpdateChatSessionRequest,
)

from .agent_run_state_service import delete_run_state_rows
from .base_service import ProjectDataService, ensure_uuid
from .models import (
    CatalogConnection as CatalogConnectionRecord,
)
from .models import (
    ChatSession,
    ChatSessionArtifact,
    ChatSessionAttachmentContext,
    ChatSessionTokenUsage,
)


class ChatSessionNotFoundError(Exception):
    """Raised when a chat session is not found."""

    pass


logger = logging.getLogger(__name__)

# Fallback title for artifacts persisted without an explicit display name.
DEFAULT_ARTIFACT_TITLE = "Untitled"


def _chat_session_to_response(session: ChatSession) -> ChatSessionModel:
    """Convert SQLAlchemy ChatSession model to Pydantic ChatSessionModel.

    Args:
        session: SQLAlchemy ChatSession instance

    Returns:
        ChatSessionModel with properly formatted data
    """
    return ChatSessionModel(
        id=str(session.id),
        project_id=str(session.project_id),
        session_name=str(session.session_name or ""),
        model_selection_id=session.model_selection_id,
        tokens_inbound=session.tokens_inbound,
        tokens_outbound=session.tokens_outbound,
        owner_id=str(session.owner_id) if session.owner_id else None,
        date_created=normalize_datetime_utc(session.created_at) or utc_now(),
        modified_by_user_id=session.updated_by,
        date_modified=normalize_datetime_utc(session.updated_at),
        query_session_id=str(session.query_session_id) if session.query_session_id else None,
        default_catalog_connection_id=str(session.default_catalog_connection_id)
        if session.default_catalog_connection_id
        else None,
        default_namespace=session.default_namespace,
        default_entity_id=str(session.default_entity_id) if session.default_entity_id else None,
        engine_type=session.engine_type,
        python_execution_approval_mode=PythonExecutionApprovalMode(
            session.python_execution_approval_mode or "always_ask"
        ),
        is_deleted=bool(session.is_deleted),
        date_deleted=normalize_datetime_utc(session.deleted_at),
    )


def _parse_attachment_context_files(
    value: list[dict[str, Any]] | None,
) -> list[ChatAttachmentContextFile]:
    files: list[ChatAttachmentContextFile] = []
    for entry in value or []:
        if not isinstance(entry, dict):
            continue
        try:
            files.append(model_validate_stored(ChatAttachmentContextFile, entry))
        except Exception:
            continue
    return files


def _parse_attachment_context_tables(
    value: list[dict[str, Any]] | None,
) -> list[ChatAttachmentContextTable]:
    tables: list[ChatAttachmentContextTable] = []
    for entry in value or []:
        if not isinstance(entry, dict):
            continue
        try:
            tables.append(model_validate_stored(ChatAttachmentContextTable, entry))
        except Exception:
            continue
    return tables


def _attachment_context_to_response(
    context: ChatSessionAttachmentContext,
) -> ChatAttachmentContext:
    return ChatAttachmentContext(
        upload_preparation_run_id=str(context.upload_preparation_run_id),
        internal_catalog_connection_id=str(context.internal_catalog_connection_id),
        files=_parse_attachment_context_files(context.files_json),
        tables=_parse_attachment_context_tables(context.tables_json),
    )


class ChatSessionDataService(ProjectDataService):
    """Service for managing chat session database operations.

    This service handles all CRUD operations for chat sessions in project-scoped
    SQLite databases. It accepts a sync Session and provides both sync and async
    methods for consistency with other data services.
    """

    # =========================================================================
    # Async Interface (for FastAPI endpoints)
    # =========================================================================

    async def create_session_async(
        self,
        request: CreateChatSessionRequest,
        user_id: str | None,
        resolved_model_config: dict | None = None,
    ) -> ChatSessionModel:
        """Create a new chat session (async wrapper)."""
        return await asyncio.to_thread(
            self._create_session_sync, request, user_id, resolved_model_config
        )

    async def get_session_by_id_async(self, chat_session_id: UUID | str) -> ChatSessionModel | None:
        """Get a chat session by ID (async wrapper)."""
        return await asyncio.to_thread(self._get_session_by_id_sync, chat_session_id)

    async def get_session_resolved_model_config_async(
        self, chat_session_id: UUID | str
    ) -> dict[str, Any] | None:
        """Get the persisted resolved model config snapshot for a session."""
        return await asyncio.to_thread(
            self._get_session_resolved_model_config_sync, chat_session_id
        )

    async def update_session_async(
        self,
        chat_session_id: UUID | str,
        request: UpdateChatSessionRequest,
        user_id: str | None,
        resolved_model_config: dict | None = None,
    ) -> ChatSessionModel:
        """Update a chat session (async wrapper)."""
        return await asyncio.to_thread(
            self._update_session_sync,
            chat_session_id,
            request,
            user_id,
            resolved_model_config,
        )

    async def delete_session_async(self, chat_session_id: UUID | str, user_id: str | None) -> None:
        """Soft delete a chat session (async wrapper)."""
        return await asyncio.to_thread(self._delete_session_sync, chat_session_id, user_id)

    async def get_filtered_sessions_async(
        self,
        filter_str: str | None = None,
        page_index: int = 1,
        page_size: int = 10,
        user_id: str | None = None,
    ) -> PaginatedChatSessionResponse:
        """Get filtered and paginated chat sessions (async wrapper)."""
        return await asyncio.to_thread(
            self._get_filtered_sessions_sync, filter_str, page_index, page_size, user_id
        )

    async def upsert_attachment_context_async(
        self,
        chat_session_id: UUID | str,
        context: ChatAttachmentContext,
    ) -> ChatAttachmentContext:
        return await asyncio.to_thread(
            self._upsert_attachment_context_sync,
            chat_session_id,
            context,
        )

    async def get_attachment_context_async(
        self, chat_session_id: UUID | str
    ) -> ChatAttachmentContext | None:
        return await asyncio.to_thread(
            self._get_attachment_context_sync,
            chat_session_id,
        )

    # =========================================================================
    # Sync Implementation
    # =========================================================================

    def _create_session_sync(
        self,
        request: CreateChatSessionRequest,
        user_id: str | None,
        resolved_model_config: dict | None = None,
    ) -> ChatSessionModel:
        """Create a new chat session.

        Args:
            request: Chat session creation request
            user_id: ID of the user creating the session

        Returns:
            Created chat session response
        """
        with self._session_scope() as session:
            engine_type = request.engine_type or self._resolve_engine_type_for_connection(
                session, request.default_catalog_connection_id
            )
            new_session = ChatSession(
                project_id=ensure_uuid(request.project_id),
                session_name=request.session_name,
                model_selection_id=request.model_selection_id,
                resolved_model_config=resolved_model_config,
                default_catalog_connection_id=ensure_uuid(request.default_catalog_connection_id)
                if request.default_catalog_connection_id
                else None,
                default_namespace=request.default_namespace,
                default_entity_id=ensure_uuid(request.default_entity_id)
                if request.default_entity_id
                else None,
                engine_type=engine_type,
                python_execution_approval_mode=(
                    request.python_execution_approval_mode or PythonExecutionApprovalMode.ALWAYSASK
                ),
                created_at=utc_now(),
                updated_at=utc_now(),
                created_by=user_id,
                owner_id=UUID(user_id) if user_id else None,
            )
            session.add(new_session)
            session.flush()
            session.expunge(new_session)
            return _chat_session_to_response(new_session)

    def _get_session_by_id_sync(self, chat_session_id: UUID | str) -> ChatSessionModel | None:
        """Get a chat session by ID.

        Args:
            chat_session_id: Chat session ID

        Returns:
            Chat session response if found, None otherwise
        """
        chat_session_id = ensure_uuid(chat_session_id)
        with self._session_scope(commit=False) as session:
            stmt = select(ChatSession).where(
                ChatSession.id == chat_session_id, ChatSession.is_deleted.is_(False)
            )

            if self._project_id:
                stmt = stmt.where(ChatSession.project_id == ensure_uuid(self._project_id))

            chat_session = session.execute(stmt).scalar_one_or_none()
            if not chat_session:
                return None
            session.expunge(chat_session)
            return _chat_session_to_response(chat_session)

    def _get_session_resolved_model_config_sync(
        self, chat_session_id: UUID | str
    ) -> dict[str, Any] | None:
        chat_session_id = ensure_uuid(chat_session_id)
        with self._session_scope(commit=False) as session:
            stmt = select(ChatSession.resolved_model_config).where(
                ChatSession.id == chat_session_id, ChatSession.is_deleted.is_(False)
            )
            if self._project_id:
                stmt = stmt.where(ChatSession.project_id == ensure_uuid(self._project_id))
            return session.execute(stmt).scalar_one_or_none()

    def _upsert_attachment_context_sync(
        self,
        chat_session_id: UUID | str,
        context: ChatAttachmentContext,
    ) -> ChatAttachmentContext:
        normalized_chat_session_id = ensure_uuid(chat_session_id)
        with self._session_scope() as session:
            record = session.get(ChatSessionAttachmentContext, normalized_chat_session_id)
            if record is None:
                record = ChatSessionAttachmentContext(chat_session_id=normalized_chat_session_id)
                session.add(record)

            record.upload_preparation_run_id = ensure_uuid(context.upload_preparation_run_id)
            record.internal_catalog_connection_id = ensure_uuid(
                context.internal_catalog_connection_id
            )
            record.files_json = [file.model_dump(mode="json") for file in context.files]
            record.tables_json = [table.model_dump(mode="json") for table in context.tables]
            record.updated_at = utc_now()

            session.flush()
            return _attachment_context_to_response(record)

    def _get_attachment_context_sync(
        self, chat_session_id: UUID | str
    ) -> ChatAttachmentContext | None:
        normalized_chat_session_id = ensure_uuid(chat_session_id)
        with self._session_scope(commit=False) as session:
            record = session.get(ChatSessionAttachmentContext, normalized_chat_session_id)
            if record is None:
                return None
            return _attachment_context_to_response(record)

    def _update_session_sync(
        self,
        chat_session_id: UUID | str,
        request: UpdateChatSessionRequest,
        user_id: str | None,
        resolved_model_config: dict | None = None,
    ) -> ChatSessionModel:
        """Update a chat session.

        Args:
            chat_session_id: Chat session ID
            request: Update request with new values
            user_id: ID of the user updating the session

        Returns:
            Updated chat session model

        Raises:
            ChatSessionNotFoundError: If session not found
        """
        chat_session_id = ensure_uuid(chat_session_id)
        with self._session_scope() as session:
            stmt = select(ChatSession).where(
                ChatSession.id == chat_session_id, ChatSession.is_deleted.is_(False)
            )

            if self._project_id:
                stmt = stmt.where(ChatSession.project_id == ensure_uuid(self._project_id))

            chat_session = session.execute(stmt).scalar_one_or_none()
            if not chat_session:
                raise ChatSessionNotFoundError(f"Chat session {chat_session_id} not found")

            # Update fields
            chat_session.updated_at = utc_now()
            chat_session.updated_by = user_id
            if request.session_name is not None:
                chat_session.session_name = request.session_name
            if request.query_session_id is not None:
                chat_session.query_session_id = ensure_uuid(request.query_session_id)
            if request.model_selection_id is not None:
                chat_session.model_selection_id = request.model_selection_id
                chat_session.resolved_model_config = resolved_model_config
            if request.default_catalog_connection_id is not None:
                chat_session.default_catalog_connection_id = ensure_uuid(
                    request.default_catalog_connection_id
                )
            if request.default_namespace is not None:
                chat_session.default_namespace = request.default_namespace
            if request.default_entity_id is not None:
                chat_session.default_entity_id = ensure_uuid(request.default_entity_id)
            if request.engine_type is not None:
                chat_session.engine_type = request.engine_type
            elif request.default_catalog_connection_id is not None:
                chat_session.engine_type = self._resolve_engine_type_for_connection(
                    session, request.default_catalog_connection_id
                )
            if request.python_execution_approval_mode is not None:
                chat_session.python_execution_approval_mode = request.python_execution_approval_mode

            session.flush()
            session.expunge(chat_session)
            return _chat_session_to_response(chat_session)

    def _resolve_engine_type_for_connection(
        self, session, connection_id: UUID | str | None
    ) -> str | None:
        if not connection_id:
            return None

        provider_kind = session.execute(
            select(CatalogConnectionRecord.provider_kind).where(
                CatalogConnectionRecord.id == ensure_uuid(connection_id),
                CatalogConnectionRecord.project_id == ensure_uuid(self._project_id),
                CatalogConnectionRecord.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if not provider_kind:
            return None
        return get_catalog_connector_spec(str(provider_kind)).query_engine_type.value

    def _delete_session_sync(self, chat_session_id: UUID | str, user_id: str | None) -> None:
        """Soft delete a chat session.

        Args:
            chat_session_id: Chat session ID
            user_id: ID of the user deleting the session

        Raises:
            ChatSessionNotFoundError: If session not found
        """
        chat_session_id = ensure_uuid(chat_session_id)
        with self._session_scope() as session:
            stmt = select(ChatSession).where(
                ChatSession.id == chat_session_id, ChatSession.is_deleted.is_(False)
            )

            if self._project_id:
                stmt = stmt.where(ChatSession.project_id == ensure_uuid(self._project_id))

            chat_session = session.execute(stmt).scalar_one_or_none()
            if not chat_session:
                raise ChatSessionNotFoundError(f"Chat session {chat_session_id} not found")

            chat_session.is_deleted = True
            chat_session.deleted_at = utc_now()
            chat_session.updated_by = user_id
            session.flush()

            # Harness run-state cascade: drop the neutral run-state rows
            # (message snapshot, harness blob) in this same transaction.
            # Keeping them would resurrect history via the store-first read
            # path after the chat session is gone.
            delete_run_state_rows(session, str(chat_session_id))

    def _get_filtered_sessions_sync(
        self,
        filter_str: str | None = None,
        page_index: int = 1,
        page_size: int = 10,
        user_id: str | None = None,
    ) -> PaginatedChatSessionResponse:
        """Get filtered and paginated chat sessions.

        Args:
            filter_str: Optional filter string for session name
            page_index: Page number (1-indexed)
            page_size: Items per page
            user_id: Optional user ID to filter by

        Returns:
            Paginated chat session response
        """
        if not self._project_id:
            return PaginatedChatSessionResponse(
                items=[],
                total_count=0,
                page_index=page_index,
                page_size=page_size,
                total_pages=0,
            )

        with self._session_scope(commit=False) as session:
            stmt = select(ChatSession).where(
                ChatSession.project_id == ensure_uuid(self._project_id),
                ChatSession.is_deleted.is_(False),
            )

            if filter_str:
                stmt = stmt.where(ChatSession.session_name.contains(filter_str))

            if user_id:
                stmt = stmt.where(ChatSession.owner_id == ensure_uuid(user_id))

            # Get total count using func.count
            from sqlalchemy import func

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = session.execute(count_stmt).scalar_one()

            items_stmt = (
                stmt.order_by(desc(ChatSession.updated_at))
                .offset((page_index - 1) * page_size)
                .limit(page_size)
            )

            items = session.execute(items_stmt).scalars().all()
            for item in items:
                session.expunge(item)
            items_pydantic = [_chat_session_to_response(item) for item in items]

            total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0
            return PaginatedChatSessionResponse(
                items=items_pydantic,
                total_count=total_count,
                page_index=page_index,
                page_size=page_size,
                total_pages=total_pages,
            )

    def update_token_usage(
        self, session_id: UUID | str, tokens_inbound: int, tokens_outbound: int
    ) -> None:
        """Update token usage statistics for a chat session."""
        with self._session_scope(commit=True) as session:
            stmt = select(ChatSession).where(ChatSession.id == ensure_uuid(session_id))
            chat_session = session.execute(stmt).scalar_one_or_none()

            if chat_session:
                chat_session.tokens_inbound = tokens_inbound
                chat_session.tokens_outbound = tokens_outbound
                chat_session.updated_at = utc_now()

    async def update_token_usage_async(
        self, session_id: UUID | str, tokens_inbound: int, tokens_outbound: int
    ) -> None:
        """Update token usage statistics for a chat session (async wrapper)."""
        await asyncio.to_thread(
            self.update_token_usage, session_id, tokens_inbound, tokens_outbound
        )

    def get_project_token_usage_stats(self) -> list[TokenUsageStatsModel]:
        """Get token usage statistics for the project aggregated by month and model.

        Uses ChatSessionTokenUsage.consumed_at for accurate temporal attribution.
        Tokens are grouped by when they were consumed, not when the session was created.
        """
        from sqlalchemy import func

        with self._session_scope(commit=False) as session:
            dialect_name = (
                getattr(session.bind.dialect, "name", "").lower()
                if session.bind is not None
                else ""
            )

            if dialect_name == "sqlite":
                month_expr = func.strftime("%Y-%m", ChatSessionTokenUsage.consumed_at)
            else:
                month_expr = func.to_char(ChatSessionTokenUsage.consumed_at, "YYYY-MM")

            stmt = (
                select(
                    month_expr.label("month"),
                    ChatSessionTokenUsage.model_selection_id,
                    func.sum(ChatSessionTokenUsage.tokens_inbound).label("inbound"),
                    func.sum(ChatSessionTokenUsage.tokens_outbound).label("outbound"),
                )
                .where(ChatSessionTokenUsage.project_id == ensure_uuid(self._project_id))
                .group_by("month", ChatSessionTokenUsage.model_selection_id)
                .order_by(desc("month"))
            )

            results = session.execute(stmt).all()

            stats = []
            for row in results:
                # Handle potential None values from sum
                inbound = row.inbound or 0
                outbound = row.outbound or 0

                stats.append(
                    TokenUsageStatsModel(
                        month=row.month,
                        model_selection_id=row.model_selection_id,
                        canonical_model_id=None,
                        inbound_tokens=inbound,
                        outbound_tokens=outbound,
                        total_tokens=inbound + outbound,
                    )
                )

            return stats

    def get_project_daily_token_usage_stats(
        self, month: str | None = None
    ) -> list[TokenUsageDailyStatsModel]:
        """Get daily token usage statistics aggregated by day and model.

        Uses ChatSessionTokenUsage.consumed_at for accurate temporal attribution.
        Tokens are grouped by when they were consumed, not when the session was created.

        Args:
            month: Optional month filter (YYYY-MM format). Defaults to current month.
        """
        from sqlalchemy import func

        # Default to current month if not provided
        if not month:
            month = utc_now().strftime("%Y-%m")

        with self._session_scope(commit=False) as session:
            dialect_name = (
                getattr(session.bind.dialect, "name", "").lower()
                if session.bind is not None
                else ""
            )

            if dialect_name == "sqlite":
                day_expr = func.strftime("%Y-%m-%d", ChatSessionTokenUsage.consumed_at)
                month_filter_expr = func.strftime("%Y-%m", ChatSessionTokenUsage.consumed_at)
            else:
                day_expr = func.to_char(ChatSessionTokenUsage.consumed_at, "YYYY-MM-DD")
                month_filter_expr = func.to_char(ChatSessionTokenUsage.consumed_at, "YYYY-MM")

            stmt = (
                select(
                    day_expr.label("day"),
                    ChatSessionTokenUsage.model_selection_id,
                    func.sum(ChatSessionTokenUsage.tokens_inbound).label("inbound"),
                    func.sum(ChatSessionTokenUsage.tokens_outbound).label("outbound"),
                )
                .where(ChatSessionTokenUsage.project_id == ensure_uuid(self._project_id))
                .where(month_filter_expr == month)
                .group_by("day", ChatSessionTokenUsage.model_selection_id)
                .order_by(desc("day"))
            )

            results = session.execute(stmt).all()

            stats = []
            for row in results:
                inbound = row.inbound or 0
                outbound = row.outbound or 0

                stats.append(
                    TokenUsageDailyStatsModel(
                        day=row.day,
                        model_selection_id=row.model_selection_id,
                        canonical_model_id=None,
                        inbound_tokens=inbound,
                        outbound_tokens=outbound,
                        total_tokens=inbound + outbound,
                    )
                )

            return stats

    async def get_project_token_usage_stats_async(self) -> list[TokenUsageStatsModel]:
        return await asyncio.to_thread(self.get_project_token_usage_stats)

    async def get_project_daily_token_usage_stats_async(
        self, month: str | None = None
    ) -> list[TokenUsageDailyStatsModel]:
        return await asyncio.to_thread(self.get_project_daily_token_usage_stats, month)

    def upsert_artifact_sync(
        self,
        session_id: UUID | str,
        artifact_id: UUID | str,
        artifact_type: str,
        title: str | None,
        meta: dict[str, Any] | None = None,
    ) -> ChatSessionArtifactModel:
        """Upsert a chat session artifact.

        On update, ``title`` and ``meta`` are only overwritten when provided
        (non-``None``); passing ``None`` preserves the existing value. This
        keeps secondary links (e.g. re-showing an already persisted data table)
        from clobbering the descriptive title and provenance recorded when the
        artifact was first created.
        """
        with self._session_scope() as session:
            stmt = select(ChatSessionArtifact).where(
                ChatSessionArtifact.session_id == ensure_uuid(session_id),
                ChatSessionArtifact.artifact_id == ensure_uuid(artifact_id),
            )
            artifact = session.execute(stmt).scalar_one_or_none()

            if artifact:
                if title is not None:
                    artifact.title = title
                if meta is not None:
                    artifact.meta = meta
                artifact.updated_at = utc_now()
            else:
                artifact = ChatSessionArtifact(
                    session_id=ensure_uuid(session_id),
                    artifact_id=ensure_uuid(artifact_id),
                    artifact_type=artifact_type,
                    title=title or DEFAULT_ARTIFACT_TITLE,
                    meta=meta,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                session.add(artifact)

            session.flush()
            session.expunge(artifact)

            return ChatSessionArtifactModel(
                id=str(artifact.id),
                session_id=str(artifact.session_id),
                artifact_id=str(artifact.artifact_id),
                artifact_type=ArtifactType(artifact.artifact_type),
                title=artifact.title,
                created_at=normalize_datetime_utc(artifact.created_at) or utc_now(),
                updated_at=normalize_datetime_utc(artifact.updated_at) or utc_now(),
                meta=artifact.meta,
            )

    async def upsert_artifact_async(
        self,
        session_id: UUID | str,
        artifact_id: UUID | str,
        artifact_type: str,
        title: str | None,
        meta: dict[str, Any] | None = None,
    ) -> ChatSessionArtifactModel:
        return await asyncio.to_thread(
            self.upsert_artifact_sync,
            session_id,
            artifact_id,
            artifact_type,
            title,
            meta,
        )

    def get_session_artifacts_sync(self, session_id: UUID | str) -> list[ChatSessionArtifactModel]:
        """Get all artifacts for a chat session."""
        with self._session_scope(commit=False) as session:
            stmt = (
                select(ChatSessionArtifact)
                .where(
                    ChatSessionArtifact.session_id == ensure_uuid(session_id),
                    ChatSessionArtifact.deleted_at.is_(None),
                )
                .order_by(desc(ChatSessionArtifact.updated_at))
            )

            artifacts = session.execute(stmt).scalars().all()
            return [
                ChatSessionArtifactModel(
                    id=str(a.id),
                    session_id=str(a.session_id),
                    artifact_id=str(a.artifact_id),
                    artifact_type=ArtifactType(a.artifact_type),
                    title=a.title,
                    created_at=normalize_datetime_utc(a.created_at) or utc_now(),
                    updated_at=normalize_datetime_utc(a.updated_at) or utc_now(),
                    meta=a.meta,
                )
                for a in artifacts
            ]

    async def get_session_artifacts_async(
        self, session_id: UUID | str
    ) -> list[ChatSessionArtifactModel]:
        return await asyncio.to_thread(self.get_session_artifacts_sync, session_id)
