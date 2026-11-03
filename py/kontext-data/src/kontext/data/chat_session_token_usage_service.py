"""
Chat session token usage data service for accurate time-series tracking.

This service manages token consumption records with proper temporal attribution,
ensuring daily and monthly aggregations reflect when tokens were actually consumed
rather than when the session was created.
"""

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, select

from kontext.common.utils.datetime_utils import utc_now
from kontext.schema import (
    TokenUsageDailyStatsModel,
    TokenUsageStatsModel,
)

from .base_service import ProjectDataService, ensure_uuid
from .models import ChatSessionTokenUsage

logger = logging.getLogger(__name__)


class ChatSessionTokenUsageDataService(ProjectDataService):
    """Service for managing time-series token usage records.

    This service tracks token consumption per chat turn with accurate timestamps,
    enabling correct daily and monthly aggregation regardless of session creation date.
    """

    # =========================================================================
    # Async Interface (for FastAPI endpoints)
    # =========================================================================

    async def record_token_usage_delta_async(
        self,
        *,
        chat_session_id: UUID | str,
        project_id: UUID | str,
        previous_inbound: int,
        previous_outbound: int,
        current_inbound: int,
        current_outbound: int,
        model_selection_id: str | None = None,
        job_run_id: UUID | str | None = None,
        consumed_at: datetime | None = None,
    ) -> None:
        """Record token usage as delta from previous cumulative values.

        This method calculates the delta between current cumulative totals and
        previous totals, storing only the incremental usage for this turn.

        Args:
            chat_session_id: The chat session ID
            project_id: The project ID
            previous_inbound: Previous cumulative inbound tokens
            previous_outbound: Previous cumulative outbound tokens
            current_inbound: New cumulative inbound tokens
            current_outbound: New cumulative outbound tokens
            model_selection_id: Optional model selection ID for aggregation
            job_run_id: Optional job run ID for tracking
            consumed_at: When tokens were consumed (defaults to now)
        """
        return await asyncio.to_thread(
            self._record_token_usage_delta_sync,
            chat_session_id=chat_session_id,
            project_id=project_id,
            previous_inbound=previous_inbound,
            previous_outbound=previous_outbound,
            current_inbound=current_inbound,
            current_outbound=current_outbound,
            model_selection_id=model_selection_id,
            job_run_id=job_run_id,
            consumed_at=consumed_at,
        )

    async def get_project_token_usage_stats_async(self) -> list[TokenUsageStatsModel]:
        """Get monthly token usage stats aggregated by consumed_at."""
        return await asyncio.to_thread(self.get_project_token_usage_stats)

    async def get_project_daily_token_usage_stats_async(
        self, month: str | None = None
    ) -> list[TokenUsageDailyStatsModel]:
        """Get daily token usage stats aggregated by consumed_at."""
        return await asyncio.to_thread(self.get_project_daily_token_usage_stats, month)

    # =========================================================================
    # Sync Implementation
    # =========================================================================

    def _record_token_usage_delta_sync(
        self,
        *,
        chat_session_id: UUID | str,
        project_id: UUID | str,
        previous_inbound: int,
        previous_outbound: int,
        current_inbound: int,
        current_outbound: int,
        model_selection_id: str | None = None,
        job_run_id: UUID | str | None = None,
        consumed_at: datetime | None = None,
    ) -> None:
        """Record token usage delta (sync implementation).

        Calculates the difference between current and previous cumulative totals
        and stores as an incremental record.
        """
        # Calculate delta
        delta_inbound = current_inbound - previous_inbound
        delta_outbound = current_outbound - previous_outbound

        # Validate deltas - negative values indicate counter reset or inconsistency
        if delta_inbound < 0 or delta_outbound < 0:
            logger.warning(
                "Token usage counter regression detected for session %s: "
                "previous=(%d, %d), current=(%d, %d), delta=(%d, %d). "
                "This may indicate a counter reset or inconsistent state. Skipping recording.",
                chat_session_id,
                previous_inbound,
                previous_outbound,
                current_inbound,
                current_outbound,
                delta_inbound,
                delta_outbound,
            )
            return

        # Only record if there's actual token usage (both zero means no change)
        if delta_inbound == 0 and delta_outbound == 0:
            logger.debug(
                "No token usage delta to record for session %s",
                chat_session_id,
            )
            return

        if consumed_at is None:
            consumed_at = utc_now()

        with self._session_scope() as session:
            record = ChatSessionTokenUsage(
                chat_session_id=ensure_uuid(chat_session_id),
                project_id=ensure_uuid(project_id),
                job_run_id=ensure_uuid(job_run_id) if job_run_id else None,
                model_selection_id=model_selection_id,
                tokens_inbound=delta_inbound,
                tokens_outbound=delta_outbound,
                consumed_at=consumed_at,
            )
            session.add(record)
            session.flush()

            logger.debug(
                "Recorded token usage for session %s: +%d inbound, +%d outbound at %s",
                chat_session_id,
                delta_inbound,
                delta_outbound,
                consumed_at,
            )

    def get_project_token_usage_stats(self) -> list[TokenUsageStatsModel]:
        """Get token usage statistics aggregated by month using consumed_at.

        Returns monthly token totals grouped by consumption date, not session creation date.
        """

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
        """Get daily token usage statistics aggregated by day using consumed_at.

        Args:
            month: Optional month filter (YYYY-MM format). Defaults to current month.

        Returns daily token totals grouped by consumption date.
        """

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
