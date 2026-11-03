"""Unit tests for the shared result-persistence policy."""

from __future__ import annotations

from kontext.common.query.result_materialization import should_persist_result


def test_explicit_reuse_always_persists():
    assert should_persist_result(row_count=0, store_as_resource=True) is True


def test_without_threshold_and_flag_never_persists():
    assert should_persist_result(row_count=10_000) is False


def test_persists_when_rows_exceed_threshold():
    assert should_persist_result(row_count=501, threshold_rows=500) is True


def test_does_not_persist_at_or_below_threshold():
    assert should_persist_result(row_count=500, threshold_rows=500) is False
    assert should_persist_result(row_count=1, threshold_rows=500) is False
