"""Tests for the persistent session-kernel manager."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any

import pytest

from kontext.kernel.sessions import SessionKernelManager

pytestmark = pytest.mark.asyncio


async def _collect(
    manager: SessionKernelManager,
    session_id: str,
    code: str,
    *,
    host_call_handler: Any = None,
) -> list[dict]:
    return [
        message
        async for message in manager.execute(session_id, code, host_call_handler=host_call_handler)
    ]


def _reply_status(messages: list[dict]) -> str:
    return str(messages[-1]["content"]["status"])


def _result_text(messages: list[dict]) -> str | None:
    for message in messages:
        if message.get("msg_type") == "execute_result":
            outputs = message["content"].get("outputs") or []
            if outputs:
                return str(outputs[0].get("content"))
    return None


async def test_session_kernel_persists_namespace(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        await _collect(manager, "s1", "x = 41")
        second = await _collect(manager, "s1", "x + 1")
        assert _result_text(second) == "42"
        assert manager.active_session_ids() == ["s1"]
    finally:
        await manager.shutdown()


async def test_sessions_are_isolated(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        await _collect(manager, "a", "secret = 1")
        other = await _collect(manager, "b", "secret")
        assert _reply_status(other) == "error"
        assert set(manager.active_session_ids()) == {"a", "b"}
    finally:
        await manager.shutdown()


async def test_idle_kernel_is_reaped(tmp_path: Path) -> None:
    manager = SessionKernelManager(
        workspace_root=tmp_path,
        idle_timeout_seconds=1.0,
        max_sessions=4,
    )
    await manager.start()
    try:
        await _collect(manager, "s1", "value = 1")
        assert manager.active_session_ids() == ["s1"]

        # Reaper sweeps at timeout/4; wait comfortably past the timeout.
        await asyncio.sleep(3.0)
        assert manager.active_session_ids() == []
    finally:
        await manager.shutdown()


async def test_close_session_terminates_kernel(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        await _collect(manager, "s1", "value = 1")
        assert await manager.close_session("s1") is True
        assert manager.active_session_ids() == []
        assert await manager.close_session("s1") is False
    finally:
        await manager.shutdown()


async def test_evicts_least_recently_used_at_capacity(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path, max_sessions=2)
    await manager.start()
    try:
        await _collect(manager, "old", "value = 1")
        await asyncio.sleep(0.05)
        await _collect(manager, "new", "value = 2")

        # Starting a third session must evict the least-recently-used ("old").
        await _collect(manager, "third", "value = 3")
        active = set(manager.active_session_ids())
        assert "old" not in active
        assert {"new", "third"} <= active
    finally:
        await manager.shutdown()


async def test_host_call_handler_is_per_execution(tmp_path: Path) -> None:
    """The platform bridge is supplied per execute() call, not bound to the kernel."""
    calls: list[str] = []

    async def handler(op: str, content: dict[str, Any]) -> tuple[bool, Any, str | None]:
        calls.append(op)
        return True, {"columns": [{"name": "value"}], "rows": [[1]]}, None

    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        first = await _collect(
            manager,
            "s1",
            "result = kontext.execute_sql('select 1')\nresult",
            host_call_handler=handler,
        )
        assert _reply_status(first) == "ok"
        assert calls == ["execute_sql"]

        # A later execution passes a fresh handler; the previous one is unused.
        second = await _collect(manager, "s1", "value = 1", host_call_handler=handler)
        assert _reply_status(second) == "ok"
        assert calls == ["execute_sql"]
    finally:
        await manager.shutdown()


async def test_interrupt_warm_session(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        assert await manager.interrupt("missing") is False

        ready = asyncio.Event()
        messages: list[dict] = []

        async def consume() -> None:
            code = "import time\nprint('ready', flush=True)\ntime.sleep(30)"
            async for message in manager.execute("s1", code):
                messages.append(message)
                content = message.get("content") or {}
                if message.get("msg_type") == "stream" and "ready" in str(
                    content.get("text") or ""
                ):
                    ready.set()

        task = asyncio.ensure_future(consume())
        try:
            await asyncio.wait_for(ready.wait(), timeout=20)
            assert await manager.interrupt("s1") is True
            await asyncio.wait_for(task, timeout=20)
            assert _reply_status(messages) == "error"
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    finally:
        await manager.shutdown()


async def test_close_session_removes_workspace(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        await _collect(manager, "s1", "value = 1")
        workspace = tmp_path / "kontext-session-s1"
        assert workspace.exists()
        assert await manager.close_session("s1") is True
        assert not workspace.exists()
    finally:
        await manager.shutdown()


async def test_reap_missing_sessions_closes_dead_sessions(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        await _collect(manager, "alive", "value = 1")
        await _collect(manager, "dead", "value = 2")

        reaped = await manager.reap_missing_sessions(lambda sid: sid != "dead")
        assert reaped == ["dead"]
        assert manager.active_session_ids() == ["alive"]
    finally:
        await manager.shutdown()


async def test_concurrent_executions_on_one_session_are_serialized(tmp_path: Path) -> None:
    """Two concurrent runs on the same session must not interleave namespaces."""
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:

        async def bump() -> None:
            for _ in range(5):
                await _collect(manager, "s1", "counter = globals().get('counter', 0) + 1")

        await asyncio.gather(bump(), bump())
        final = await _collect(manager, "s1", "counter")
        # Serialized increments: 10 total (each bump does 5). Interleaving the
        # read-modify-write would lose updates and yield fewer.
        assert _result_text(final) == "10"
    finally:
        await manager.shutdown()


async def test_busy_session_kernel_rejects_new_execution(tmp_path: Path) -> None:
    """A busy kernel whose consumer timed out must fail fast, not silently queue."""
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        ready = asyncio.Event()

        async def consume_long() -> None:
            code = "import time\nprint('ready', flush=True)\ntime.sleep(30)"
            async for message in manager.execute("s1", code):
                content = message.get("content") or {}
                if message.get("msg_type") == "stream" and "ready" in str(
                    content.get("text") or ""
                ):
                    ready.set()

        consumer = asyncio.ensure_future(consume_long())
        try:
            await asyncio.wait_for(ready.wait(), timeout=30)
        finally:
            # Simulate the runner's collect-timeout cancellation: the consumer
            # goes away while the kernel keeps running the script.
            consumer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer

        # Let the kernel settle into its still-busy state.
        await asyncio.sleep(0.3)

        second = await asyncio.wait_for(_collect(manager, "s1", "1 + 1"), timeout=25)
        assert _reply_status(second) == "error"
        assert "busy" in str(second[-1]["content"].get("error") or "")
    finally:
        await manager.shutdown()


async def test_idle_interrupts_never_end_the_session(tmp_path: Path) -> None:
    """SIGINT is asynchronous; it must interrupt without killing the kernel.

    The control channel raises the signal from another thread, so it can land
    outside the blocking read (for example while the reply of the cell it was
    meant to cancel is still being published). Escaping to ``main`` there exits
    the process cleanly and silently drops the session namespace.
    """
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        await _collect(manager, "s1", "value = 41")
        for _ in range(10):
            assert await manager.interrupt("s1") is True
            assert manager.active_session_ids() == ["s1"]

        # The namespace survived every interrupt.
        assert _result_text(await _collect(manager, "s1", "value")) == "41"
    finally:
        await manager.shutdown()


async def test_second_timeout_escalation_recreates_kernel(tmp_path: Path) -> None:
    """Two consecutive timeouts recreate the kernel instead of wedging the session."""
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    try:
        await _collect(manager, "s1", "value = 41")
        assert manager.active_session_ids() == ["s1"]

        # First timeout: best-effort SIGINT only.
        assert await manager.escalate_timeout("s1") is False
        assert manager.active_session_ids() == ["s1"]

        # Second consecutive timeout: control-channel shutdown + fresh session.
        assert await manager.escalate_timeout("s1") is True
        assert manager.active_session_ids() == []

        # Next use starts a fresh kernel with an empty namespace.
        fresh = await _collect(manager, "s1", "value")
        assert _reply_status(fresh) == "error"
        assert manager.active_session_ids() == ["s1"]
    finally:
        await manager.shutdown()
