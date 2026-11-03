"""Freshness/trust gates derived from OKF v0.2 attestation fields.

OKF v0.2 makes ``stale_after``, ``status``, and ``verified`` first-class so a
consumer can decide how much to trust a concept. These helpers apply those
signals to the projected ``KnowledgeSearchHit`` metadata (produced by
:func:`kontext.okf.concept_to_index_document`) so retrieval can skip stale or
deprecated knowledge before it reaches the agent.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: Concept statuses that should never surface to retrieval because they are
#: awaiting human review (agent proposals / drafts) or explicitly retired.
#: ``proposed`` is Kontext's legacy alias for the OKF ``draft`` lifecycle value.
_UNVERIFIED_OR_RETIRED_STATUSES = frozenset(
    {"proposed", "draft", "pending", "deprecated", "retired", "archived"}
)


def is_concept_fresh(
    metadata: Mapping[str, object],
    *,
    now: date | None = None,
) -> bool:
    """Return ``True`` when a concept's attestation says it is still usable.

    A concept is considered unusable when:

    * ``status`` is a proposal awaiting review or a deprecated lifecycle value, or
    * ``stale_after`` is set and in the past relative to ``now``.

    Concepts without these fields are treated as fresh (the OKF spec makes them
    optional), so hand-authored notes with no attestation still surface.
    """
    status = metadata.get("status")
    if isinstance(status, str) and status.lower() in _UNVERIFIED_OR_RETIRED_STATUSES:
        return False

    stale_after_raw = metadata.get("stale_after")
    if isinstance(stale_after_raw, str):
        reference = now or datetime.now(UTC).date()
        try:
            # OKF v0.2 uses ISO 8601 datetimes (``2026-12-31T00:00:00Z``);
            # v0.1 used plain dates (``2026-12-31``). Accept both.
            stale_after = date.fromisoformat(stale_after_raw[:10])
        except ValueError:
            return True
        if stale_after < reference:
            return False
    return True


def filter_fresh_hits(
    hits: Sequence[Mapping[str, object]],
    *,
    now: date | None = None,
) -> list[Mapping[str, object]]:
    """Drop hits whose projected metadata marks them stale or deprecated."""
    return [hit for hit in hits if is_concept_fresh(hit, now=now)]
