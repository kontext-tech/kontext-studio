"""Unit tests for the result-store retention rule."""

from __future__ import annotations

from datetime import timedelta

from kontext.common.query.retention import RetentionPolicy
from kontext.common.utils.datetime_utils import utc_now


def _policy() -> RetentionPolicy:
    return RetentionPolicy(ttl=timedelta(days=1))


def test_referenced_stores_are_never_reclaimed():
    now = utc_now()
    reclaim = _policy().select_reclaimable(
        candidate_names=["a"],
        referenced_names={"a"},
        modified_at_by_name={"a": now - timedelta(days=30)},
        now=now,
    )
    assert reclaim == []


def test_unreferenced_and_expired_is_reclaimed():
    now = utc_now()
    reclaim = _policy().select_reclaimable(
        candidate_names=["a"],
        referenced_names=set(),
        modified_at_by_name={"a": now - timedelta(days=2)},
        now=now,
    )
    assert reclaim == ["a"]


def test_unreferenced_but_fresh_is_kept():
    now = utc_now()
    reclaim = _policy().select_reclaimable(
        candidate_names=["a"],
        referenced_names=set(),
        modified_at_by_name={"a": now - timedelta(hours=1)},
        now=now,
    )
    assert reclaim == []


def test_missing_mtime_is_treated_as_old():
    now = utc_now()
    reclaim = _policy().select_reclaimable(
        candidate_names=["a"],
        referenced_names=set(),
        modified_at_by_name={"a": None},
        now=now,
    )
    assert reclaim == ["a"]


def test_disabled_policy_reclaims_nothing():
    policy = RetentionPolicy(enabled=False)
    reclaim = policy.select_reclaimable(
        candidate_names=["a"],
        referenced_names=set(),
        modified_at_by_name={"a": None},
    )
    assert reclaim == []
