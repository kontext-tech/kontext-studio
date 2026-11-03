"""
Query session data service for managing query session database operations.

This service encapsulates all database operations for query sessions,
separating data access logic from API endpoint logic.
"""

from uuid import UUID, uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from kontext.common.catalog.connector_specs import get_catalog_connector_spec
from kontext.common.utils.datetime_utils import normalize_datetime_utc, utc_now
from kontext.schema import (
    CreateQuerySessionRequest,
    QueryEngineType,
    QuerySessionModel,
    QuerySessionStatus,
    UpdateQuerySessionRequest,
)

from .base_service import ProjectDataService
from .models import CatalogConnection as CatalogConnectionRecord
from .models import ChatSession, QuerySession

#: Statuses whose materialized catalog can be stale and must not be reused.
#: ``ERROR``/``CLOSED``/``DELETED`` are already non-reusable, so they are left
#: untouched (their files are still reclaimed by the orphan sweeper).
_REUSABLE_SESSION_STATUSES = (QuerySessionStatus.ACTIVE, QuerySessionStatus.INITIALIZING)


class QuerySessionNotFoundError(Exception):
    """Raised when a query session is not found."""

    pass


def _query_session_to_response(session: QuerySession) -> QuerySessionModel:
    """Convert SQLAlchemy QuerySession to Pydantic response.

    Args:
        session: SQLAlchemy QuerySession instance

    Returns:
        QuerySessionModel with properly formatted data
    """
    # Convert database_size_bytes from string to int if present
    db_size = None
    if session.database_size_bytes:
        try:
            db_size = int(session.database_size_bytes)
        except (ValueError, TypeError):
            db_size = None

    return QuerySessionModel(
        id=str(session.id),
        session_name=str(session.session_name),
        project_id=str(session.project_id),
        catalog_connection_id=(
            str(session.catalog_connection_id) if session.catalog_connection_id else None
        ),
        default_namespace=session.default_namespace,
        default_entity_id=(str(session.default_entity_id) if session.default_entity_id else None),
        owner_id=str(session.owner_id) if session.owner_id else None,
        status=QuerySessionStatus(session.status),
        engine_type=QueryEngineType(session.engine_type)
        if session.engine_type
        else QueryEngineType.DUCKDB,
        job_run_id=str(session.job_run_id) if session.job_run_id else None,
        created_at=normalize_datetime_utc(session.created_at),
        updated_at=normalize_datetime_utc(session.updated_at),
        last_accessed_at=normalize_datetime_utc(session.last_accessed_at),
        is_persistent=True,  # All SQLite sessions are persistent
        database_size_bytes=db_size,
        catalog_revision=session.catalog_revision,
    )


class QuerySessionDataService(ProjectDataService):
    """Service for managing query session database operations.

    This service handles all CRUD operations for query sessions in project-scoped
    SQLite databases. Session lifecycle is managed by the caller.
    """

    async def get_by_id_async(
        self, session_id: UUID | str, owner_id: str | None = None
    ) -> QuerySessionModel | None:
        """Get a query session by ID (async wrapper)."""
        import asyncio

        return await asyncio.to_thread(self.get_session, str(session_id), owner_id)

    async def create_session_async(
        self,
        request: CreateQuerySessionRequest,
        user_id: str | None,
        engine_type: QueryEngineType | None = None,
    ) -> QuerySessionModel:
        """Create a new query session (async wrapper).

        Args:
            request: Request containing session creation details
            user_id: ID of the user creating the session
            engine_type: Optional pre-resolved engine type

        Returns:
            Created query session response
        """
        import asyncio

        return await asyncio.to_thread(self.create_session, request, user_id, engine_type)

    async def set_catalog_revision_async(
        self, session_id: UUID | str, revision: str | None
    ) -> bool:
        """Set the catalog revision a session materialized (async wrapper)."""
        import asyncio

        return await asyncio.to_thread(self.set_catalog_revision, str(session_id), revision)

    def get_catalog_revision(self, connection_id: UUID | str | None) -> str | None:
        """Return the current catalog revision for a connection, if known."""
        if not connection_id:
            return None
        with self._session_scope(commit=False) as session:
            revision = session.execute(
                select(CatalogConnectionRecord.catalog_revision).where(
                    CatalogConnectionRecord.id == UUID(str(connection_id)),
                    CatalogConnectionRecord.project_id == UUID(self._project_id),
                    CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                )
            ).scalar_one_or_none()
        return revision

    async def get_catalog_revision_async(self, connection_id: UUID | str | None) -> str | None:
        """Async wrapper for :meth:`get_catalog_revision`."""
        import asyncio

        return await asyncio.to_thread(self.get_catalog_revision, connection_id)

    async def invalidate_sessions_for_catalog_connection_async(
        self,
        connection_id: UUID | str,
        reason: str = "Catalog structure changed",
    ) -> list[UUID]:
        """Invalidate reusable sessions for a connection (async wrapper)."""
        import asyncio

        return await asyncio.to_thread(
            self.invalidate_sessions_for_catalog_connection,
            connection_id,
            reason,
        )

    def create_session(
        self,
        request: CreateQuerySessionRequest,
        user_id: str | None,
        engine_type: QueryEngineType | None = None,
    ) -> QuerySessionModel:
        """Create a new query session.

        Args:
            request: Request containing session creation details
            user_id: ID of the user creating the session
            engine_type: Optional pre-resolved engine type. If omitted,
                it will be resolved from request or project defaults.

        Returns:
            Created query session response
        """
        with self._session_scope() as session:
            # Determine engine type (request -> catalog connection -> project default -> DuckDB).
            if not engine_type:
                engine_type = request.engine_type

            if not engine_type and request.catalog_connection_id:
                provider_kind = session.execute(
                    select(CatalogConnectionRecord.provider_kind).where(
                        CatalogConnectionRecord.id == UUID(str(request.catalog_connection_id)),
                        CatalogConnectionRecord.project_id == UUID(self._project_id),
                        CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                    )
                ).scalar_one_or_none()
                if provider_kind:
                    engine_type = get_catalog_connector_spec(str(provider_kind)).query_engine_type

            # Check project default engine if still not resolved
            if not engine_type:
                config = self._get_project_config(session)
                if config and config.default_query_engine:
                    engine_type = config.default_query_engine

            # Final fallback
            if not engine_type:
                engine_type = QueryEngineType.DUCKDB

            session_id = uuid4()
            new_session = QuerySession(
                id=session_id,
                session_name=request.session_name or f"Session {str(session_id)[:8]}",
                project_id=UUID(str(request.project_id)),
                catalog_connection_id=(
                    UUID(str(request.catalog_connection_id))
                    if request.catalog_connection_id
                    else None
                ),
                default_namespace=request.default_namespace,
                default_entity_id=(
                    UUID(str(request.default_entity_id)) if request.default_entity_id else None
                ),
                owner_id=UUID(user_id) if user_id else None,
                status=QuerySessionStatus.INITIALIZING.value,
                engine_type=engine_type.value,  # Store enum value as string in DB
                created_by=user_id,
                created_at=utc_now(),
                is_deleted=False,
            )

            session.add(new_session)
            session.flush()
            self._make_detached(session, new_session)

            return _query_session_to_response(new_session)

    def get_session(self, session_id: str, owner_id: str | None = None) -> QuerySessionModel | None:
        """Get a query session by ID.

        Args:
            session_id: ID of the session to retrieve

        Returns:
            Query session response or None if not found
        """
        with self._session_scope(commit=False) as session:
            stmt = select(QuerySession).where(
                QuerySession.id == UUID(session_id),
                QuerySession.project_id == UUID(self._project_id),
                QuerySession.is_deleted == False,  # noqa: E712
            )

            # Optionally restrict to sessions owned by a specific user
            if owner_id:
                stmt = stmt.where(QuerySession.owner_id == UUID(owner_id))

            query_session = session.execute(stmt).scalar_one_or_none()

            if not query_session:
                return None

            self._make_detached(session, query_session)
            return _query_session_to_response(query_session)

    def update_session(
        self, session_id: str, request: UpdateQuerySessionRequest, user_id: str | None
    ) -> QuerySessionModel:
        """Update a query session.

        Args:
            session_id: ID of the session to update
            request: Request containing update details
            user_id: ID of the user updating the session

        Returns:
            Updated query session response

        Raises:
            QuerySessionNotFoundError: If session not found
        """
        with self._session_scope() as session:
            stmt = select(QuerySession).where(
                QuerySession.id == UUID(session_id),
                QuerySession.project_id == UUID(self._project_id),
                QuerySession.is_deleted == False,  # noqa: E712
            )

            query_session = session.execute(stmt).scalar_one_or_none()

            if not query_session:
                raise QuerySessionNotFoundError(f"Query session {session_id} not found")

            # Update fields
            if request.session_name is not None:
                query_session.session_name = request.session_name
            if request.status is not None:
                query_session.status = request.status
                # If status is being set to DELETED, trigger soft-delete fields
                if request.status == QuerySessionStatus.DELETED:
                    query_session.is_deleted = True
                    query_session.deleted_at = utc_now()
            if request.metadata is not None:
                query_session.metadata_json = request.metadata
            if request.database_size_bytes is not None:
                query_session.database_size_bytes = request.database_size_bytes

            query_session.updated_by = user_id
            query_session.updated_at = utc_now()
            query_session.last_accessed_at = utc_now()

            session.flush()
            self._make_detached(session, query_session)

            return _query_session_to_response(query_session)

    def set_job_run_id(self, session_id: str, job_run_id: str, user_id: str | None = None) -> bool:
        """Set the job run ID for a session.

        This links the session to a job run for tracking initialization status.

        Args:
            session_id: ID of the session to update
            job_run_id: Job run ID to link
            user_id: ID of the user updating the session

        Returns:
            True if successful, False if session not found
        """
        with self._session_scope() as session:
            stmt = select(QuerySession).where(
                QuerySession.id == UUID(session_id),
                QuerySession.project_id == UUID(self._project_id),
                QuerySession.is_deleted == False,  # noqa: E712
            )

            query_session = session.execute(stmt).scalar_one_or_none()

            if not query_session:
                return False

            query_session.job_run_id = UUID(job_run_id)
            query_session.updated_by = user_id
            query_session.updated_at = utc_now()

            session.flush()
            return True

    def set_catalog_revision(self, session_id: str, revision: str | None) -> bool:
        """Record the catalog revision a session materialized at init time.

        Returns True if the session was found and updated.
        """
        with self._session_scope() as session:
            stmt = select(QuerySession).where(
                QuerySession.id == UUID(session_id),
                QuerySession.project_id == UUID(self._project_id),
                QuerySession.is_deleted == False,  # noqa: E712
            )
            query_session = session.execute(stmt).scalar_one_or_none()
            if not query_session:
                return False
            query_session.catalog_revision = revision
            query_session.updated_at = utc_now()
            session.flush()
            return True

    def _invalidate_query_sessions(
        self,
        session: Session,
        *,
        where_clauses: list,
        reason: str,
    ) -> list[UUID]:
        """Soft-delete reusable query sessions matching *where_clauses*.

        Also clears the reverse ``ChatSession.query_session_id`` links so a
        dangling reference is never left behind; the next SQL tool call
        re-creates and re-links a session. Returns the invalidated session IDs
        so callers can reclaim their DuckDB files.
        """
        import json

        now = utc_now()
        stmt = select(QuerySession).where(*where_clauses)
        sessions = session.execute(stmt).scalars().all()
        invalidated_ids: list[UUID] = []
        for query_session in sessions:
            query_session.status = QuerySessionStatus.DELETED
            query_session.is_deleted = True
            query_session.deleted_at = now
            query_session.metadata_json = json.dumps({"reason": reason, "invalidated_by": "system"})
            query_session.updated_at = now
            invalidated_ids.append(query_session.id)

        if invalidated_ids:
            linked_chats = (
                session.execute(
                    select(ChatSession).where(ChatSession.query_session_id.in_(invalidated_ids))
                )
                .scalars()
                .all()
            )
            for chat_session in linked_chats:
                chat_session.query_session_id = None
                chat_session.updated_at = now

        session.flush()
        return invalidated_ids

    def invalidate_sessions(self, reason: str = "Catalog structure changed") -> list[UUID]:
        """Invalidate all reusable sessions in the project due to catalog changes.

        Prefer :meth:`invalidate_sessions_for_catalog_connection`; this project-wide
        variant is only for callers that cannot resolve the affected connection.

        Args:
            reason: Reason for invalidation (stored in metadata as JSON)

        Returns:
            List of session IDs that were invalidated
        """
        with self._session_scope() as session:
            return self._invalidate_query_sessions(
                session,
                where_clauses=[
                    QuerySession.project_id == UUID(self._project_id),
                    QuerySession.status.in_(_REUSABLE_SESSION_STATUSES),
                    QuerySession.is_deleted == False,  # noqa: E712
                ],
                reason=reason,
            )

    def invalidate_sessions_for_catalog_connection(
        self,
        connection_id: UUID | str,
        reason: str = "Catalog structure changed",
    ) -> list[UUID]:
        """Invalidate reusable sessions bound to a specific catalog connection."""
        target_connection_id = UUID(str(connection_id))
        with self._session_scope() as session:
            return self._invalidate_query_sessions(
                session,
                where_clauses=[
                    QuerySession.project_id == UUID(self._project_id),
                    QuerySession.catalog_connection_id == target_connection_id,
                    QuerySession.status.in_(_REUSABLE_SESSION_STATUSES),
                    QuerySession.is_deleted == False,  # noqa: E712
                ],
                reason=reason,
            )

    def delete_session(self, session_id: str, user_id: str | None) -> bool:
        """Soft delete a query session.

        Args:
            session_id: ID of the session to delete
            user_id: ID of the user deleting the session

        Returns:
            True if successful, False if session not found
        """
        with self._session_scope() as session:
            stmt = select(QuerySession).where(
                QuerySession.id == UUID(session_id),
                QuerySession.project_id == UUID(self._project_id),
                QuerySession.is_deleted == False,  # noqa: E712
            )

            query_session = session.execute(stmt).scalar_one_or_none()

            if not query_session:
                return False

            query_session.is_deleted = True
            query_session.deleted_at = utc_now()
            query_session.updated_by = user_id
            query_session.updated_at = utc_now()
            query_session.status = QuerySessionStatus.DELETED

            session.flush()
            return True

    def list_sessions(
        self,
        owner_id: str | None,
        page_index: int,
        page_size: int,
        include_deleted: bool = False,
    ) -> tuple[list[QuerySessionModel], int]:
        """List query sessions with pagination.

        Args:
            owner_id: Filter by owner ID (None for all sessions)
            page_index: Page number (1-indexed)
            page_size: Number of items per page
            include_deleted: Whether to include deleted sessions

        Returns:
            Tuple of (list of sessions, total count)
        """
        with self._session_scope(commit=False) as session:
            stmt = select(QuerySession).where(QuerySession.project_id == UUID(self._project_id))

            if not include_deleted:
                stmt = stmt.where(QuerySession.is_deleted == False)  # noqa: E712

            if owner_id:
                stmt = stmt.where(QuerySession.owner_id == UUID(owner_id))

            # Get total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = session.execute(count_stmt).scalar_one()

            # Get paginated results
            paginated_stmt = (
                stmt.order_by(desc(QuerySession.created_at))
                .offset((page_index - 1) * page_size)
                .limit(page_size)
            )

            sessions = session.execute(paginated_stmt).scalars().all()
            for s in sessions:
                session.expunge(s)

            return [_query_session_to_response(s) for s in sessions], total_count

    def get_most_recent_session_by_status(
        self,
        owner_id: str,
        statuses: list[QuerySessionStatus] | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        engine_type: QueryEngineType | str | None = None,
    ) -> QuerySessionModel | None:
        """Get the most recent session with specified status and catalog scope.

        Useful for automatic session reuse - returns the most recently created
        or accessed active/initializing session for the user.

        Args:
            owner_id: Owner ID to filter by
            statuses: Optional list of QuerySessionStatus to filter by.
                     If None, returns the most recent session regardless of status.
            engine_type: Optional engine type to filter by.

        Returns:
            The most recent matching session, or None if no sessions found
        """
        with self._session_scope(commit=False) as session:
            stmt = select(QuerySession).where(
                QuerySession.project_id == UUID(self._project_id),
                QuerySession.owner_id == UUID(owner_id),
                QuerySession.is_deleted == False,  # noqa: E712
            )

            if statuses:
                stmt = stmt.where(QuerySession.status.in_(statuses))

            if catalog_connection_id:
                stmt = stmt.where(QuerySession.catalog_connection_id == UUID(catalog_connection_id))

            if default_namespace:
                stmt = stmt.where(QuerySession.default_namespace == default_namespace)

            if engine_type:
                # Convert to string if it's an enum
                if isinstance(engine_type, QueryEngineType):
                    engine_val = str(engine_type.value)
                else:
                    engine_val = str(engine_type)
                stmt = stmt.where(QuerySession.engine_type == engine_val)

            # Order by creation date (newest first) and get the first one
            stmt = stmt.order_by(desc(QuerySession.created_at)).limit(1)

            query_session = session.execute(stmt).scalar_one_or_none()
            if query_session:
                session.expunge(query_session)
                return _query_session_to_response(query_session)
            return None

    def list_sessions_by_status(
        self,
        owner_id: str | None = None,
        statuses: list[QuerySessionStatus] | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        page_index: int = 1,
        page_size: int = 50,
        include_deleted: bool = False,
    ) -> tuple[list[QuerySessionModel], int]:
        """List query sessions filtered by status and catalog scope with pagination.

        Useful for getting all active/initializing sessions for reuse detection
        or other status-specific operations.

        Args:
            owner_id: Optional filter by owner ID
            statuses: Optional list of QuerySessionStatus to filter by.
                     If None, returns all non-deleted sessions.
            page_index: Page number (1-indexed)
            page_size: Number of items per page
            include_deleted: Whether to include deleted sessions

        Returns:
            Tuple of (list of matching sessions, total count)
        """
        with self._session_scope(commit=False) as session:
            stmt = select(QuerySession).where(QuerySession.project_id == UUID(self._project_id))

            if not include_deleted:
                stmt = stmt.where(QuerySession.is_deleted == False)  # noqa: E712

            if owner_id:
                stmt = stmt.where(QuerySession.owner_id == UUID(owner_id))

            if statuses:
                stmt = stmt.where(QuerySession.status.in_(statuses))

            if catalog_connection_id:
                stmt = stmt.where(QuerySession.catalog_connection_id == UUID(catalog_connection_id))

            if default_namespace:
                stmt = stmt.where(QuerySession.default_namespace == default_namespace)

            # Get total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = session.execute(count_stmt).scalar_one()

            # Get paginated results
            paginated_stmt = (
                stmt.order_by(desc(QuerySession.created_at))
                .offset((page_index - 1) * page_size)
                .limit(page_size)
            )

            sessions = session.execute(paginated_stmt).scalars().all()
            for s in sessions:
                session.expunge(s)

            return [_query_session_to_response(s) for s in sessions], total_count
