"""Tests for job-run display summaries derived from job parameters."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from kontext.jobs import job_run_summary
from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_run_summary import (
    build_display_summary,
    enrich_job_run_display_summary,
)
from kontext.schema import (
    JobCategory,
    JobModel,
    JobRetryStrategy,
    JobRunModel,
    JobRunStatus,
)


class _SummaryParams(BaseJobParams):
    sql: str | None = None
    code: str | None = None


@job(
    job_type="python.jobs.SummaryProbeJob",
    name="Summary Probe Job",
    description="Test-only job used to exercise display summaries.",
    category=JobCategory.DATAPROCESSING,
    params_model=_SummaryParams,
    required_permissions=[],
    display_parameter="sql",
    is_system_job=True,
)
class _SummaryProbeJob(BasePythonJob[_SummaryParams]):
    async def execute_job(self, context, parameters):  # pragma: no cover - not run
        raise NotImplementedError


class _FakeRegistry:
    def get_job_class(self, job_type: str):
        if job_type == _SummaryProbeJob.get_job_type():
            return _SummaryProbeJob
        return None


@pytest.fixture(autouse=True)
def _patch_registry(monkeypatch):
    monkeypatch.setattr(job_run_summary, "get_job_registry", _FakeRegistry)


def _job_run(*, parameters: str | None, job_parameters: str | None = None) -> JobRunModel:
    created_at = datetime(2024, 1, 1, tzinfo=UTC)
    job_id = str(uuid4())
    job = JobModel(
        id=job_id,
        name="Summary Probe Job",
        type=_SummaryProbeJob.get_job_type(),
        timeout=60,
        is_enabled=True,
        retry_strategy=JobRetryStrategy.NONE,
        retry_limit=0,
        date_created=created_at,
        total_runs=0,
        successful_runs=0,
        failed_runs=0,
        in_progress_runs=0,
        parameters=job_parameters,
    )
    return JobRunModel(
        id=str(uuid4()),
        job_id=job_id,
        status=JobRunStatus.QUEUED,
        attempt_count=1,
        created_at=created_at,
        parameters=parameters,
        job=job,
    )


def test_decorator_records_display_parameter():
    assert _SummaryProbeJob.get_display_parameter() == "sql"


def test_build_display_summary_returns_requested_field():
    summary = build_display_summary(
        _SummaryProbeJob.get_job_type(), '{"sql": "SELECT 1", "code": "print(1)"}'
    )
    assert summary == "SELECT 1"


def test_build_display_summary_unknown_type_returns_none():
    assert build_display_summary("python.jobs.UnknownJob", '{"sql": "SELECT 1"}') is None


def test_build_display_summary_invalid_json_returns_none():
    assert build_display_summary(_SummaryProbeJob.get_job_type(), "not-json") is None


def test_build_display_summary_non_object_returns_none():
    assert build_display_summary(_SummaryProbeJob.get_job_type(), '"just a string"') is None


def test_build_display_summary_missing_value_returns_none():
    assert build_display_summary(_SummaryProbeJob.get_job_type(), '{"code": "print(1)"}') is None


def test_build_display_summary_blank_value_returns_none():
    assert build_display_summary(_SummaryProbeJob.get_job_type(), '{"sql": "   "}') is None


def test_enrich_job_run_display_summary_sets_field_from_run_parameters():
    run = _job_run(parameters='{"sql": "SELECT 1"}')
    enriched = enrich_job_run_display_summary(run)
    assert enriched.display_summary == "SELECT 1"


def test_enrich_job_run_display_summary_falls_back_to_job_parameters():
    run = _job_run(parameters=None, job_parameters='{"sql": "SELECT 2"}')
    enriched = enrich_job_run_display_summary(run)
    assert enriched.display_summary == "SELECT 2"


def test_enrich_job_run_display_summary_keeps_existing_value():
    run = _job_run(parameters='{"sql": "SELECT 1"}')
    run.display_summary = "Already set"
    enriched = enrich_job_run_display_summary(run)
    assert enriched.display_summary == "Already set"
