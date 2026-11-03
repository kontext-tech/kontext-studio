"""Provider contract tests for the worker-facing runtime ports.

These tests express the *behavioral contract* of the ports a worker depends
on — job-run lifecycle, idempotent terminal updates, batched logs, durable
result storage, run provenance, and session invalidation — against any
runtime provider composition. Today the matrix contains the local
(direct-access) provider; when a client-backed (API/HTTP) provider exists,
add a fixture exposing the same harness surface and the entire suite
applies unchanged.

Run creation is deliberately *not* part of the port (the durable run layer
owns it), so each harness seeds runs through its own composition-specific
mechanism.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from kontext.common.jobs.trigger_actor import agent_actor
from kontext.data.database import get_engine, get_session_factory, get_sync_db_session
from kontext.data.models import Project
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.runtime.providers.local import LocalRuntimeProvider
from kontext.schema import (
    CreateJobRequest,
    DataColumn,
    DataTable,
    FileFormatType,
    JobRetryStrategy,
    JobRunStatus,
    JobTriggerType,
    LogLevel,
    QueryResponse,
)
from kontext.storage import clear_storage_provider_cache


def _clear_runtime_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    clear_storage_provider_cache()


@dataclass
class LocalProviderHarness:
    """Composition-specific seeding for the local (direct-access) provider."""

    project_id: str
    provider: LocalRuntimeProvider = field(init=False)

    def __post_init__(self) -> None:
        self.provider = LocalRuntimeProvider(self.project_id)

    async def create_job_run(self, name: str) -> tuple[str, str]:
        """Seed a job and a queued run; returns (job_id, run_id)."""
        from kontext.data import JobDataService, JobRunDataService

        job_service = JobDataService(self.project_id)
        run_service = JobRunDataService(self.project_id)
        job = await job_service.create_job_async(
            CreateJobRequest(
                name=name,
                type="python.jobs.ContractProbe",
                description="Provider contract test probe",
                timeout=300,
                is_enabled=True,
                retry_strategy=JobRetryStrategy.NONE,
                retry_limit=0,
            ),
            created_by="contract-test",
        )
        run = await run_service.create_run_async(
            job_id=UUID(str(job.id)),
            parameters="{}",
            status="Queued",
            triggered_by=agent_actor("contract-test"),
            trigger_type=JobTriggerType.INTERACTIVE,
        )
        return str(job.id), str(run.id)

    async def attach_run_context(
        self,
        run_id: str,
        *,
        chat_session_id: UUID | None = None,
        root_run_id: UUID | str | None = None,
    ) -> None:
        from kontext.data import ExecutionRunContextDataService

        await ExecutionRunContextDataService(self.project_id).upsert_context_async(
            run_id=UUID(run_id),
            chat_session_id=chat_session_id,
            root_run_id=root_run_id,
        )

    async def read_run_logs(self, run_id: str) -> list[Any]:
        from kontext.data import JobRunLogDataService

        return await JobRunLogDataService(self.project_id).get_logs_for_run_async(UUID(run_id))

    async def claim_next_run(self, worker: str = "contract-worker") -> str | None:
        """Claim the project's oldest queued run through the claim-transport port."""
        from kontext.engine.transports import (
            LocalDbJobRunClaimTransport,
            StaticProjectIds,
        )

        transport = LocalDbJobRunClaimTransport(StaticProjectIds((self.project_id,)))
        claim = await transport.claim_next(worker_identifier=worker)
        return claim.run_id if claim else None

    def expire_run_lease(self, run_id: str, *, seconds_in_past: float = 10.0) -> None:
        """Backdate a run's lease so the reaper sees it as lapsed (local seeding)."""
        from datetime import timedelta

        from kontext.common.utils.datetime_utils import utc_now
        from kontext.data.database import get_sync_db_session
        from kontext.data.models import JobRun

        expired = utc_now() - timedelta(seconds=seconds_in_past)
        with get_sync_db_session() as session:
            session.execute(
                update(JobRun).where(JobRun.id == UUID(run_id)).values(lease_expires_at=expired)
            )
            # get_sync_db_session does not auto-commit (only the data layer's
            # _session_scope does), so the seeding write is explicit.
            session.commit()

    async def reclaim_expired_leases(self, *, max_attempts: int, reason: str) -> list[str]:
        """Run the reaper's reclaim over this project (local seeding)."""
        from kontext.data import JobRunDataService

        reclaimed = await JobRunDataService(self.project_id).reclaim_expired_run_leases_async(
            reason=reason, max_attempts=max_attempts
        )
        return [str(run_id) for run_id in reclaimed]


@pytest.fixture()
def harness(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_url = f"sqlite:///{tmp_path / 'kontext.db'}"
    monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(tmp_path / "storage"))

    with (
        patch(
            "kontext.runtime.local.config.get_local_database_url",
            return_value=db_url,
        ),
        patch(
            "kontext.runtime.local.auth.get_local_jwt_secret",
            return_value="test-local-secret",
        ),
    ):
        _clear_runtime_caches()
        try:
            initialize_local_mode()
            with get_sync_db_session() as session:
                project_id = session.execute(
                    select(Project.id).where(Project.project_code == "local")
                ).scalar_one()
            yield LocalProviderHarness(project_id=str(project_id))
        finally:
            _clear_runtime_caches()


async def test_job_run_lifecycle_roundtrip(harness: LocalProviderHarness) -> None:
    """The port supports the full worker run lifecycle: claim fields, logs, terminal state."""
    from kontext.common.protocols import JobRunLogEntry

    service = harness.provider.get_job_run_service()
    assert service is not None

    job_id, run_id = await harness.create_job_run("contract-lifecycle")

    run = await service.get_job_run(run_id, harness.project_id)
    assert run is not None and run.status == JobRunStatus.QUEUED

    job = await service.get_job(job_id, harness.project_id)
    assert job is not None and job.type == "python.jobs.ContractProbe"

    await service.update_worker(run_id, harness.project_id, "contract-worker")
    await service.update_progress(run_id, harness.project_id, 42)
    await service.add_log(run_id, harness.project_id, LogLevel.INFORMATION, "single entry")
    await service.add_log_batch(
        run_id,
        harness.project_id,
        [
            JobRunLogEntry(level=LogLevel.DEBUG, message="batch entry 1"),
            JobRunLogEntry(level=LogLevel.WARNING, message="batch entry 2", data={"k": "v"}),
        ],
    )
    await service.update_status(
        run_id, harness.project_id, JobRunStatus.SUCCEEDED, result_data={"ok": True}
    )

    run = await service.get_job_run(run_id, harness.project_id)
    assert run is not None
    assert run.status == JobRunStatus.SUCCEEDED
    assert run.progress == 42
    assert run.worker == "contract-worker"
    assert run.result_data is not None
    assert json.loads(run.result_data) == {"ok": True}

    logs = await harness.read_run_logs(run_id)
    # The port does not promise log ordering; the contract is that every
    # entry (single and batched) is durably persisted.
    assert sorted(log.message for log in logs) == [
        "batch entry 1",
        "batch entry 2",
        "single entry",
    ]
    assert run.completed_at is not None


async def test_terminal_update_status_is_idempotent(
    harness: LocalProviderHarness,
) -> None:
    """At-least-once delivery: replaying an identical terminal update changes nothing."""
    service = harness.provider.get_job_run_service()
    assert service is not None

    _, run_id = await harness.create_job_run("contract-idempotent")

    await service.update_status(
        run_id, harness.project_id, JobRunStatus.SUCCEEDED, result_data={"n": 1}
    )
    first = await service.get_job_run(run_id, harness.project_id)
    assert first is not None

    await service.update_status(
        run_id, harness.project_id, JobRunStatus.SUCCEEDED, result_data={"n": 1}
    )
    second = await service.get_job_run(run_id, harness.project_id)
    assert second is not None

    assert second.status == first.status == JobRunStatus.SUCCEEDED
    assert second.result_data == first.result_data
    assert second.completed_at == first.completed_at


async def test_first_terminal_outcome_wins(harness: LocalProviderHarness) -> None:
    """A late conflicting terminal write can never rewrite a recorded outcome."""
    service = harness.provider.get_job_run_service()
    assert service is not None

    _, run_id = await harness.create_job_run("contract-first-terminal")

    await service.update_status(
        run_id, harness.project_id, JobRunStatus.SUCCEEDED, result_data={"outcome": "success"}
    )
    await service.update_status(
        run_id,
        harness.project_id,
        JobRunStatus.FAILED,
        error_message="late conflicting write",
    )

    run = await service.get_job_run(run_id, harness.project_id)
    assert run is not None
    assert run.status == JobRunStatus.SUCCEEDED
    assert run.result_data is not None
    assert json.loads(run.result_data) == {"outcome": "success"}
    assert run.error_message is None


async def test_query_results_persist_through_file_service(
    harness: LocalProviderHarness,
) -> None:
    """Results materialize through the file port and are visible afterwards."""
    file_service = harness.provider.get_file_service()
    assert file_service is not None

    response = QueryResponse(
        result=DataTable(
            columns=[DataColumn(name="city", type="VARCHAR")],
            rows=[["cologne"], ["berlin"]],
            row_count=2,
        ),
        total_execution_time_ms=5,
        success=True,
        error_message=None,
        data_id=None,
        sql="select city from places",
    )

    file_id = await file_service.store_query_results_as_file(
        harness.project_id,
        response,
        name="Contract Result",
        chat_session_id=None,
    )
    assert file_id, "store_query_results_as_file must return a file id"

    assert await file_service.exists_by_id(harness.project_id, file_id)
    details = await file_service.get_file_details(harness.project_id, file_id)
    assert str(details.id) == file_id
    assert details.file_type == FileFormatType.DATATABLE


async def test_run_provenance_roundtrip(harness: LocalProviderHarness) -> None:
    """Provenance recorded at queue time is readable through the provider port."""
    provenance_service = harness.provider.get_execution_run_context_service()
    assert provenance_service is not None

    _, run_id = await harness.create_job_run("contract-provenance")
    assert await provenance_service.get_run_provenance(run_id) is None

    chat_session_id = uuid4()
    await harness.attach_run_context(run_id, chat_session_id=chat_session_id)

    provenance = await provenance_service.get_run_provenance(run_id)
    assert provenance is not None
    assert provenance.run_id == run_id
    assert provenance.chat_session_id == str(chat_session_id)
    assert provenance.parent_run_id is None
    assert provenance.root_run_id is None

    assert await provenance_service.get_run_provenance(uuid4()) is None


async def test_query_session_invalidation_contract(
    harness: LocalProviderHarness,
) -> None:
    """Catalog-structure changes invalidate exactly the sessions bound to the connection."""
    session_service = harness.provider.get_query_session_service()
    assert session_service is not None

    connection_id = uuid4()
    other_connection_id = uuid4()
    bound_session_id, _ = await session_service.create_query_session(
        harness.project_id,
        catalog_connection_id=connection_id,
        session_name="contract-bound",
    )
    unbound_session_id, _ = await session_service.create_query_session(
        harness.project_id,
        catalog_connection_id=other_connection_id,
        session_name="contract-unbound",
    )

    invalidated = await session_service.invalidate_sessions_for_catalog_connection(
        harness.project_id, connection_id, reason="Contract test"
    )
    assert [str(session_id) for session_id in invalidated] == [bound_session_id]

    # Invalidated sessions are soft-deleted: a replay invalidates nothing.
    replayed = await session_service.invalidate_sessions_for_catalog_connection(
        harness.project_id, connection_id, reason="Contract test replay"
    )
    assert replayed == []

    _ = unbound_session_id


async def test_run_claim_stamps_lease_and_renewal_fences(
    harness: LocalProviderHarness,
) -> None:
    """A claim holds a lease only while its worker keeps renewing it."""
    service = harness.provider.get_job_run_service()
    assert service is not None

    _, run_id = await harness.create_job_run("contract-lease")

    claimed_run_id = await harness.claim_next_run()
    assert claimed_run_id == run_id

    run = await service.get_job_run(run_id, harness.project_id)
    assert run is not None
    assert run.status == JobRunStatus.DISPATCHED
    assert run.worker == "contract-worker"

    # The owning worker can extend its lease...
    assert await service.renew_lease(run_id, harness.project_id, "contract-worker") is True
    # ...but a different worker cannot renew someone else's claim (fencing).
    assert await service.renew_lease(run_id, harness.project_id, "contract-worker-2") is False


async def test_expired_lease_reclaims_then_deadletters(
    harness: LocalProviderHarness,
) -> None:
    """A lapsed lease requeues the same run; a crash-looping run is dead-lettered."""
    service = harness.provider.get_job_run_service()
    assert service is not None

    _, run_id = await harness.create_job_run("contract-lease-reclaim")

    # Reclaim #1 (attempt_count 0 -> 1, back to Queued for another claim).
    assert await harness.claim_next_run() == run_id
    harness.expire_run_lease(run_id)
    assert await harness.reclaim_expired_leases(max_attempts=2, reason="lease expired") == [run_id]
    run = await service.get_job_run(run_id, harness.project_id)
    assert run is not None
    assert run.status == JobRunStatus.QUEUED
    assert run.attempt_count == 1
    assert run.worker is None

    # Reclaim #2 (attempt 1 -> 2) still requeues at the cap boundary...
    assert await harness.claim_next_run() == run_id
    harness.expire_run_lease(run_id)
    assert await harness.reclaim_expired_leases(max_attempts=2, reason="lease expired") == [run_id]
    run = await service.get_job_run(run_id, harness.project_id)
    assert run is not None
    assert run.attempt_count == 2

    # ...and reclaim #3 exceeds the budget: dead-lettered, not retried forever.
    assert await harness.claim_next_run() == run_id
    harness.expire_run_lease(run_id)
    assert await harness.reclaim_expired_leases(max_attempts=2, reason="lease expired") == [run_id]
    run = await service.get_job_run(run_id, harness.project_id)
    assert run is not None
    assert run.status == JobRunStatus.DEADLETTERED
    assert run.error_message == "lease expired"

    # A dead-lettered run cannot be claimed again.
    assert await harness.claim_next_run() is None
