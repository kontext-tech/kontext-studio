"""Unit tests for ExecutionRunService notebook-run discovery (`list_recent_notebook_python_runs_async`)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from kontext.execution.runs import ExecutionRunService
from kontext.schema import (
    JobModel,
    JobRetryStrategy,
    JobRunModel,
    JobRunStatus,
)

_NOTEBOOK_JOB_TYPE = "python.jobs.ExecuteNotebookPythonJob"
_NOTEBOOK_ID = "bd994563-232b-454f-a5b3-2f7d3d33cb2c"


class _FakePaged:
    def __init__(self, items: list[JobRunModel]) -> None:
        self.items = items


class _FakeJobRunDataService:
    """Captures paging arguments and returns queued item pages."""

    pages: list[list[JobRunModel]] = []

    def __init__(self, project_id: UUID) -> None:
        self.project_id = project_id

    async def get_runs_paginated_async(
        self,
        *,
        page_index: int = 1,
        page_size: int = 20,
        job_id: UUID | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        owner_id: UUID | None = None,
    ) -> _FakePaged:
        idx = page_index - 1
        return _FakePaged(self.pages[idx] if 0 <= idx < len(self.pages) else [])


def _job(job_type: str = _NOTEBOOK_JOB_TYPE) -> JobModel:
    return JobModel(
        id=str(uuid4()),
        name="Execute Notebook Python",
        type=job_type,
        timeout=3,
        is_enabled=True,
        retry_strategy=JobRetryStrategy("None"),
        retry_limit=0,
        date_created=datetime(2026, 10, 17, 9, 0),
        total_runs=0,
        successful_runs=0,
        failed_runs=0,
        in_progress_runs=0,
    )


def _job_run(
    *,
    job_type: str = _NOTEBOOK_JOB_TYPE,
    notebook_id: str | None = _NOTEBOOK_ID,
    block_id: str | None = None,
    pascal_keys: bool = True,
    chat_session_id: str | None = None,
    attach_job: bool = True,
) -> JobRunModel:
    params: dict[str, Any] = {}
    if notebook_id is not None:
        params["NotebookId" if pascal_keys else "notebook_id"] = notebook_id
    if block_id is not None:
        params["BlockId" if pascal_keys else "block_id"] = block_id
    if chat_session_id is not None:
        params["ChatSessionId" if pascal_keys else "chat_session_id"] = chat_session_id
    return JobRunModel(
        id=str(uuid4()),
        job_id=str(uuid4()),
        status=JobRunStatus.SUCCEEDED,
        attempt_count=1,
        created_at=datetime(2026, 10, 18, 10, 0),
        parameters=json.dumps(params) if params else None,
        job=_job(job_type) if attach_job else None,
    )


def _install(monkeypatch: pytest.MonkeyPatch, pages: list[list[JobRunModel]]) -> None:
    _FakeJobRunDataService.pages = pages
    monkeypatch.setattr("kontext.execution.runs.JobRunDataService", _FakeJobRunDataService)


async def test_matches_notebook_job_runs_with_pascal_and_snake_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runs are matched by job type plus the persisted notebook id (either key style)."""
    runs = [
        _job_run(block_id="b1", chat_session_id="c1"),  # PascalCase (persisted form)
        _job_run(pascal_keys=False),  # snake_case tolerated
        _job_run(notebook_id="11111111-2222-3333-4444-555555555555"),  # other notebook
        _job_run(job_type="python.jobs.ExecutePythonScriptJob"),  # other job type
        _job_run(attach_job=False),  # detached job record
    ]
    _install(monkeypatch, [runs])

    matches = await ExecutionRunService().list_recent_notebook_python_runs_async(
        project_id=uuid4(),
        notebook_id=_NOTEBOOK_ID,
        limit=10,
    )

    assert [str(match["runId"]) for match in matches] == [
        runs[0].id,
        runs[1].id,
    ]
    assert matches[0]["blockId"] == "b1"
    assert matches[0]["chatSessionId"] == "c1"
    assert matches[0]["createdAt"] is not None
    assert matches[0]["status"]


async def test_stops_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discovery is bounded by ``limit`` regardless of how many runs match."""
    page = [_job_run(block_id=f"b{index}") for index in range(8)]
    _install(monkeypatch, [page])

    matches = await ExecutionRunService().list_recent_notebook_python_runs_async(
        project_id=uuid4(),
        notebook_id=_NOTEBOOK_ID,
        limit=3,
    )

    assert len(matches) == 3


async def test_skips_runs_without_notebook_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """Job-type matches without notebook params in ``parameters`` are ignored."""
    run = _job_run(notebook_id=None)
    _install(monkeypatch, [[run]])

    matches = await ExecutionRunService().list_recent_notebook_python_runs_async(
        project_id=uuid4(),
        notebook_id=_NOTEBOOK_ID,
        limit=10,
    )

    assert matches == []


async def test_pages_until_matches_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discovery keeps paging while nothing matches and items keep arriving."""
    filler = [
        _job_run(job_type="python.jobs.ExecutePythonScriptJob", notebook_id=None) for _ in range(50)
    ]
    match = _job_run(block_id="b9")
    _install(
        monkeypatch,
        [
            filler,  # full page of unrelated runs
            [match],  # short page: terminal, but the match is on it
        ],
    )

    matches = await ExecutionRunService().list_recent_notebook_python_runs_async(
        project_id=uuid4(),
        notebook_id=_NOTEBOOK_ID,
        limit=10,
    )

    assert [str(item["runId"]) for item in matches] == [match.id]
