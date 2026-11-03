"""Query execution history data service for project-scoped SQLite operations.

This service encapsulates all database operations for query execution records,
separating data access logic from API endpoint logic.
"""

from uuid import UUID, uuid4

from sqlalchemy import desc, func, select

from kontext.common.utils.datetime_utils import normalize_datetime_utc, utc_now
from kontext.schema import CreateQueryRequest, QueryModel

from .base_service import ProjectDataService
from .models import Query


def _query_to_response(query: Query) -> QueryModel:
    """Convert SQLAlchemy Query to Pydantic response.

    Args:
        query: SQLAlchemy Query instance

    Returns:
        QueryModel with properly formatted data
    """
    # Convert string values back to int/long if present
    record_count = None
    if query.record_count:
        try:
            record_count = int(query.record_count)
        except (ValueError, TypeError):
            record_count = None

    duration_ms = 0
    if query.duration_ms:
        try:
            duration_ms = int(query.duration_ms)
        except (ValueError, TypeError):
            duration_ms = 0

    return QueryModel(
        id=str(query.id),
        code=str(query.code),
        succeeded=bool(query.succeeded),
        record_count=record_count,
        message=query.message,
        owner_id=str(query.owner_id),
        session_id=str(query.session_id) if query.session_id else None,
        job_run_id=str(query.job_run_id) if query.job_run_id else None,
        created_at=normalize_datetime_utc(query.created_at),
        duration_ms=duration_ms,
    )


class QueryHistoryDataService(ProjectDataService):
    """Service for managing query execution history database operations.

    This service handles all CRUD operations for query execution records in
    project-scoped SQLite databases. Session lifecycle is managed by the caller.
    """

    def record_query(self, request: CreateQueryRequest, user_id: str | None) -> QueryModel:
        """Record a query execution in history.

        Args:
            request: Request containing query execution details
            user_id: ID of the user executing the query

        Returns:
            Created query view model
        """
        with self._session_scope() as session:
            new_query = Query(
                id=uuid4(),
                code=request.code,
                succeeded=request.succeeded,
                record_count=(str(request.record_count) if request.record_count else None),
                message=request.message,
                owner_id=(
                    UUID(user_id) if user_id else UUID("00000000-0000-0000-0000-000000000000")
                ),
                session_id=(UUID(str(request.session_id)) if request.session_id else None),
                job_run_id=(UUID(str(request.job_run_id)) if request.job_run_id else None),
                duration_ms=str(request.duration_ms),
                created_at=utc_now(),
            )

            session.add(new_query)
            session.flush()
            self._make_detached(session, new_query)

            return _query_to_response(new_query)

    def get_session_queries(
        self, session_id: str, page_index: int, page_size: int
    ) -> tuple[list[QueryModel], int]:
        """Get queries for a session with pagination.

        Args:
            session_id: ID of the session
            page_index: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of queries, total count)
        """
        with self._session_scope(commit=False) as session:
            stmt = select(Query).where(Query.session_id == UUID(session_id))

            # Get total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = session.execute(count_stmt).scalar_one()

            # Get paginated results
            paginated_stmt = (
                stmt.order_by(desc(Query.created_at))
                .offset((page_index - 1) * page_size)
                .limit(page_size)
            )

            queries = session.execute(paginated_stmt).scalars().all()
            for q in queries:
                self._make_detached(session, q)

            return [_query_to_response(q) for q in queries], total_count
