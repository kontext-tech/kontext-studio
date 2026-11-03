"""Retention rule for content-addressed result stores.

A materialized result (Parquet row store) is referenced by the ``.dt``
descriptors that point at it; a store with no live descriptor is garbage. A
store may also be shared by several descriptors (content addressing dedupes
identical results), so deletion must be driven by *references*, not by the age
of any single descriptor.

The rule is pure (no I/O) so it can be unit-tested and shared by the local
worker sweeper.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from kontext.common.utils.datetime_utils import utc_now

__all__ = ["RetentionPolicy"]


@dataclass(frozen=True)
class RetentionPolicy:
    """How long an unreferenced result store is retained before reclamation."""

    ttl: timedelta = timedelta(days=1)
    enabled: bool = True

    def select_reclaimable(
        self,
        *,
        candidate_names: list[str],
        referenced_names: set[str],
        modified_at_by_name: dict[str, datetime | None],
        now: datetime | None = None,
    ) -> list[str]:
        """Return candidate store names that are unreferenced and past their TTL.

        A candidate is reclaimable only when nothing references it *and* it is
        older than the TTL (the TTL also absorbs the brief window where a store
        has been written but its descriptor is not yet visible).
        """
        if not self.enabled:
            return []

        current = now or utc_now()
        reclaimable: list[str] = []
        for name in candidate_names:
            if name in referenced_names:
                continue
            modified_at = modified_at_by_name.get(name)
            if modified_at is not None and modified_at.tzinfo is None:
                modified_at = modified_at.replace(tzinfo=current.tzinfo)
            if modified_at is not None and (current - modified_at) < self.ttl:
                continue
            reclaimable.append(name)
        return reclaimable
