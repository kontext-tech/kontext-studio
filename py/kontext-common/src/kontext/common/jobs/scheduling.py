"""Cross-cutting scheduling helpers shared across packages."""

from datetime import UTC, datetime

from croniter import croniter

from ..utils.datetime_utils import utc_now


class CronParser:
    """Utility class for CRON expression operations."""

    @staticmethod
    def is_valid(expression: str) -> bool:
        try:
            croniter(expression)
            return True
        except (ValueError, KeyError):
            return False

    @staticmethod
    def get_next_run(expression: str, base_time: datetime | None = None) -> datetime:
        try:
            base = base_time or utc_now()
            if base.tzinfo is None:
                base = base.replace(tzinfo=UTC)
            cron = croniter(expression, base)
            next_time = cron.get_next(datetime)
            if next_time.tzinfo is None:
                next_time = next_time.replace(tzinfo=UTC)
            return next_time
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Invalid CRON expression: {expression}") from exc

    @staticmethod
    def get_previous_run(expression: str, base_time: datetime | None = None) -> datetime:
        try:
            base = base_time or utc_now()
            if base.tzinfo is None:
                base = base.replace(tzinfo=UTC)
            cron = croniter(expression, base)
            previous_time = cron.get_prev(datetime)
            if previous_time.tzinfo is None:
                previous_time = previous_time.replace(tzinfo=UTC)
            return previous_time
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Invalid CRON expression: {expression}") from exc

    @staticmethod
    def is_due(expression: str, last_run: datetime | None, now: datetime | None = None) -> bool:
        current = now or utc_now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)

        if last_run is None:
            return True

        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=UTC)

        next_run = CronParser.get_next_run(expression, last_run)
        return next_run <= current

    @staticmethod
    def get_next_n_runs(
        expression: str, n: int = 5, base_time: datetime | None = None
    ) -> list[datetime]:
        base = base_time or utc_now()
        if base.tzinfo is None:
            base = base.replace(tzinfo=UTC)

        cron = croniter(expression, base)
        runs: list[datetime] = []
        for _ in range(n):
            next_time = cron.get_next(datetime)
            if next_time.tzinfo is None:
                next_time = next_time.replace(tzinfo=UTC)
            runs.append(next_time)
        return runs
