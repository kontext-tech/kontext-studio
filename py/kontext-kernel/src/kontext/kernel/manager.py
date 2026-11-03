"""Parent-side kernel connection, client and lifecycle manager.

The kernel binds the sockets and publishes a connection file; the parent waits
for that file and connects as a client. Kernel death is therefore observable as
a closed connection. See :mod:`kontext.kernel.protocol` for the wire
contract.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from uuid import uuid4

from kontext.common.constants.env_vars import StorageEnvVars
from kontext.common.python_execution.policy import BLACKLISTED_MODULES, WHITELISTED_MODULES
from kontext.common.utils.path_policy import get_allowed_roots

from .limits import (
    ProcessLimits,
    WindowsJobObject,
    attach_windows_job_object,
    popen_limit_kwargs,
)
from .protocol import (
    CONTROL,
    EXECUTE_REPLY,
    EXECUTE_REQUEST,
    HELLO,
    HOST_CALL_REPLY,
    HOST_CALL_REQUEST,
    INTERRUPT_REQUEST,
    KERNEL_INFO_REQUEST,
    SHELL,
    SHUTDOWN_REQUEST,
    KernelConnectionInfo,
    new_message,
    parse_line,
)

logger = logging.getLogger(__name__)

_READER_LIMIT = 2**22  # 4 MiB: plenty for one framed message + headroom

_STDERR_CAPTURE_LIMIT = 64 * 1024  # bounded tail of child stderr for diagnostics

# iopub status message type published by the kernel harness (harness-local
# constant; not shared through protocol.py).
_STATUS_MSG_TYPE = "status"


class _ChildStderrCapture:
    """Bounded in-memory capture of a kernel child's stderr.

    Keeps the pipe's read end open for the lifetime of the launch, collects up
    to ``_STDERR_CAPTURE_LIMIT`` trailing bytes on a reader thread, and logs
    them when the kernel fails to start or connect. Without this, early kernel
    deaths surfaced only as "exited early with code 1" with no cause.
    """

    def __init__(self) -> None:
        read_handle, self.handle = os.pipe()
        self._read_handle = read_handle
        self._read_closed = False
        # The reader thread appends while the consumer thread reads; the lock
        # keeps chunk list mutations and reads mutually safe.
        self._chunks_lock = threading.Lock()
        self._chunks: list[bytes] = []
        self._size = 0
        self._thread = threading.Thread(
            target=self._drain_forever, name="kernel-stderr-capture", daemon=True
        )
        self._thread.start()

    def close_write_handle(self) -> None:
        """The parent process does not write; close so EOF never blocks reads."""
        with contextlib.suppress(OSError):
            os.close(self.handle)

    def _close_read_handle(self) -> None:
        """Close the read end exactly once (a reused fd number must not close)."""
        if self._read_closed:
            return
        self._read_closed = True
        with contextlib.suppress(OSError):
            os.close(self._read_handle)
        self._thread.join(timeout=1.0)

    def _drain_forever(self) -> None:
        try:
            while True:
                chunk = os.read(self._read_handle, 4096)
                if not chunk:
                    return
                with self._chunks_lock:
                    self._chunks.append(chunk)
                    self._size += len(chunk)
                    while self._size > _STDERR_CAPTURE_LIMIT and len(self._chunks) > 1:
                        self._size -= len(self._chunks.pop(0))
        except OSError:
            return

    def close(self) -> None:
        """Release the read handle and reader thread when a kernel shuts down."""
        self._close_read_handle()

    def drain_to_logger(self, *, context: str) -> None:
        """Log (and stop) whatever stderr content has been captured."""
        self._close_read_handle()
        with self._chunks_lock:
            text = b"".join(self._chunks).decode("utf-8", errors="replace").strip()
            # The capture is consumed: a stale double-drain must not re-log.
            self._chunks = []
            self._size = 0
        if text:
            logger.error("Kernel %s stderr tail:\n%s", context, text)


def _new_id() -> str:
    return uuid4().hex


class KernelClient:
    """An async client connected to a running kernel's four channels."""

    def __init__(self, connection: KernelConnectionInfo) -> None:
        self.connection = connection
        self._shell_reader: asyncio.StreamReader | None = None
        self._shell_writer: asyncio.StreamWriter | None = None
        self._iopub_reader: asyncio.StreamReader | None = None
        self._iopub_writer: asyncio.StreamWriter | None = None
        self._control_reader: asyncio.StreamReader | None = None
        self._control_writer: asyncio.StreamWriter | None = None
        self._heartbeat_reader: asyncio.StreamReader | None = None
        self._heartbeat_writer: asyncio.StreamWriter | None = None
        self._iopub_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._shell_waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._control_waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._host_call_handler: Any = None
        self._host_call_tasks: set[asyncio.Task[None]] = set()
        self._iopub_task: asyncio.Task[None] | None = None
        self._control_task: asyncio.Task[None] | None = None
        self._shell_task: asyncio.Task[None] | None = None
        # Tracks the kernel's last iopub ``execution_state`` (``busy``/``idle``)
        # so callers can detect a live-but-wedged kernel before queueing.
        self._execution_state = "idle"

    async def connect(self, *, connect_timeout: float = 30.0) -> None:
        """Open the kernel's sockets under one deadline.

        A half-started kernel must not hang a worker forever: each socket
        connect (and the final authentication) runs under ``connect_timeout``.
        """
        conn = self.connection

        async def _open(port: int):
            return await asyncio.wait_for(
                asyncio.open_connection(conn.ip, port, limit=_READER_LIMIT),
                timeout=connect_timeout,
            )

        self._shell_reader, self._shell_writer = await _open(conn.shell_port)
        self._iopub_reader, self._iopub_writer = await _open(conn.iopub_port)
        self._control_reader, self._control_writer = await _open(conn.control_port)
        # The kernel accepts heartbeat out-of-band, so connect it after control.
        (
            self._heartbeat_reader,
            self._heartbeat_writer,
        ) = await _open(conn.heartbeat_port)
        self._iopub_task = asyncio.create_task(self._pump_iopub())
        self._control_task = asyncio.create_task(self._pump_control())
        self._shell_task = asyncio.create_task(self._pump_shell())
        await self._authenticate()

    async def _authenticate(self) -> None:
        """Send the connection key and require the kernel's ack.

        The kernel refuses to serve shell requests until this handshake
        succeeds, so a stray local process cannot drive the kernel.
        """
        writer = self._require(self._shell_writer)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        message = new_message(HELLO, {"key": self.connection.key}, channel=SHELL)
        self._shell_waiters[message["msg_id"]] = future
        await self._send(writer, message)
        try:
            reply = await asyncio.wait_for(future, timeout=30.0)
        finally:
            self._shell_waiters.pop(message["msg_id"], None)
        if (reply.get("content") or {}).get("status") != "ok":
            raise RuntimeError("Kernel rejected the connection handshake")

    def set_host_call_handler(self, handler: Any) -> None:
        """Set an async ``handler(op, content) -> (success, result, error)``."""
        self._host_call_handler = handler

    def is_busy(self) -> bool:
        """Whether the kernel reports a running execution (iopub status stream)."""
        return self._execution_state == "busy"

    # -- low-level send/read -------------------------------------------------

    async def _send(self, writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
        writer.write((json.dumps(message, default=str) + "\n").encode("utf-8"))
        await writer.drain()

    async def _read_message(self, reader: asyncio.StreamReader) -> dict[str, Any] | None:
        line = await reader.readline()
        if not line:
            return None
        return parse_line(line)

    async def request(
        self,
        channel: str,
        msg_type: str,
        content: dict[str, Any],
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        if channel == SHELL:
            writer = self._require(self._shell_writer)
            waiters = self._shell_waiters
        else:
            writer = self._require(self._control_writer)
            waiters = self._control_waiters

        message = new_message(msg_type, content, channel=channel)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        waiters[message["msg_id"]] = future
        await self._send(writer, message)
        try:
            reply = await asyncio.wait_for(future, timeout=timeout)
        finally:
            waiters.pop(message["msg_id"], None)
        return reply

    async def execute(self, code: str) -> dict[str, Any]:
        # Backstop just above the runners' collect timeout (300s): long runs
        # are interrupted long before this can fire, so it only guards a
        # wedged/never-replied shell request.
        return await self.request(
            SHELL,
            EXECUTE_REQUEST,
            {"code": code},
            timeout=330.0,
        )

    async def kernel_info(self) -> dict[str, Any]:
        return await self.request(
            SHELL,
            KERNEL_INFO_REQUEST,
            {},
            timeout=30.0,
        )

    async def interrupt(self) -> None:
        with contextlib.suppress(Exception):
            await self.request(
                CONTROL,
                INTERRUPT_REQUEST,
                {},
                timeout=10.0,
            )

    async def shutdown(self) -> None:
        with contextlib.suppress(Exception):
            await self.request(
                CONTROL,
                SHUTDOWN_REQUEST,
                {"restart": False},
                timeout=10.0,
            )

    # -- IOPub ---------------------------------------------------------------

    async def _pump_iopub(self) -> None:
        reader = self._require(self._iopub_reader)
        while True:
            message = await self._read_message(reader)
            if message is None:
                await self._iopub_queue.put({"_closed": True})
                return
            if message.get("msg_type") == _STATUS_MSG_TYPE:
                state = (message.get("content") or {}).get("execution_state")
                if state in {"busy", "idle"}:
                    self._execution_state = state
            await self._iopub_queue.put(message)

    async def _pump_shell(self) -> None:
        reader = self._require(self._shell_reader)
        while True:
            message = await self._read_message(reader)
            if message is None:
                return
            parent_id = message.get("parent_id")
            if parent_id and parent_id in self._shell_waiters:
                future = self._shell_waiters[parent_id]
                if not future.done():
                    future.set_result(message)

    async def stream_until_reply(self, code: str) -> AsyncGenerator[dict[str, Any], None]:
        """Execute *code*, yielding every IOPub message until the shell reply.

        Yields IOPub messages (``stream``, ``execute_result``, ``status`` …) then
        a final synthetic ``execute_reply`` carrying the shell response.
        """
        reply_future = asyncio.ensure_future(self.execute(code))
        try:
            while True:
                get_task = asyncio.ensure_future(self._iopub_queue.get())
                done, _pending = await asyncio.wait(
                    {get_task, reply_future},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if get_task in done:
                    message = get_task.result()
                    if message.get("_closed"):
                        break
                    yield message
                    continue
                get_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await get_task
                break
            reply = await reply_future
            yield {"msg_type": EXECUTE_REPLY, "channel": SHELL, "content": reply["content"]}
        finally:
            if not reply_future.done():
                reply_future.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await reply_future

    # -- control pump (host calls) -------------------------------------------

    async def _pump_control(self) -> None:
        reader = self._require(self._control_reader)
        while True:
            message = await self._read_message(reader)
            if message is None:
                return
            msg_type = message.get("msg_type")
            if msg_type == HOST_CALL_REQUEST:
                self._host_call_tasks.add(asyncio.create_task(self._handle_host_call(message)))
                self._host_call_tasks = {t for t in self._host_call_tasks if not t.done()}
            else:
                parent_id = message.get("parent_id")
                if parent_id and parent_id in self._control_waiters:
                    future = self._control_waiters[parent_id]
                    if not future.done():
                        future.set_result(message)

    async def _handle_host_call(self, message: dict[str, Any]) -> None:
        content = message.get("content") or {}
        request_id = str(content.get("request_id") or "")
        op = str(content.get("op") or "")
        success = False
        result: Any = None
        error: str | None = None
        if self._host_call_handler is None:
            error = "Host calls are not available in this execution context."
        else:
            try:
                success, result, error = await self._host_call_handler(op, content)
            except Exception as exc:
                success = False
                error = str(exc)
        await self._send(
            self._require(self._control_writer),
            {
                "msg_id": _new_id(),
                "msg_type": HOST_CALL_REPLY,
                "channel": CONTROL,
                "parent_id": message.get("msg_id"),
                "content": {
                    "request_id": request_id,
                    "success": success,
                    "result": result,
                    "error": error,
                },
            },
        )

    @staticmethod
    def _require(sock: Any) -> Any:
        if sock is None:
            raise RuntimeError("Kernel client is not connected")
        return sock

    async def close(self) -> None:
        for task in (self._iopub_task, self._control_task, self._shell_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        for writer in (
            self._shell_writer,
            self._iopub_writer,
            self._control_writer,
            self._heartbeat_writer,
        ):
            if writer is not None:
                with contextlib.suppress(Exception):
                    writer.close()
                    await writer.wait_closed()


class ManagedKernel:
    """Owns a single kernel process and its client."""

    def __init__(
        self,
        process: subprocess.Popen[Any],
        client: KernelClient,
        workspace: Path,
        *,
        job_object: WindowsJobObject | None = None,
        stderr_capture: _ChildStderrCapture | None = None,
    ) -> None:
        self.process = process
        self.client = client
        self.workspace = workspace
        self._job_object = job_object
        self._stderr_capture = stderr_capture
        self._closed = False

    def set_host_call_handler(self, handler: Any) -> None:
        self.client.set_host_call_handler(handler)

    def is_alive(self) -> bool:
        return self.process.poll() is None

    def is_busy(self) -> bool:
        """True while the kernel reports a running (possibly wedged) cell."""
        return self.client.is_busy()

    def log_exit_diagnostics(self, *, context: str) -> None:
        """Log a dead kernel's exit code and captured stderr tail, if any."""
        if self.is_alive():
            return
        logger.warning("Kernel %s exited (code %s)", context, self.process.poll())
        if self._stderr_capture is not None:
            self._stderr_capture.drain_to_logger(context=f"exit ({context})")

    async def execute(self, code: str) -> AsyncGenerator[dict[str, Any], None]:
        async for message in self.client.stream_until_reply(code):
            yield message

    async def interrupt(self) -> None:
        await self.client.interrupt()

    def terminate_now(self) -> None:
        """Force-terminate the kernel process tree synchronously.

        Used by cancellation, which may be invoked from a thread without a
        running event loop. The client sockets are closed by the process going
        away; :meth:`shutdown` remains the graceful path.
        """
        self._closed = True
        _terminate_tree(self.process)
        if self._job_object is not None:
            with contextlib.suppress(Exception):
                self._job_object.terminate()
            self._job_object.close()
        if self._stderr_capture is not None:
            self._stderr_capture.close()

    async def shutdown(self, *, timeout: float = 5.0) -> None:
        if self._closed:
            return
        self._closed = True
        await self.client.shutdown()
        await self.client.close()
        await asyncio.to_thread(self._wait_or_kill, timeout)
        if self._job_object is not None:
            self._job_object.close()
        if self._stderr_capture is not None:
            self._stderr_capture.close()

    def _wait_or_kill(self, timeout: float) -> None:
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate_tree(self.process)


# ── process tree termination (posix process groups / windows job objects) ────


def _terminate_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    with contextlib.suppress(Exception):
        if os.name != "nt":
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:  # pragma: no cover - Windows-only path
            process.kill()


class KernelManager:
    """Spawn and supervise kernels for the current process."""

    def __init__(self, *, python_executable: str | None = None) -> None:
        self._python_executable = python_executable or sys.executable
        self._harness_path = Path(__file__).with_name("harness.py")

    async def start(
        self,
        *,
        workspace: Path,
        env: dict[str, str] | None = None,
        connect_timeout: float = 30.0,
        limits: ProcessLimits | None = None,
        run_id: str | None = None,
    ) -> ManagedKernel:
        workspace.mkdir(parents=True, exist_ok=True)
        connection_path = workspace / "kernel-connection.json"
        with contextlib.suppress(FileNotFoundError):
            connection_path.unlink()

        effective_limits = limits or ProcessLimits()
        effective_env = env if env is not None else _default_child_env(workspace)
        # Hand the child its policy configuration (directory names only — no
        # secrets). A caller-supplied value wins, so custom spawns can pin it.
        with contextlib.suppress(Exception):
            for name, value in _supervisor_policy_env().items():
                effective_env.setdefault(name, value)

        # The child's stderr is the only place early startup failures (import
        # errors, rlimit rejections, interpreter problems) are reported; keep a
        # bounded pipe so "exited early" can actually be diagnosed.
        stderr_capture = _ChildStderrCapture()
        popen_kwargs: dict[str, Any] = {
            "cwd": str(workspace),
            "env": effective_env,
            "stdout": subprocess.DEVNULL,
            "stderr": stderr_capture.handle,
            **popen_limit_kwargs(effective_limits),
        }

        try:
            process = subprocess.Popen(
                [self._python_executable, "-I", str(self._harness_path), str(connection_path)],
                **popen_kwargs,
            )
        except BaseException:
            # Popen inherited (then lost) the write handle; make sure the
            # reader thread gets EOF and both ends are released.
            stderr_capture.close_write_handle()
            stderr_capture.drain_to_logger(context="launch")
            raise
        stderr_capture.close_write_handle()
        job_object = attach_windows_job_object(process)

        try:
            connection = await asyncio.to_thread(
                self._await_connection_file, connection_path, process, connect_timeout
            )
        except RuntimeError:
            stderr_capture.drain_to_logger(context="startup")
            _terminate_tree(process)
            if job_object is not None:
                job_object.close()
            raise
        client = KernelClient(connection)
        try:
            await client.connect(connect_timeout=connect_timeout)
        except (OSError, ConnectionError) as exc:
            stderr_capture.drain_to_logger(context="connect")
            _terminate_tree(process)
            if job_object is not None:
                job_object.close()
            raise RuntimeError(f"Kernel failed to connect: {exc}") from exc

        kernel = ManagedKernel(
            process,
            client,
            workspace,
            job_object=job_object,
            stderr_capture=stderr_capture,
        )
        if run_id:
            from .run_registry import get_running_kernel_registry

            get_running_kernel_registry().register(run_id, kernel)
        return kernel

    def _await_connection_file(
        self,
        connection_path: Path,
        process: subprocess.Popen[Any],
        connect_timeout: float,
    ) -> KernelConnectionInfo:
        deadline = time.monotonic() + connect_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Kernel process exited early with code {process.returncode}")
            if connection_path.exists():
                with contextlib.suppress(json.JSONDecodeError, KeyError, ValueError):
                    return KernelConnectionInfo.read(connection_path)
            time.sleep(0.05)
        raise RuntimeError("Kernel did not publish its connection file in time")


OPEN_ROOTS_ENV = StorageEnvVars.OPEN_ROOTS
WHITELISTED_MODULES_ENV = StorageEnvVars.WHITELISTED_MODULES
BLACKLISTED_MODULES_ENV = StorageEnvVars.BLACKLISTED_MODULES


def _supervisor_policy_env() -> dict[str, str]:
    """Policy configuration the stdlib-only kernel child must be told about.

    The child cannot import ``kontext``, so the supervisor resolves each value
    with the shared policy and hands it over through the scrubbed environment:
    the allowed open roots (storage + ``KONTEXT_ALLOWED_PATHS``) and the import
    whitelist/blacklist that mirror the pre-flight checks.
    """
    return {
        OPEN_ROOTS_ENV: os.pathsep.join(str(root) for root in get_allowed_roots()),
        WHITELISTED_MODULES_ENV: os.pathsep.join(sorted(WHITELISTED_MODULES)),
        BLACKLISTED_MODULES_ENV: os.pathsep.join(sorted(BLACKLISTED_MODULES)),
    }


def _default_child_env(workspace: Path) -> dict[str, str]:
    """Minimal, scrubbed environment for a kernel child process.

    No host secrets are inherited: a minimal PATH, no user site, and a
    workspace-scoped temp/home/cache so the kernel cannot read or write host
    state (matplotlib's font cache, XDG caches and ``$HOME`` all resolve into
    the workspace, which is also an allowed open root).
    """
    path = str(workspace)
    env = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "MPLBACKEND": "Agg",
        "TMPDIR": path,
        "TMP": path,
        "TEMP": path,
        # Point library caches/config (and HOME on POSIX, mirroring the
        # Windows USERPROFILE below) at the workspace so nothing tries to
        # touch the real home — which the open policy would deny anyway.
        "MPLCONFIGDIR": str(Path(path) / ".mplconfig"),
        "XDG_CACHE_HOME": str(Path(path) / ".cache"),
        "PATH": r"C:\Windows\System32" if os.name == "nt" else "/usr/bin:/bin",
    }
    if os.name != "nt":
        env["HOME"] = path
    if os.name == "nt":  # pragma: no cover - Windows-only
        env["USERPROFILE"] = path
        if os.environ.get("SystemRoot"):  # noqa: SIM112 - Windows env var name
            env["SystemRoot"] = os.environ["SystemRoot"]  # noqa: SIM112
        if os.environ.get("WINDIR"):
            env["WINDIR"] = os.environ["WINDIR"]
    else:
        env["HOME"] = path
    return env
