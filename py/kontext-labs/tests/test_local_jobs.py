from __future__ import annotations

import asyncio
import threading
import time
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from kontext.common.jobs.trigger_actor import agent_actor
from kontext.data import (
    JobRunDataService,
    QueryHistoryDataService,
    QuerySessionDataService,
)
from kontext.data.database import get_engine, get_session_factory, get_sync_db_session
from kontext.data.models import Project
from kontext.labs.server import create_app
from kontext.schema import CreateQueryRequest, CreateQuerySessionRequest
from kontext.storage import clear_storage_provider_cache


def _clear_runtime_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    clear_storage_provider_cache()


async def _drain_worker(timeout: float = 15.0) -> None:
    """Run the worker's claim/execute loop until no queued work remains.

    The worker normally runs as a separate process; tests drive the same
    functions in-process for determinism. A session-kernel manager is installed
    so notebook/chat jobs exercise the session-kernel path, as in production.
    """
    from kontext.kernel.registry import (
        get_session_kernel_manager,
        install_session_kernel_manager,
    )
    from kontext.kernel.sessions import SessionKernelManager
    from kontext.labs import local_worker

    worker = local_worker.worker_identifier()
    transport = local_worker._build_claim_transport()
    manager = get_session_kernel_manager() or SessionKernelManager()
    install_session_kernel_manager(manager)
    await manager.start()
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not await local_worker._run_one(worker=worker, transport=transport):
                return
        raise AssertionError("worker did not drain queued runs in time")
    finally:
        await manager.shutdown()
        install_session_kernel_manager(None)


@contextmanager
def _background_worker(*, poll_interval: float = 0.1):
    """Run the worker loop in a background thread for the duration of a block.

    Request handlers such as ``/session/init`` queue a run and poll until a
    worker executes it. In production that is the separate worker process; a
    thread keeps this test deterministic while still exercising the real
    claim/execute code path.
    """
    from kontext.kernel.registry import install_session_kernel_manager
    from kontext.kernel.sessions import SessionKernelManager
    from kontext.labs import local_worker

    stop = threading.Event()
    ready = threading.Event()
    errors: list[BaseException] = []

    def _run() -> None:
        async def _loop() -> None:
            worker = local_worker.worker_identifier()
            transport = local_worker._build_claim_transport()
            manager = SessionKernelManager()
            install_session_kernel_manager(manager)
            await manager.start()
            ready.set()
            try:
                while not stop.is_set():
                    try:
                        ran = await local_worker._run_one(worker=worker, transport=transport)
                    except BaseException as exc:
                        errors.append(exc)
                        ran = False
                    if not ran:
                        await asyncio.sleep(poll_interval)
            finally:
                await manager.shutdown()
                install_session_kernel_manager(None)

        asyncio.run(_loop())

    thread = threading.Thread(target=_run, name="test-local-worker", daemon=True)
    thread.start()
    assert ready.wait(timeout=5), "background worker did not start"
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=10)
    if errors:
        raise AssertionError(f"background worker raised: {errors[0]!r}") from errors[0]


TEST_LAUNCH_TOKEN = "test-launch-token"


def _launch_headers() -> dict[str, str]:
    return {"X-Kontext-Launch-Token": TEST_LAUNCH_TOKEN}


def _get_local_access_token(client: TestClient) -> str:
    bootstrap_response = client.get("/host/auth/bootstrap", headers=_launch_headers())
    bootstrap_payload = bootstrap_response.json()

    if bootstrap_payload.get("accessToken"):
        return bootstrap_payload["accessToken"]["accessToken"]

    setup_response = client.post(
        "/setup",
        json={
            "firstName": "Local",
            "lastName": "Tester",
            "email": "local-tester@example.com",
        },
        headers=_launch_headers(),
    )
    assert setup_response.status_code == 200
    return setup_response.json()["accessToken"]


def test_labs_upload_creates_run_and_worker_executes_it(tmp_path, monkeypatch):
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
            app = create_app(dist_dir=str(tmp_path / "nonexistent-dist"))
            with TestClient(app) as client:
                access_token = _get_local_access_token(client)

                with get_sync_db_session() as session:
                    project_id = session.execute(
                        select(Project.id).where(Project.project_code == "local")
                    ).scalar_one()

                response = client.post(
                    f"/file/upload?projectId={project_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    files={"file": ("orders.csv", b"id,total\n1,10\n", "text/csv")},
                )
                assert response.status_code == 201

                account_info_response = client.get(
                    "/account/info",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert account_info_response.status_code == 200
                user_id = account_info_response.json()["id"]

                chat_session_response = client.post(
                    "/ai/chat/session",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "projectId": str(project_id),
                        "sessionName": "Local Chat",
                    },
                )
                assert chat_session_response.status_code == 201
                chat_session = chat_session_response.json()
                assert chat_session["dateCreated"].endswith("Z")

                query_session_service = QuerySessionDataService(project_id)
                query_session = asyncio.run(
                    query_session_service.create_session_async(
                        CreateQuerySessionRequest(
                            project_id=str(project_id),
                            session_name="Local Query Session",
                        ),
                        user_id=user_id,
                    )
                )

                query_history_service = QueryHistoryDataService(project_id)
                query_history_service.record_query(
                    CreateQueryRequest(
                        code="select 1",
                        succeeded=True,
                        session_id=str(query_session.id),
                        duration_ms=12,
                    ),
                    user_id=user_id,
                )

                job_runs_response = client.get(
                    f"/job-runs?projectId={project_id}&pageIndex=1&pageSize=10",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert job_runs_response.status_code == 200
                payload = job_runs_response.json()
                assert payload["items"]
                first_run = payload["items"][0]
                assert first_run["createdAt"].endswith("Z")
                assert first_run["job"]["dateCreated"].endswith("Z")
                assert first_run["jobTrigger"]["createdAt"].endswith("Z")

                run_service = JobRunDataService(project_id)
                page = asyncio.run(run_service.get_runs_paginated_async(page_index=1, page_size=20))
                assert page.items
                queued_run = page.items[0]
                assert queued_run.status.value == "Queued"

                # The worker runs as a separate process in production; drive its
                # claim/execute loop here and assert it runs the queued work.
                asyncio.run(_drain_worker())

                completed_run = asyncio.run(
                    run_service.get_run_by_id_async(queued_run.id, include_job=True)
                )
                assert completed_run is not None
                assert completed_run.status.value == "Succeeded"
                assert completed_run.job is not None
                assert completed_run.job.type == "python.jobs.LakehouseIngestJob"

                project_response = client.get(
                    "/project/code/local",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert project_response.status_code == 200
                project_payload = project_response.json()
                assert project_payload["dateCreated"].endswith("Z")

                catalog_entities_payload = []
                deadline = time.time() + 10
                while time.time() < deadline:
                    catalog_entities_response = client.get(
                        f"/catalog/entities?projectId={project_id}",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    assert catalog_entities_response.status_code == 200
                    catalog_entities_payload = catalog_entities_response.json()
                    if catalog_entities_payload:
                        break
                    time.sleep(0.2)

                assert catalog_entities_payload
                assert catalog_entities_payload[0]["entityName"] == "orders"

                jobs_types_response = client.get(
                    f"/jobs/types?projectId={project_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert jobs_types_response.status_code == 200

                chat_sessions_response = client.get(
                    f"/ai/chat/session/filtered?projectId={project_id}&pageIndex=1&pageSize=10&mySessionsOnly=true",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert chat_sessions_response.status_code == 200
                chat_sessions_payload = chat_sessions_response.json()
                assert chat_sessions_payload["items"]
                assert chat_session["id"] == chat_sessions_payload["items"][0]["id"]
                assert chat_sessions_payload["items"][0]["dateCreated"].endswith("Z")

                query_sessions_response = client.get(
                    f"/session?projectId={project_id}&pageIndex=1&pageSize=10&mySessionsOnly=true",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert query_sessions_response.status_code == 200
                query_sessions_payload = query_sessions_response.json()
                assert query_sessions_payload["items"]
                assert str(query_session.id) == query_sessions_payload["items"][0]["id"]
                assert query_sessions_payload["items"][0]["createdAt"].endswith("Z")

                query_history_response = client.get(
                    f"/query/sessions/{query_session.id}/history?projectId={project_id}&pageIndex=1&pageSize=10",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert query_history_response.status_code == 200
                query_history_payload = query_history_response.json()
                assert query_history_payload["queries"]
                assert query_history_payload["queries"][0]["createdAt"].endswith("Z")

                events_response = client.get(
                    f"/event?projectId={project_id}&pageIndex=1&pageSize=10&daysLimit=30",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert events_response.status_code == 200
                events_payload = events_response.json()
                assert events_payload["items"]
                assert events_payload["items"][0]["dateCreated"].endswith("Z")
        finally:
            _clear_runtime_caches()


def test_labs_query_session_init_and_execute_use_local_worker(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'kontext.db'}"
    monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(tmp_path / "storage"))
    # The worker runs as a subprocess and inherits the environment, so the DB
    # URL must be set here rather than only patched in this process.
    monkeypatch.setenv("PROJECT_DB_URL", db_url)

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
            app = create_app(dist_dir=str(tmp_path / "nonexistent-dist"))
            with TestClient(app) as client:
                access_token = _get_local_access_token(client)
                headers = {"Authorization": f"Bearer {access_token}"}

                with get_sync_db_session() as session:
                    project_id = session.execute(
                        select(Project.id).where(Project.project_code == "local")
                    ).scalar_one()

                account_info_response = client.get("/account/info", headers=headers)
                assert account_info_response.status_code == 200
                user_id = account_info_response.json()["id"]

                query_session_service = QuerySessionDataService(project_id)
                query_session = asyncio.run(
                    query_session_service.create_session_async(
                        CreateQuerySessionRequest(
                            project_id=str(project_id),
                            session_name="Local Query Session",
                        ),
                        user_id=user_id,
                    )
                )

                # `/session/init` and `/query/execute` queue runs and poll
                # until the worker completes them, so run the worker for the
                # duration of both requests.
                with _background_worker():
                    init_response = client.post(
                        "/session/init",
                        headers=headers,
                        json={
                            "projectId": str(project_id),
                            "sessionId": str(query_session.id),
                            "persistent": True,
                        },
                    )
                    assert init_response.status_code == 200

                    execute_response = client.post(
                        "/query/execute",
                        headers=headers,
                        json={
                            "projectId": str(project_id),
                            "sessionId": str(query_session.id),
                            "sqlQuery": "select 1 as value",
                        },
                    )
                    assert execute_response.status_code == 200

                init_payload = init_response.json()
                assert init_payload["success"] is True
                assert init_payload["session"]["status"] == "Active"
                execute_payload = execute_response.json()
                assert execute_payload["success"] is True
                assert execute_payload["result"]["rowCount"] == 1
                assert execute_payload["result"]["rows"] == [[1]]
        finally:
            _clear_runtime_caches()


def _seed_project_and_user(client: TestClient):
    access_token = _get_local_access_token(client)
    headers = {"Authorization": f"Bearer {access_token}"}
    with get_sync_db_session() as session:
        project_id = session.execute(
            select(Project.id).where(Project.project_code == "local")
        ).scalar_one()
    user_id = client.get("/account/info", headers=headers).json()["id"]
    return project_id, user_id, headers


def test_labs_session_python_jobs_run_in_worker_and_share_namespace(tmp_path, monkeypatch):
    """A session-scoped Python run executes in the worker and keeps state.

    This is the notebook/chat path end to end: the API enqueues a queued run and
    waits, the worker claims it and runs a session kernel, and a second run on
    the same chat session sees the first run's variable.
    """
    import json
    from uuid import uuid4

    from kontext.execution.python_execution import PythonExecutionService

    db_url = f"sqlite:///{tmp_path / 'kontext.db'}"
    monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("PROJECT_DB_URL", db_url)
    monkeypatch.setenv("KONTEXT_LOCAL_WORKER_POLL_INTERVAL", "0.1")

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
            app = create_app(dist_dir=str(tmp_path / "nonexistent-dist"))
            with TestClient(app) as client:
                project_id, _, _ = _seed_project_and_user(client)
                chat_session_id = str(uuid4())
                execution_service = PythonExecutionService()

                with _background_worker():
                    first = asyncio.run(
                        execution_service.execute_script_async(
                            project_id=str(project_id),
                            chat_session_id=chat_session_id,
                            code="remembered = 41",
                            data_sources={},
                            triggered_by=agent_actor("test"),
                        )
                    )
                    second = asyncio.run(
                        execution_service.execute_script_async(
                            project_id=str(project_id),
                            chat_session_id=chat_session_id,
                            code="remembered + 1",
                            data_sources={},
                            triggered_by=agent_actor("test"),
                        )
                    )

                assert first.python_result.success is True
                assert second.python_result.success is True
                outputs = second.python_result.outputs
                rendered = json.dumps([output.model_dump(by_alias=True) for output in outputs])
                # The second run only succeeds if the kernel kept `remembered`.
                assert "42" in rendered
        finally:
            _clear_runtime_caches()
