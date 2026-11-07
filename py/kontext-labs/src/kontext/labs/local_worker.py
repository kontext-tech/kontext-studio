"""
Local job worker (supervisor) for Kontext.

Runs as its own process (``kontext worker``), separate from the API
server. The worker is a *supervisor*: it discovers queued work through an
:class:`~kontext.common.jobs.transport.IJobRunClaimTransport` (the local DB
poll), then delegates execution. It never executes job code itself.

This mirrors how Celery/RQ (worker) and uvicorn ``--workers`` separate job
execution from the request process: a hung or crashed job can never wedge the
API, and tests that only exercise the API never start worker threads or child
processes at all.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import signal
from datetime import UTC, timedelta
from pathlib import Path

from kontext.common.jobs.transport import IJobRunClaimTransport
from kontext.engine.adapters import LocalJobRunService
from kontext.engine.transports import LocalDbJobRunClaimTransport
from kontext.execution.scheduling import handle_run_status_change_hook
from kontext.jobs.job_execution_service import JobExecutionService
from kontext.runtime.providers.local import LocalRuntimeProvider

from .sqlite_compat import ensure_supported_sqlite

logger = logging.getLogger(__name__)

# How often (seconds) the worker checks for queued runs when idle. Kept short
# because interactive notebook/chat execution enqueues a run and polls for the
# worker to pick it up; a long interval would add that latency to every cell.
_POLL_INTERVAL = float(os.getenv("KONTEXT_LOCAL_WORKER_POLL_INTERVAL", "0.5"))

# How many runs the worker executes concurrently. Bounded so a slow job cannot
# block every interactive cell, but low so local CPU/memory stay sane.
_DEFAULT_CONCURRENCY = 2


def _resolve_concurrency() -> int:
    """Return the configured worker concurrency (default 2, invalid -> default)."""
    raw = os.getenv("KONTEXT_LOCAL_WORKER_CONCURRENCY")
    if not raw:
        return _DEFAULT_CONCURRENCY
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid KONTEXT_LOCAL_WORKER_CONCURRENCY=%r; using default", raw)
        return _DEFAULT_CONCURRENCY
    return value if value >= 1 else _DEFAULT_CONCURRENCY


# How often the worker checks whether session kernels still map to live sessions.
_SESSION_REAP_INTERVAL_SECONDS = float(os.getenv("KONTEXT_LOCAL_SESSION_REAP_INTERVAL", "60.0"))

# How often (seconds) the worker reclaims job runs whose claim lease lapsed
# (worker crashed mid-run, the DB-poll analogue of a queue visibility-timeout
# expiry). Reclaimed runs return to Queued for another claim; runs that keep
# outliving their lease are dead-lettered after a budget.
_RUN_LEASE_REAP_INTERVAL_SECONDS = float(os.getenv("KONTEXT_LOCAL_RUN_LEASE_REAP_INTERVAL", "60.0"))

# How often the worker reclaims persistent DuckDB session files whose DB row is
# gone (soft-deleted). Invalidation marks rows but never removes files, so a
# periodic sweeper keeps the sessions directory from growing without bound.
_SESSION_FILE_SWEEP_INTERVAL_SECONDS = float(
    os.getenv("KONTEXT_LOCAL_SESSION_FILE_SWEEP_INTERVAL", "3600.0")
)
# A session file younger than this is never swept: it may belong to an
# in-flight initialization whose DB row has not been observed yet.
_SESSION_FILE_SWEEP_GRACE_SECONDS = float(
    os.getenv("KONTEXT_LOCAL_SESSION_FILE_SWEEP_GRACE", "600.0")
)

# How long an unreferenced materialized row store is retained before reclamation.
# Unlike session files, this is a data-retention window: a user who reopens a
# chat within the window still finds the full rows.
_RESULT_STORE_RETENTION = timedelta(
    seconds=float(os.getenv("KONTEXT_LOCAL_RESULT_STORE_RETENTION", "86400"))
)


def _expected_session_db_names(project_id: str) -> set[str]:
    """Return the ``{session_id}.db`` names for every live query session."""
    from uuid import UUID

    from sqlalchemy import select

    from kontext.data.database import get_sync_db_session
    from kontext.data.models import QuerySession

    with get_sync_db_session() as db:
        rows = (
            db.execute(
                select(QuerySession.id).where(
                    QuerySession.project_id == UUID(project_id),
                    QuerySession.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )
    return {f"{row}.db" for row in rows}


def _sweep_project_session_files(project_id: str, *, now: float | None = None) -> int:
    """Delete persisted session DB files that no live query session references."""
    import time

    from kontext.common.query.session_storage import get_project_sessions_directory

    now = now if now is not None else time.time()
    sessions_dir = Path(get_project_sessions_directory(project_id))
    if not sessions_dir.is_dir():
        return 0

    expected = _expected_session_db_names(project_id)
    removed = 0
    for path in sessions_dir.iterdir():
        if not path.is_file():
            continue
        # DuckDB WAL companions share the base name; clean both.
        base = path.name.removesuffix(".wal")
        if base in expected:
            continue
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age < _SESSION_FILE_SWEEP_GRACE_SECONDS:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError as exc:
            logger.warning("Failed to remove orphan session file %s: %s", path, exc)
    return removed


async def _sweep_orphan_session_files() -> int:
    """Reclaim orphaned session files across every project."""
    project_ids = await _list_project_ids()
    total = 0
    for project_id in project_ids:
        try:
            total += await asyncio.to_thread(_sweep_project_session_files, project_id)
        except Exception:
            logger.exception("Failed to sweep session files for project %s", project_id)
    return total


def _referenced_result_stores(project_id: str) -> set[str]:
    """Return ``{fingerprint}.parquet`` names referenced by any live ``.dt`` file."""
    import json
    from uuid import UUID

    from sqlalchemy import select

    from kontext.common.utils.file_storage import DATATABLE_PROJECT_FILE_PREFIX
    from kontext.data.database import get_sync_db_session
    from kontext.data.models import ProjectFile

    referenced: set[str] = set()
    with get_sync_db_session() as db:
        rows = (
            db.execute(
                select(ProjectFile.uri).where(
                    ProjectFile.project_id == UUID(project_id),
                    ProjectFile.prefix == DATATABLE_PROJECT_FILE_PREFIX,
                    ProjectFile.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )

    from kontext.storage import get_storage_provider

    provider = get_storage_provider()
    for uri in rows:
        if not uri:
            continue
        try:
            content = (provider.resolve_path(uri)).read_text(encoding="utf-8")
            metadata = json.loads(content).get("metadata") or {}
            data_path = metadata.get("dataPath")
        except Exception:
            continue
        if data_path:
            referenced.add(Path(data_path).name)
    return referenced


async def _sweep_project_result_stores(project_id: str, *, now: float | None = None) -> int:
    """Delete content-addressed row stores that no live ``.dt`` descriptor references."""
    from datetime import datetime

    from kontext.common.query.retention import RetentionPolicy
    from kontext.common.utils.file_storage import RESULT_STORE_PROJECT_FILE_PREFIX
    from kontext.storage import get_storage_provider

    provider = get_storage_provider()

    referenced = await asyncio.to_thread(_referenced_result_stores, project_id)
    stored = await provider.list_files(
        project_id=project_id, prefix=RESULT_STORE_PROJECT_FILE_PREFIX
    )

    modified_at_by_name: dict[str, datetime | None] = {}
    by_name: dict[str, str] = {}
    for relative in stored:
        name = Path(relative).name
        by_name[name] = relative
        try:
            mtime = provider.resolve_path(relative).stat().st_mtime
            modified_at_by_name[name] = datetime.fromtimestamp(mtime, tz=UTC)
        except OSError:
            modified_at_by_name[name] = None

    policy = RetentionPolicy(ttl=_RESULT_STORE_RETENTION)
    reclaim = policy.select_reclaimable(
        candidate_names=list(by_name.keys()),
        referenced_names=referenced,
        modified_at_by_name=modified_at_by_name,
        now=datetime.fromtimestamp(now, tz=UTC) if now is not None else None,
    )

    removed = 0
    for name in reclaim:
        full = provider.resolve_path(by_name[name])
        try:
            full.unlink()
            removed += 1
        except OSError as exc:
            logger.warning("Failed to remove orphan row store %s: %s", by_name[name], exc)
    return removed


async def _sweep_orphan_result_stores() -> int:
    """Reclaim orphaned materialized row stores across every project."""
    project_ids = await _list_project_ids()
    total = 0
    for project_id in project_ids:
        try:
            total += await _sweep_project_result_stores(project_id)
        except Exception:
            logger.exception("Failed to sweep row stores for project %s", project_id)
    return total


async def _run_lease_reaper_loop(shutdown: asyncio.Event) -> None:
    """Periodically reclaim job runs whose claim lease lapsed.

    A killed or crashed worker leaves its claimed runs in ``Dispatched``/
    ``Running`` with a lapsed lease: a real queue would recover them via its
    visibility timeout; the DB-backed claim relies on the reaper instead.
    Each reclaimed run returns to ``Queued`` for another claim (attempt count
    incremented), or is dead-lettered once it exhausts the reclaim budget.
    """
    from kontext.common.constants import job_run_max_lease_reclaims
    from kontext.data import JobRunDataService

    max_reclaims = job_run_max_lease_reclaims()
    while not shutdown.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(shutdown.wait(), timeout=_RUN_LEASE_REAP_INTERVAL_SECONDS)
        if shutdown.is_set():
            return
        for project_id in await _list_project_ids():
            try:
                reclaimed = await JobRunDataService(project_id).reclaim_expired_run_leases_async(
                    reason=f"Run lease expired; reclaimed by {worker_identifier()}",
                    max_attempts=max_reclaims,
                )
            except Exception:
                logger.exception(
                    "Run-lease reclaim failed for project %s; will retry next interval",
                    project_id,
                )
                continue
            if reclaimed:
                logger.info(
                    "Reclaimed %d expired job-run lease(s) in project %s",
                    len(reclaimed),
                    project_id,
                )


def _session_still_exists(session_id: str) -> bool:
    """Return whether a session-kernel id still refers to a live session.

    Unknown or errored lookups return ``True`` so a transient DB error never
    reaps a kernel that is still in use.
    """
    from uuid import UUID

    from sqlalchemy import select

    from kontext.common.python_execution.kernel_identity import parse_session_kernel_id
    from kontext.data.database import get_sync_db_session
    from kontext.data.models import ChatSession, ProjectFile, QuerySession

    _MODELS = {
        "chat": ChatSession,
        "query": QuerySession,
        "notebook": ProjectFile,
    }

    try:
        ref = parse_session_kernel_id(session_id)
        model = _MODELS[ref.namespace]
        with get_sync_db_session() as db:
            found = db.execute(
                select(model.id).where(
                    model.id == UUID(ref.record_id),
                    model.is_deleted.is_(False),
                )
            ).scalar_one_or_none()
        return found is not None
    except Exception:
        logger.exception("Failed to resolve liveness for session %s", session_id)
        return True


def worker_identifier() -> str:
    """Return a stable identifier for this worker process."""
    return f"local-worker@{platform.node()}:{os.getpid()}"


async def _list_project_ids() -> list[str]:
    """Return all non-deleted project IDs from the local database."""
    try:
        from sqlalchemy import select

        from kontext.data.database import get_sync_db_session
        from kontext.data.models import Project

        def _query() -> list[str]:
            with get_sync_db_session() as session:
                rows = (
                    session.execute(
                        select(Project.id).where(Project.is_deleted == False)  # noqa: E712
                    )
                    .scalars()
                    .all()
                )
            return [str(r) for r in rows]

        return await asyncio.to_thread(_query)
    except Exception:
        logger.exception("Failed to list projects; will retry on next poll")
        return []


def _build_claim_transport() -> IJobRunClaimTransport:
    """Build the local claim transport (DB-poll) for this worker process."""
    return LocalDbJobRunClaimTransport(_list_project_ids)


async def _execute_run(project_id: str, run_id: str) -> None:
    """Execute a single job run in this worker process."""
    runtime_provider = LocalRuntimeProvider(project_id=project_id)
    job_run_service = LocalJobRunService(
        project_id, on_terminal_status=handle_run_status_change_hook
    )
    execution_svc = JobExecutionService(
        project_id=project_id,
        runtime_provider=runtime_provider,
        service=job_run_service,
    )
    try:
        await execution_svc.execute_job_run(run_id, worker_identifier=worker_identifier())
    except Exception:
        logger.exception("Job run %s failed", run_id)


async def _run_one(*, worker: str, transport: IJobRunClaimTransport) -> bool:
    """Claim one run and execute it, isolating errors. Returns True if claimed."""
    try:
        claimed = await transport.claim_next(worker_identifier=worker)
    except Exception:
        logger.exception("Error claiming a queued run")
        return False
    if claimed is None:
        return False
    logger.info("Executing queued job run %s (project=%s)", claimed.run_id, claimed.project_id)
    await _execute_run(claimed.project_id, claimed.run_id)
    return True


async def _worker_loop(
    *,
    worker: str,
    transport: IJobRunClaimTransport,
    shutdown: asyncio.Event,
) -> None:
    """One execution slot: repeatedly claim and run, idling when the queue is empty.

    Running ``concurrency`` of these gives bounded fan-out: a slow job occupies
    its slot, not the whole worker, so interactive cells on other sessions still
    get picked up.
    """
    while not shutdown.is_set():
        ran = await _run_one(worker=worker, transport=transport)
        if not ran:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(shutdown.wait(), timeout=_POLL_INTERVAL)


async def run_local_worker(
    *,
    shutdown: asyncio.Event | None = None,
    transport: IJobRunClaimTransport | None = None,
    concurrency: int | None = None,
) -> None:
    """Poll, claim, and execute queued runs until *shutdown* is set.

    Runs up to *concurrency* jobs at once (default
    ``KONTEXT_LOCAL_WORKER_CONCURRENCY`` or 2) so one slow job cannot block
    every interactive notebook/chat cell.
    """
    from kontext.kernel.registry import (
        get_session_kernel_manager,
        install_session_kernel_manager,
    )
    from kontext.kernel.sessions import SessionKernelManager
    from kontext.runtime.python_environment import resolve_managed_python_executable

    _shutdown = shutdown or asyncio.Event()
    _transport = transport or _build_claim_transport()
    _concurrency = max(1, concurrency if concurrency is not None else _resolve_concurrency())
    worker = worker_identifier()
    logger.info(
        "Local job worker started (id=%s, poll interval=%.1fs, concurrency=%d)",
        worker,
        _POLL_INTERVAL,
        _concurrency,
    )

    # Own the session kernels for this supervisor process. Jobs resolve the
    # manager through the registry, so consecutive cells share a namespace.
    # Kernels use the managed venv (numpy/pandas) when it exists.
    session_manager = get_session_kernel_manager() or SessionKernelManager(
        python_executable=resolve_managed_python_executable()
    )
    install_session_kernel_manager(session_manager)
    await session_manager.start()

    workers = [
        asyncio.create_task(
            _worker_loop(
                worker=worker,
                transport=_transport,
                shutdown=_shutdown,
            ),
            name=f"local-worker-slot-{slot}",
        )
        for slot in range(_concurrency)
    ]
    reaper = asyncio.create_task(_session_reaper_loop(session_manager, _shutdown))
    sweeper = asyncio.create_task(_session_file_sweeper_loop(_shutdown))
    run_lease_reaper = asyncio.create_task(_run_lease_reaper_loop(_shutdown))
    try:
        await _shutdown.wait()
    finally:
        for task in (*workers, reaper, sweeper, run_lease_reaper):
            task.cancel()
        await asyncio.gather(*workers, reaper, sweeper, run_lease_reaper, return_exceptions=True)
        await session_manager.shutdown()
        install_session_kernel_manager(None)


async def _session_reaper_loop(
    session_manager,
    shutdown: asyncio.Event,
    *,
    interval_seconds: float | None = None,
) -> None:
    """Periodically close session kernels whose session no longer exists."""
    interval = interval_seconds if interval_seconds is not None else _SESSION_REAP_INTERVAL_SECONDS
    while not shutdown.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(shutdown.wait(), timeout=interval)
        if shutdown.is_set():
            return
        with contextlib.suppress(Exception):
            await session_manager.reap_missing_sessions(_session_still_exists)


async def _session_file_sweeper_loop(
    shutdown: asyncio.Event,
    *,
    interval_seconds: float | None = None,
) -> None:
    """Periodically reclaim orphaned persistent query-session DuckDB files."""
    interval = (
        interval_seconds if interval_seconds is not None else _SESSION_FILE_SWEEP_INTERVAL_SECONDS
    )
    while not shutdown.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(shutdown.wait(), timeout=interval)
        if shutdown.is_set():
            return
        try:
            removed = await _sweep_orphan_session_files()
            if removed:
                logger.info("Reclaimed %d orphaned session file(s)", removed)
        except Exception:
            logger.exception("Session file sweep failed; will retry next interval")
        try:
            reclaimed = await _sweep_orphan_result_stores()
            if reclaimed:
                logger.info("Reclaimed %d orphaned row store(s)", reclaimed)
        except Exception:
            logger.exception("Row store sweep failed; will retry next interval")


def run_worker_process() -> None:
    """Blocking entry point for the standalone worker process.

    Initializes local mode (database, migrations, default data), installs
    SIGINT/SIGTERM handlers for graceful shutdown, and runs the poll loop.
    """
    # Direct `kontext worker` invocations bypass the server CLI guard.
    try:
        ensure_supported_sqlite()
    except RuntimeError as exc:
        raise SystemExit(f"❌ {exc}") from None

    from kontext.labs.worker_reaper import reap_orphaned_processes
    from kontext.runtime.local.bootstrap import initialize_local_mode

    try:
        reaped = reap_orphaned_processes()
    except Exception:
        logger.exception("Orphan reaping failed; continuing anyway")
        reaped = []
    if reaped:
        logger.warning(
            "Reaped previous-generation processes orphaned by a restarted server: %s",
            ", ".join(f"{orphan.kind} pid={orphan.pid}" for orphan in reaped),
        )

    initialize_local_mode()

    shutdown = asyncio.Event()

    def _request_shutdown(*_args: object) -> None:
        logger.info("Shutdown signal received; stopping after current run")
        shutdown.set()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, ValueError):
            loop.add_signal_handler(sig, _request_shutdown)

    try:
        loop.run_until_complete(run_local_worker(shutdown=shutdown))
    finally:
        loop.close()
        logger.info("Local job worker stopped")


if __name__ == "__main__":
    # Allows ``python -m kontext.labs.local_worker`` (used by the supervisor).
    run_worker_process()
