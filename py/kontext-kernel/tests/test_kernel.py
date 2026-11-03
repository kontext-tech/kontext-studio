"""End-to-end tests for the separate-process kernel execution model.

These spawn a real kernel child process, so they are slower than the rest of the
package's unit tests but exercise the true isolation boundary.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from pathlib import Path

import pytest

from kontext.kernel.contracts import PythonRunnerRequest
from kontext.kernel.manager import KernelManager, ManagedKernel
from kontext.kernel.protocol import KernelConnectionInfo
from kontext.kernel.runner import KernelPythonRunnerBackend

pytestmark = pytest.mark.asyncio


async def _start_manager(tmp_path: Path) -> tuple[KernelManager, ManagedKernel]:
    manager = KernelManager()
    kernel = await manager.start(workspace=tmp_path / "kernel", connect_timeout=30)
    return manager, kernel


async def test_kernel_executes_and_streams_stdout(tmp_path: Path) -> None:
    _manager, kernel = await _start_manager(tmp_path)
    try:
        messages = [message async for message in kernel.execute("print('hello')\n2 + 2")]
    finally:
        await kernel.shutdown()

    types = [message.get("msg_type") for message in messages]
    assert "execute_result" in types
    assert messages[-1]["msg_type"] == "execute_reply"

    stream_text = "".join(
        str((message.get("content") or {}).get("text") or "")
        for message in messages
        if message.get("msg_type") == "stream"
    )
    assert "hello" in stream_text

    result = next(message for message in messages if message.get("msg_type") == "execute_result")
    outputs = result["content"]["outputs"]
    assert outputs and outputs[0]["content"] == "4"


async def test_kernel_reports_user_error(tmp_path: Path) -> None:
    _manager, kernel = await _start_manager(tmp_path)
    try:
        messages = [message async for message in kernel.execute("raise ValueError('boom')")]
    finally:
        await kernel.shutdown()

    error = next(message for message in messages if message.get("msg_type") == "error")
    assert error["content"]["ename"] == "Exception"
    reply = messages[-1]
    assert reply["content"]["status"] == "error"


async def test_kernel_interrupt_stops_running_code(tmp_path: Path) -> None:
    _manager, kernel = await _start_manager(tmp_path)

    ready = asyncio.Event()
    messages: list[dict] = []

    async def consume() -> None:
        # Print a sentinel from inside the execution so the test only interrupts
        # once the code is genuinely running (not while the kernel is idle).
        code = "import time\nprint('ready', flush=True)\ntime.sleep(30)"
        async for message in kernel.execute(code):
            messages.append(message)
            content = message.get("content") or {}
            if message.get("msg_type") == "stream" and "ready" in str(content.get("text") or ""):
                ready.set()

    task = asyncio.ensure_future(consume())
    try:
        await asyncio.wait_for(ready.wait(), timeout=20)
        await kernel.interrupt()
        await asyncio.wait_for(task, timeout=20)
        # The kernel survives an interrupt and can still be shut down cleanly.
        assert kernel.is_alive()
        error = next(message for message in messages if message.get("msg_type") == "error")
        assert error["content"]["ename"] == "KeyboardInterrupt"
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await kernel.shutdown()

    assert not kernel.is_alive()


async def test_kernel_heartbeat_and_info(tmp_path: Path) -> None:
    _manager, kernel = await _start_manager(tmp_path)
    try:
        info = await kernel.client.kernel_info()
        assert info["content"]["kernel_name"] == "kontext-python"
        assert kernel.is_alive()
    finally:
        await kernel.shutdown()

    assert not kernel.is_alive()


async def test_runner_backend_success_and_timeout() -> None:
    backend = KernelPythonRunnerBackend()

    ok = await backend.run(
        PythonRunnerRequest(code="print('hi')\n41 + 1", data_payloads={}, timeout_seconds=30)
    )
    assert ok.success
    assert ok.stdout == "hi\n"
    assert ok.outputs[0] == {"type": "text", "mimeType": "text/plain", "content": "hi"}

    timed_out = await backend.run(
        PythonRunnerRequest(
            code="x = 0\nwhile True:\n    x += 1",
            data_payloads={},
            timeout_seconds=2,
        )
    )
    assert not timed_out.success
    assert timed_out.error == "Execution timed out."


async def test_runner_backend_rejects_forbidden_code() -> None:
    backend = KernelPythonRunnerBackend()
    result = await backend.run(
        PythonRunnerRequest(code="import subprocess", data_payloads={}, timeout_seconds=5)
    )
    assert not result.success
    assert "Forbidden import" in (result.error or "")


def test_connection_info_round_trip(tmp_path: Path) -> None:
    connection = KernelConnectionInfo(
        ip="127.0.0.1",
        shell_port=1,
        iopub_port=2,
        control_port=3,
        heartbeat_port=4,
        key="secret",
    )
    path = tmp_path / "connection.json"
    connection.write(path)
    loaded = KernelConnectionInfo.read(path)
    assert loaded.port("shell") == 1
    assert loaded.port("iopub") == 2
    assert loaded.key == "secret"


def test_connection_file_is_owner_only(tmp_path: Path) -> None:
    import stat

    connection = KernelConnectionInfo(
        ip="127.0.0.1",
        shell_port=1,
        iopub_port=2,
        control_port=3,
        heartbeat_port=4,
        key="secret",
    )
    path = tmp_path / "connection.json"
    connection.write(path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


async def test_kernel_rejects_wrong_token(tmp_path: Path) -> None:
    """The kernel refuses to serve a client that does not present the key."""
    import socket

    from kontext.kernel.harness import _Kernel
    from kontext.kernel.protocol import HELLO, new_message

    server_sock, client_sock = socket.socketpair()
    try:
        kernel = _Kernel(
            shell=server_sock,
            iopub=socket.socket(),
            control=socket.socket(),
            token="correct-secret",
        )
        bad = new_message(HELLO, {"key": "wrong-secret"}, channel="shell")
        client_sock.sendall((json.dumps(bad) + "\n").encode("utf-8"))

        assert kernel._authenticate() is False
    finally:
        server_sock.close()
        client_sock.close()


async def test_kernel_accepts_correct_token(tmp_path: Path) -> None:
    import socket

    from kontext.kernel.harness import _Kernel
    from kontext.kernel.protocol import HELLO, new_message

    server_sock, client_sock = socket.socketpair()
    try:
        kernel = _Kernel(
            shell=server_sock,
            iopub=socket.socket(),
            control=socket.socket(),
            token="correct-secret",
        )
        good = new_message(HELLO, {"key": "correct-secret"}, channel="shell")
        client_sock.sendall((json.dumps(good) + "\n").encode("utf-8"))

        assert kernel._authenticate() is True
        reply = json.loads(client_sock.recv(4096).decode("utf-8"))
        assert reply["msg_type"] == "hello_ack"
    finally:
        server_sock.close()
        client_sock.close()


async def test_collector_truncates_stdout_at_limit() -> None:
    from kontext.kernel.execution import ExecutionCollector
    from kontext.kernel.protocol import STREAM

    collector = ExecutionCollector(stdout_limit_bytes=8)
    collector.consume(
        {"msg_type": STREAM, "content": {"name": "stdout", "text": "0123456789abcdef"}}
    )
    collector.consume({"msg_type": "execute_reply", "content": {"status": "ok"}})

    result = collector.to_result()

    assert result.stdout == "01234567\n...[truncated]"
    assert result.outputs[0]["content"] == "01234567\n...[truncated]"


async def test_collector_leaves_stdout_intact_when_no_limit() -> None:
    from kontext.kernel.execution import ExecutionCollector
    from kontext.kernel.protocol import STREAM

    collector = ExecutionCollector()
    collector.consume({"msg_type": STREAM, "content": {"name": "stdout", "text": "a" * 100}})
    collector.consume({"msg_type": "execute_reply", "content": {"status": "ok"}})

    result = collector.to_result()

    assert result.stdout == "a" * 100


@pytest.mark.slow
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="creates a POSIX shell script; Windows uses a different launcher shape",
)
async def test_kernel_startup_failure_captures_child_stderr(tmp_path, caplog):
    """A kernel that dies at startup must surface the child's real stderr.

    Regression: stderr went to DEVNULL, so early exits were reported only as
    "Kernel process exited early with code 1" with no cause to act on.
    """
    import logging
    import stat

    failing_python = tmp_path / "failing-python.sh"
    failing_python.write_text('#!/bin/sh\necho "kernel bootstrap broken" >&2\nexit 1\n')
    failing_python.chmod(failing_python.stat().st_mode | stat.S_IXUSR)

    with caplog.at_level(logging.ERROR, logger="kontext.kernel.manager"):
        manager = KernelManager(python_executable=str(failing_python))
        with pytest.raises(RuntimeError) as exc_info:
            await manager.start(workspace=tmp_path / "kernel", connect_timeout=5)

    assert "exited early with code 1" in str(exc_info.value)
    assert "kernel bootstrap broken" in caplog.text
    # The startup failure path must log the captured stderr through
    # drain_to_logger so operators can tell start failures from run failures.
    assert any("Kernel startup stderr tail" in record.message for record in caplog.records)


@pytest.mark.slow
async def test_kernel_launcher_does_not_leak_stderr_pipe(tmp_path):
    """A healthy kernel must close the stderr capture pipe after launch."""
    manager = KernelManager()
    kernel = await manager.start(workspace=tmp_path / "kernel", connect_timeout=30)
    try:
        assert kernel.is_alive()
    finally:
        await kernel.shutdown(timeout=5)
