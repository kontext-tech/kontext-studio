"""Kontext kernel child process.

Standalone and stdlib-only by design: this file is executed as a script by the
managed interpreter and must not import ``kontext`` (that would couple the
kernel to the parent process's package graph and defeat isolation).

Topology: the kernel binds four loopback sockets, writes a connection file with
their ports and an auth key, then accepts the parent's connection on each. The
parent reads the file and connects. Binding in the child removes the
connection-file race (the ports are listening before they are published) at the
cost of the parent polling for the file.

* main thread   accepts/reads ``shell``, executes code, publishes on ``iopub``
* control thread reads ``control`` (interrupt/shutdown + host-call replies)
* beat thread    echoes ``heartbeat`` pings

Kept in sync with :mod:`kontext.kernel.protocol`; the protocol module is
the source of truth for message names and framing.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import contextlib
import hmac
import io
import json
import os
import signal
import socket
import sys
import textwrap
import threading
import traceback
import types
from pathlib import Path
from typing import Any

EXECUTE_REQUEST = "execute_request"
EXECUTE_REPLY = "execute_reply"
KERNEL_INFO_REQUEST = "kernel_info_request"
KERNEL_INFO_REPLY = "kernel_info_reply"
INTERRUPT_REQUEST = "interrupt_request"
INTERRUPT_REPLY = "interrupt_reply"
SHUTDOWN_REQUEST = "shutdown_request"
SHUTDOWN_REPLY = "shutdown_reply"
STATUS = "status"
EXECUTE_INPUT = "execute_input"
STREAM = "stream"
DISPLAY_DATA = "display_data"
EXECUTE_RESULT = "execute_result"
ERROR = "error"
HOST_CALL_REQUEST = "host_call_request"
HOST_CALL_REPLY = "host_call_reply"
HELLO = "hello"
HELLO_ACK = "hello_ack"

_KERNEL_NAME = "kontext-python"
_PROTOCOL_VERSION = "1.0"
_SOCKET_TIMEOUT_SECONDS = 30.0

# ── confined runtime policy (open + dynamic execution) ───────────────────────

# The supervisor resolves the allowed roots with the shared path policy
# (storage + KONTEXT_ALLOWED_PATHS) and passes them here. Kept in sync with
# ``kontext.kernel.manager`` / ``kontext.common.constants.StorageEnvVars``;
# this child is stdlib-only and cannot import ``kontext``.
_OPEN_ROOTS_ENV = "KONTEXT_OPEN_ROOTS"
_WHITELISTED_MODULES_ENV = "KONTEXT_WHITELISTED_MODULES"
_BLACKLISTED_MODULES_ENV = "KONTEXT_BLACKLISTED_MODULES"


class _PolicyDenied(PermissionError):
    """Raised when user code violates the kernel runtime policy.

    Covers confined ``open`` roots and banned dynamic execution/imports; the
    message carries the actionable detail.
    """


def _canonical_roots() -> list[Path]:
    roots: list[Path] = []
    raw = os.environ.get(_OPEN_ROOTS_ENV, "")
    for entry in raw.split(os.pathsep):
        if not entry.strip():
            continue
        candidate = Path(entry).expanduser().resolve()
        if candidate not in roots:
            roots.append(candidate)
    workspace = Path.cwd().resolve()
    if workspace not in roots:
        roots.append(workspace)
    return roots


def _library_roots() -> list[Path]:
    """Directories the interpreter may *read* its own libraries from.

    Whitelisted packages load bundled data through Python-level ``open``
    (matplotlib style files, package resources). Those reads must succeed;
    writing anywhere outside the managed roots stays denied, so this grants no
    capability the policy cares about (the agent cannot reach host state).
    Derived child-side because the child's interpreter (managed venv) may
    differ from the supervisor's.
    """
    candidates: list[Path] = [Path(sys.prefix), Path(sys.base_prefix)]
    try:
        import site

        candidates.extend(Path(entry) for entry in site.getsitepackages())
    except Exception:
        pass

    roots: list[Path] = []
    for candidate in candidates:
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        if resolved not in roots:
            roots.append(resolved)
    return roots


def _is_read_only_mode(mode: str) -> bool:
    """Whether *mode* opens without write/append/create intent."""
    return not any(flag in mode for flag in ("w", "a", "x", "+"))


def _install_confined_open() -> None:
    """Route the Python-level file constructors (``open``, ``io.open``,
    ``io.FileIO``, and any route to them) through the allowed roots.

    A Python-level pre-flight policy cannot be airtight: module dicts are
    reachable without any banned builtin call or dunder attribute access
    (``vars(module)['builtins']['open']``). Patching the real builtins/module
    attributes means *every* Python-level construction in this process applies
    the same policy: reads/writes inside the managed roots, plus read-only
    access to the interpreter's own libraries so whitelisted packages can load
    their bundled data.

    Scope: this confines Python-level file I/O. Libraries that open files below
    Python (e.g. ``numpy.fromfile``, ``matplotlib.savefig``) bypass it; process
    isolation, not this guardrail, is the boundary for untrusted code.
    """
    roots = _canonical_roots()
    library_roots = _library_roots()
    real_open = io.open

    def resolve_allowed(path_str: str, mode: str) -> Path:
        """Return the canonical path if policy permits *mode*, else raise."""
        resolved = Path(path_str).expanduser().resolve()
        if any(resolved.is_relative_to(root) for root in roots):
            return resolved
        if _is_read_only_mode(mode) and any(
            resolved.is_relative_to(root) for root in library_roots
        ):
            return resolved
        allowed = os.pathsep.join(str(root) for root in roots)
        raise _PolicyDenied(
            f"Path '{path_str}' is outside the kernel's allowed open roots "
            f"({allowed}); only read-only access to the interpreter's libraries "
            f"is additionally permitted."
        )

    def open_within(file, mode="r", *args, **kwargs):
        if isinstance(file, int):
            # A file descriptor, not a path.
            return real_open(file, mode, *args, **kwargs)
        path_str = file if isinstance(file, str) else os.fsdecode(file)
        return real_open(resolve_allowed(path_str, mode), mode, *args, **kwargs)

    class _ConfinedFileIO(io.FileIO):
        """``io.FileIO`` is a second construction path and takes the same rule."""

        def __init__(self, file, mode="r", *args, **kwargs):
            if isinstance(file, int):
                super().__init__(file, mode, *args, **kwargs)
                return
            path_str = file if isinstance(file, str) else os.fsdecode(file)
            super().__init__(str(resolve_allowed(path_str, mode)), mode, *args, **kwargs)

    import builtins

    builtins.open = open_within
    io.open = open_within
    io.FileIO = _ConfinedFileIO


def _env_module_set(env_name: str) -> frozenset[str] | None:
    """Parse a supervisor-passed module list.

    ``None`` means the supervisor did not configure runtime import
    confinement; the child then leaves imports to the pre-flight policy
    instead of denying everything (a legacy/custom spawn must degrade, not
    brick user imports).
    """
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return None
    return frozenset(entry.strip() for entry in raw.split(os.pathsep) if entry.strip())


def _install_confined_execution(user_ns: dict) -> None:
    """Confine user-originated dynamic execution (``exec``/``eval``/``compile``)
    and imports reached through dynamic paths.

    The real builtins dict remains reachable without banned attribute access
    (``vars(module)['builtins']``), so the policy enforces *at the builtin
    itself*: a stub applies the same whitelist/blacklist rules as the
    pre-flight check when the immediate caller frame runs in the persistent
    user namespace (``f_globals is user_ns``), and delegates to the original
    for every other caller — library internals (numpy/pandas importing ``os``,
    ``compile`` usage inside package code) are unaffected because their frames
    are library frames. Delegation is namespace-faithful: when the caller
    relied on implicit globals/locals (module-level ``exec('del ' + obj)``),
    the stub resolves them from the caller's frame instead of its own, so
    library code that builds/tears down module names sees its own namespace.
    Configured by the supervisor through the scrubbed
    environment; the child cannot import the shared policy module.
    """
    whitelist = _env_module_set(_WHITELISTED_MODULES_ENV)
    blacklist = _env_module_set(_BLACKLISTED_MODULES_ENV)

    import builtins

    def _caller_is_user(frame) -> bool:
        return frame is not None and (
            frame.f_globals is user_ns or frame.f_code.co_filename == "<kontext-generated>"
        )

    real_import = builtins.__import__
    real_exec = builtins.exec
    real_eval = builtins.eval
    real_compile = builtins.compile

    def confined_import(name, globals=None, locals=None, fromlist=(), level=0):
        if _caller_is_user(sys._getframe(1)) and whitelist is not None:
            if level != 0:
                raise _PolicyDenied(
                    "Relative imports are not available in managed cells; "
                    "import top-level packages with absolute names."
                )
            root = str(name).split(".")[0]
            if blacklist and root in blacklist:
                raise _PolicyDenied(f"Forbidden import: '{root}'")
            if root not in whitelist:
                raise _PolicyDenied(f"Module '{root}' is not in the managed-cells whitelist.")
        return real_import(name, globals, locals, fromlist, level)

    def confined_exec(source, *args, **kwargs):
        frame = sys._getframe(1)
        if _caller_is_user(frame):
            raise _PolicyDenied(
                "Dynamic execution (exec/eval/compile) is not available in "
                "managed cells; write the code directly instead."
            )
        if not args and not kwargs:
            # Delegation runs in this stub's frame, so implicit-namespace
            # semantics would resolve globals/locals from *here* instead of
            # the true caller (module-level ``exec('del ' + obj)`` in
            # scipy.stats and caller-frame ``eval`` in numpy.f2py break that
            # way). Pass the caller's namespaces explicitly: identical
            # behavior for module frames (``f_locals`` is the module dict)
            # and native-equivalent for function frames (a materialized
            # locals snapshot, matching what the builtin would have used).
            return real_exec(source, frame.f_globals, frame.f_locals)
        return real_exec(source, *args, **kwargs)

    def confined_eval(source, *args, **kwargs):
        frame = sys._getframe(1)
        if _caller_is_user(frame):
            raise _PolicyDenied(
                "Dynamic execution (exec/eval/compile) is not available in "
                "managed cells; write the code directly instead."
            )
        if not args and not kwargs:
            return real_eval(source, frame.f_globals, frame.f_locals)
        return real_eval(source, *args, **kwargs)

    def confined_compile(source, *args, **kwargs):
        if _caller_is_user(sys._getframe(1)):
            raise _PolicyDenied(
                "Dynamic execution (exec/eval/compile) is not available in "
                "managed cells; write the code directly instead."
            )
        return real_compile(source, *args, **kwargs)

    builtins.__import__ = confined_import
    builtins.exec = confined_exec
    builtins.eval = confined_eval
    builtins.compile = confined_compile


# ── output formatting ────────────────────────────────────────────────────────


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    item = getattr(value, "item", None)
    if callable(item):
        with contextlib.suppress(Exception):
            return item()
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        with contextlib.suppress(Exception):
            return tolist()
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _make_json_output(content: Any) -> dict[str, str]:
    return {
        "type": "json",
        "mimeType": "application/json",
        "content": json.dumps(content, default=_json_default, ensure_ascii=True),
    }


def _make_text_output(content: str) -> dict[str, str]:
    return {"type": "text", "mimeType": "text/plain", "content": content}


def _make_image_output(image_bytes: bytes) -> dict[str, str]:
    return {
        "type": "image",
        "mimeType": "image/png",
        "content": base64.b64encode(image_bytes).decode("ascii"),
    }


def _is_dataframe(value: Any) -> bool:
    return (
        hasattr(value, "to_dict")
        and hasattr(value, "head")
        and value.__class__.__module__.startswith("pandas")
    )


def _dataframe_output(frame: Any) -> dict[str, str]:
    preview = frame.head(50)
    return _make_json_output(
        {
            "type": "dataframe_preview",
            "columns": [str(column) for column in preview.columns.tolist()],
            "rows": preview.to_dict(orient="records"),
            "rowCount": len(frame.index),
        }
    )


def _emit_output(value: Any, outputs: list[dict[str, str]]) -> None:
    value = _unwrap_await_ready(value)
    if value is None:
        return
    if _is_dataframe(value):
        outputs.append(_dataframe_output(value))
        return
    if isinstance(value, dict | list | tuple | set):
        outputs.append(_make_json_output(value))
        return
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        with contextlib.suppress(Exception):
            outputs.append(_make_json_output(to_dict()))
            return
    outputs.append(_make_text_output(str(value)))


def _capture_matplotlib(outputs: list[dict[str, str]]) -> None:
    with contextlib.suppress(Exception):
        import matplotlib.pyplot as plt  # type: ignore[import-untyped]

        figures = list(plt.get_fignums())
        for figure_number in figures:
            figure = plt.figure(figure_number)
            buffer = io.BytesIO()
            figure.savefig(buffer, format="png", bbox_inches="tight")
            outputs.append(_make_image_output(buffer.getvalue()))
            buffer.close()
        if figures:
            plt.close("all")


# ── streaming stdout/stderr ───────────────────────────────────────────────────


class _StreamBridge(io.TextIOBase):
    """Redirects writes to ``iopub`` ``stream`` messages as they happen."""

    def __init__(self, publish: Any, name: str) -> None:
        self._publish = publish
        self._name = name

    def writable(self) -> bool:
        return True

    def write(self, value: str) -> int:
        text = str(value)
        if text:
            self._publish(self._name, text)
        return len(text)

    def flush(self) -> None:
        return None


# ── host bridge (kernel side) ─────────────────────────────────────────────────


class _HostBridge:
    """Kernel-side proxy that asks the parent to run platform operations."""

    def __init__(self, kernel: _Kernel) -> None:
        self._kernel = kernel

    def call(self, op: str, **payload: Any) -> Any:
        return self._kernel.host_call(op, payload)

    def execute_sql(self, sql: str, title: str | None = None) -> Any:
        return self._kernel.host_call("execute_sql", {"sql": sql, "title": title})

    def save_table(self, title: str | None, frame: Any) -> Any:
        return self._kernel.host_call(
            "save_table",
            {"title": title, "data": _encode_frame_for_save(frame)},
        )

    def load_data(self, data_id: str) -> Any:
        return self._kernel.host_call("load_data", {"data_id": data_id})

    def list_data_sources(self) -> Any:
        return self._kernel.host_call("list_data_sources", {})


# ── kernel ────────────────────────────────────────────────────────────────────


class _Kernel:
    def __init__(
        self,
        *,
        shell: socket.socket,
        iopub: socket.socket,
        control: socket.socket,
        token: str,
    ) -> None:
        self._shell = shell
        self._iopub = iopub
        self._control = control
        self._token = token
        self._send_lock = threading.Lock()
        self._pending_host_calls: dict[str, threading.Event] = {}
        self._host_call_results: dict[str, dict[str, Any]] = {}
        self._shutdown = threading.Event()
        self._execution_count = 0
        # One reader per socket, shared by every consumer: ``_MessageReader``
        # keeps the partial-frame buffer on the instance so an asynchronous
        # ``KeyboardInterrupt`` cannot drop bytes already read from the socket.
        self._shell_messages = _MessageReader(shell)
        self._control_messages = _MessageReader(control)
        # Persistent user namespace: survives across executions in a session
        # kernel; a one-shot kernel simply uses it once.
        self._user_ns: dict[str, Any] = {}
        # Confine dynamic execution/imports for anything run in this namespace.
        # (Confined `open` is installed earlier, in ``main``.)
        _install_confined_execution(self._user_ns)

    # -- transport helpers ---------------------------------------------------

    def _send(self, sock: socket.socket, message: dict[str, Any]) -> None:
        payload = (json.dumps(message, default=str) + "\n").encode("utf-8")
        with self._send_lock:
            sock.sendall(payload)

    def _publish(
        self,
        msg_type: str,
        content: dict[str, Any],
        *,
        parent_id: str | None = None,
    ) -> None:
        self._send(
            self._iopub,
            {
                "msg_id": _new_id(),
                "msg_type": msg_type,
                "channel": "iopub",
                "parent_id": parent_id,
                "content": content,
            },
        )

    def _reply(
        self,
        msg_type: str,
        content: dict[str, Any],
        *,
        request: dict[str, Any],
        channel: str,
    ) -> None:
        sock = self._shell if channel == "shell" else self._control
        self._send(
            sock,
            {
                "msg_id": _new_id(),
                "msg_type": msg_type,
                "channel": channel,
                "parent_id": request.get("msg_id"),
                "content": content,
            },
        )

    # -- background loops ----------------------------------------------------

    def start_background(self) -> None:
        threading.Thread(target=self._control_loop, name="kernel-control", daemon=True).start()

    def _control_loop(self) -> None:
        for message in self._control_messages:
            msg_type = message.get("msg_type")
            content = message.get("content") or {}
            if msg_type == INTERRUPT_REQUEST:
                # Deliver SIGINT to the process so the main thread's in-progress
                # blocking call (e.g. time.sleep) raises KeyboardInterrupt
                # promptly. Windows cannot signal this way and falls back to the
                # supervisor killing the process tree.
                with contextlib.suppress(Exception):
                    os.kill(os.getpid(), signal.SIGINT)
                self._reply(
                    INTERRUPT_REPLY, {"status": "interrupting"}, request=message, channel="control"
                )
            elif msg_type == SHUTDOWN_REQUEST:
                self._reply(SHUTDOWN_REPLY, {"status": "ok"}, request=message, channel="control")
                self._shutdown.set()
                with contextlib.suppress(Exception):
                    sys.stdout.flush()
                os._exit(0)
            elif msg_type == HOST_CALL_REPLY:
                request_id = str(content.get("request_id") or "")
                event = self._pending_host_calls.get(request_id)
                if event is None:
                    # Late reply for an already-timed-out host call: drop it so
                    # long-lived session kernels do not accumulate results.
                    continue
                self._host_call_results[request_id] = content
                event.set()

    # -- host calls ----------------------------------------------------------

    def host_call(self, op: str, payload: dict[str, Any]) -> Any:
        request_id = _new_id()
        event = threading.Event()
        self._pending_host_calls[request_id] = event
        self._send(
            self._control,
            {
                "msg_id": _new_id(),
                "msg_type": HOST_CALL_REQUEST,
                "channel": "control",
                "parent_id": None,
                "content": {"request_id": request_id, "op": op, **payload},
            },
        )
        if not event.wait(timeout=_SOCKET_TIMEOUT_SECONDS):
            self._pending_host_calls.pop(request_id, None)
            raise TimeoutError(f"Host call '{op}' timed out")
        response = self._host_call_results.pop(request_id, {})
        self._pending_host_calls.pop(request_id, None)
        if not response.get("success"):
            raise RuntimeError(str(response.get("error") or f"Host call '{op}' failed"))
        return response.get("result")

    # -- shell loop ----------------------------------------------------------

    def _authenticate(self) -> bool:
        """Require a valid ``hello`` handshake before serving any request.

        The parent must send its connection key first; without it the kernel
        refuses to serve. This keeps a stray local process from driving a
        kernel it happened to find a port for.
        """
        for message in self._shell_messages:
            if message.get("msg_type") != HELLO:
                return False
            key = str((message.get("content") or {}).get("key") or "")
            if not hmac.compare_digest(key, self._token):
                return False
            self._reply(
                HELLO_ACK,
                {"status": "ok", "protocol_version": _PROTOCOL_VERSION},
                request=message,
                channel="shell",
            )
            return True
        return False

    def serve_shell(self) -> None:
        if not self._authenticate():
            return
        self._publish(STATUS, {"execution_state": "starting"})
        self._publish(STATUS, {"execution_state": "idle"})
        while True:
            # An interrupt may land anywhere in this loop, not just inside the
            # blocking read: the control channel raises SIGINT, and the reply of
            # the execution it was meant to cancel is published by this thread
            # first. Letting it escape would end the kernel (``main`` treats a
            # ``KeyboardInterrupt`` as a clean exit) and silently drop the
            # session namespace, so an interrupt never ends the shell loop;
            # shutdown goes through the control channel.
            try:
                try:
                    message = next(self._shell_messages)
                except StopIteration:
                    return
                if self._shutdown.is_set():
                    return
                msg_type = message.get("msg_type")
                if msg_type == EXECUTE_REQUEST:
                    self._handle_execute(message)
                elif msg_type == KERNEL_INFO_REQUEST:
                    self._reply(
                        KERNEL_INFO_REPLY,
                        {"kernel_name": _KERNEL_NAME, "protocol_version": _PROTOCOL_VERSION},
                        request=message,
                        channel="shell",
                    )
            except KeyboardInterrupt:
                continue

    def _handle_execute(self, message: dict[str, Any]) -> None:
        content = message.get("content") or {}
        code = str(content.get("code") or "")
        request_id = message.get("msg_id")

        self._execution_count += 1
        self._publish(
            EXECUTE_INPUT,
            {"code": code, "execution_count": self._execution_count},
            parent_id=request_id,
        )
        self._publish(STATUS, {"execution_state": "busy"}, parent_id=request_id)

        outputs: list[dict[str, str]] = []
        error_text: str | None = None
        error_type: str | None = None
        error_value: str | None = None

        stdout = _StreamBridge(self._publish_stream(request_id), "stdout")
        stderr = _StreamBridge(self._publish_stream(request_id), "stderr")
        saved_stdout, saved_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = stdout, stderr
        try:
            result_value = _execute_code(code, self, self._user_ns, outputs)
            if result_value is not None:
                _emit_output(result_value, outputs)
        except KeyboardInterrupt:
            error_text = "Execution interrupted"
            error_type = "KeyboardInterrupt"
            error_value = "Execution interrupted by user"
        except SystemExit as exc:
            error_text = f"SystemExit: {exc}"
            error_type = "SystemExit"
            error_value = str(exc)
        except BaseException:
            error_text = traceback.format_exc()
            error_type = "Exception"
            error_value = error_text.strip().splitlines()[-1]
        finally:
            sys.stdout, sys.stderr = saved_stdout, saved_stderr
            _capture_matplotlib(outputs)

        if error_text is not None:
            self._publish(
                ERROR,
                {"ename": error_type, "evalue": error_value, "traceback": error_text},
                parent_id=request_id,
            )

        if outputs:
            self._publish(
                EXECUTE_RESULT,
                {"outputs": outputs, "execution_count": self._execution_count},
                parent_id=request_id,
            )

        self._publish(STATUS, {"execution_state": "idle"}, parent_id=request_id)
        self._reply(
            EXECUTE_REPLY,
            {
                "status": "error" if error_text is not None else "ok",
                "execution_count": self._execution_count,
                "result": {"outputs": outputs},
                "error": error_text,
                "error_name": error_type,
                "error_value": error_value,
            },
            request=message,
            channel="shell",
        )

    def _publish_stream(self, parent_id: str | None) -> Any:
        def publish(name: str, text: str) -> None:
            with contextlib.suppress(OSError):
                self._publish(STREAM, {"name": name, "text": text}, parent_id=parent_id)

        return publish


def _new_id() -> str:
    import uuid

    return uuid.uuid4().hex


class _MessageReader:
    """Iterate JSON messages read as newline-delimited frames from a socket.

    This is a plain iterator rather than a generator on purpose. The shell loop
    blocks in ``recv`` while idle, and the control channel raises ``SIGINT`` to
    unblock a running cell; that ``KeyboardInterrupt`` can therefore land inside
    ``recv``. A generator would be closed by the escaping exception, so the next
    ``next()`` would look like EOF and end the kernel. Keeping the partial-frame
    buffer on the instance lets the caller swallow the interrupt and keep
    reading the same connection.
    """

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buffer = b""

    def __iter__(self) -> _MessageReader:
        return self

    def __next__(self) -> dict[str, Any]:
        while True:
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    return json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
            try:
                chunk = self._sock.recv(65536)
            except OSError:
                raise StopIteration from None
            if not chunk:
                raise StopIteration from None
            self._buffer += chunk


def _bind(port: int) -> socket.socket:
    """Bind a loopback listener on *port* (0 = ephemeral) and return it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    sock.settimeout(None)
    return sock


def _accept(listener: socket.socket) -> socket.socket:
    connection, _address = listener.accept()
    connection.settimeout(None)
    with contextlib.suppress(OSError):
        listener.close()
    return connection


def _collect_target_names(target: ast.expr | None) -> list[str]:
    """Names bound by an assignment/loop/with target expression."""
    if target is None:
        return []
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple | ast.List):
        names: list[str] = []
        for element in target.elts:
            names.extend(_collect_target_names(element))
        return names
    if isinstance(target, ast.Starred):
        return _collect_target_names(target.value)
    return []


def _record_binding_names(node: ast.AST, names: list[str]) -> None:
    """Binding rules for a node: assignments, imports, for/with, match captures.

    Some bindings live in a *field* of their owning node (``for``/``with``
    targets), so this covers both nodes that are bindings themselves and nodes
    that bind through a field. Targets reachable only as comprehension
    variables are deliberately excluded (they bind in their own scope).
    """
    if isinstance(node, ast.Assign):
        for target in node.targets:
            names.extend(_collect_target_names(target))
    elif isinstance(node, ast.AnnAssign | ast.AugAssign):
        names.extend(_collect_target_names(node.target))
    elif isinstance(node, ast.NamedExpr):
        # `x := value` binds in the enclosing function scope (PEP 572).
        names.extend(_collect_target_names(node.target))
    elif isinstance(node, ast.Delete):
        for target in node.targets:
            names.extend(_collect_target_names(target))
    elif isinstance(node, ast.For | ast.AsyncFor):
        names.extend(_collect_target_names(node.target))
    elif isinstance(node, ast.With | ast.AsyncWith):
        for item in node.items:
            names.extend(_collect_target_names(item.optional_vars))
    elif isinstance(node, ast.Import):
        for alias in node.names:
            names.append(alias.asname or alias.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            if alias.name != "*":
                names.append(alias.asname or alias.name)
    elif isinstance(node, ast.MatchAs | ast.MatchStar | ast.MatchMapping):
        # `case x`, `case [x, *rest]`, `case {key: value, **rest}` bind a name
        # in the enclosing function scope, so it needs the same treatment.
        captured = getattr(node, "name", None)
        if isinstance(captured, str):
            names.append(captured)
        else:
            rest = getattr(node, "rest", None)
            if isinstance(rest, str):
                names.append(rest)


_SCOPE_DEFINITIONS = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _collect_function_scope_bindings(statements: list[ast.stmt]) -> list[str]:
    """Names bound directly in the generated async wrapper's function scope.

    ``await``-using cells are compiled inside ``async def __kontext_generated__``,
    so without ``global`` declarations their assignments/imports stay function
    locals and never reach the persistent session namespace. The walker records
    bindings at every depth *except* nested scopes (``def``/``class``/``lambda``
    introduce their own binding scopes, so their internals are skipped).
    """
    names: list[str] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _SCOPE_DEFINITIONS):
                names.append(child.name)
                continue  # nested scope: its bindings belong to that scope
            if isinstance(child, ast.Lambda):
                continue  # nested scope with no name to record
            _record_binding_names(child, names)
            visit(child)

    for statement in statements:
        # A top-level `def`/`class` *is* the nested scope; only its name binds.
        if isinstance(statement, _SCOPE_DEFINITIONS):
            names.append(statement.name)
            continue
        _record_binding_names(statement, names)
        visit(statement)

    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name.isidentifier() and not name.startswith("__") and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _execute_code(
    code: str,
    kernel: _Kernel,
    user_ns: dict[str, Any],
    outputs: list[dict[str, str]],
) -> Any:
    """Execute *code* in *user_ns*, supporting ``await`` and auto-display.

    ``user_ns`` is owned by the kernel and reused across executions, so a
    session kernel keeps its variables (the persistent-namespace behavior).
    Injected helpers (including ``display``, bound to *outputs*) are refreshed
    on every call.
    """
    needs_async = True
    body_source = code
    last_expression: str | None = None
    tree: ast.Module | None = None
    try:
        tree = ast.parse(code)
        needs_async = any(
            isinstance(node, ast.Await | ast.AsyncFor | ast.AsyncWith) for node in ast.walk(tree)
        )
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last = tree.body.pop()
            if isinstance(last, ast.Expr):
                last_expression = ast.unparse(last.value)
        body_source = ast.unparse(ast.Module(body=tree.body, type_ignores=[])) if tree.body else ""
    except SyntaxError:
        pass

    def display(value: Any) -> Any:
        _emit_output(value, outputs)
        return value

    user_ns["__name__"] = "__main__"
    user_ns["display"] = display
    adapter = _KontextAdapter(_HostBridge(kernel), await_ready=needs_async)
    user_ns["kontext"] = adapter
    _install_kontext_module_alias(adapter)

    if needs_async:
        # ``ast.unparse`` never ends with a newline, so the appended ``return``
        # would glue onto the last body line and make every async script a
        # SyntaxError. Normalize the terminator before appending anything.
        wrapper = "async def __kontext_generated__():\n"
        # Bind function-scope names in the module namespace so variables survive
        # into later cells of the same session kernel (assignments otherwise
        # stay locals of the generated async function).
        bindings = _collect_function_scope_bindings(tree.body) if tree is not None else []
        if bindings:
            wrapper += "    global " + ", ".join(bindings) + "\n"
        indented = textwrap.indent(body_source, "    ") if body_source.strip() else "    pass"
        wrapper += indented + "\n"
        if last_expression is not None:
            wrapper += f"    return ({last_expression})\n"
        else:
            wrapper += "    return None\n"
        exec(compile(wrapper, "<kontext-generated>", "exec"), user_ns)
        return asyncio.run(user_ns["__kontext_generated__"]())

    exec(compile(body_source, "<kontext-generated>", "exec"), user_ns)
    if last_expression is not None:
        return eval(compile(last_expression, "<kontext-generated>", "eval"), user_ns)
    return None


class _AwaitReady:
    """A resolved value that also satisfies ``await``.

    Host calls resolve synchronously inside the kernel, so ``load_data`` and
    friends return the real value already. Agents are guided towards the
    ``await kontext.load_data(...)`` style, however, and awaiting a raw value
    would fail with ``TypeError: object is not awaitable``. When the script is
    compiled asynchronously (``await_ready=True``), adapter results are wrapped
    so both styles work: ``await`` yields the underlying value, and
    attribute/get-item/len/iter access proxies to it for un-awaited calls.
    """

    __slots__ = ("_value",)

    def __init__(self, value: Any) -> None:
        object.__setattr__(self, "_value", value)

    def __await__(self) -> Any:
        value = object.__getattribute__(self, "_value")
        if False:  # pragma: no cover - makes this method a generator
            yield
        return value

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_value"), name)

    def __getitem__(self, key: Any) -> Any:
        return object.__getattribute__(self, "_value")[key]

    def __len__(self) -> int:
        return len(object.__getattribute__(self, "_value"))

    def __iter__(self) -> Any:
        return iter(object.__getattribute__(self, "_value"))

    def __repr__(self) -> str:
        return repr(object.__getattribute__(self, "_value"))

    def __str__(self) -> str:
        return str(object.__getattribute__(self, "_value"))

    def __bool__(self) -> bool:
        return bool(object.__getattribute__(self, "_value"))


def _unwrap_await_ready(value: Any) -> Any:
    """Peel an :class:`_AwaitReady` wrapper so output shaping sees the value."""
    if isinstance(value, _AwaitReady):
        return object.__getattribute__(value, "_value")
    return value


class _KontextAdapter:
    def __init__(self, bridge: _HostBridge, *, await_ready: bool = False) -> None:
        self._bridge = bridge
        self._await_ready = await_ready

    def _wrap(self, value: Any) -> Any:
        return _AwaitReady(value) if self._await_ready else value

    def execute_sql(self, sql: str, title: str | None = None) -> Any:
        table = self._bridge.execute_sql(sql, title)
        return self._wrap(_to_dataframe(table))

    def save_table(self, frame: Any, title: str | None = None) -> Any:
        result = self._bridge.save_table(title, frame)
        return self._wrap(result)

    def load_data(self, data_id: str) -> Any:
        payload = self._bridge.load_data(data_id)
        return self._wrap(_payload_to_dataframe(payload))

    def list_data_sources(self) -> Any:
        result = self._bridge.list_data_sources() or {}
        shaped = {
            "aliases": [str(item) for item in (result.get("aliases") or [])],
            "data_ids": [str(item) for item in (result.get("data_ids") or [])],
        }
        return self._wrap(shaped)


def _encode_frame_for_save(frame: Any) -> str:
    """Encode a table-like object as base64 Parquet for a ``save_table`` host call.

    Managed runtime venvs ship the analytics stack, so pandas DataFrames
    (``to_parquet``, Arrow engine) and ``pyarrow`` Tables are both supported;
    anything else is rejected with a clear message instead of a TypeError.
    """
    is_pandas = hasattr(frame, "to_parquet")
    if not is_pandas and not str(type(frame).__module__).startswith("pyarrow"):
        raise TypeError(
            "kontext.save_table expects a pandas DataFrame (or a pyarrow Table); "
            f"got {type(frame).__module__}.{type(frame).__name__}."
        )

    import io

    try:
        import pyarrow.parquet as parquet
    except Exception as exc:  # pragma: no cover - managed profiles ship pyarrow
        raise RuntimeError(
            "kontext.save_table requires pyarrow in the managed Python runtime."
        ) from exc

    buffer = io.BytesIO()
    if is_pandas:
        if str(type(frame).__module__).endswith("geopandas"):
            raise TypeError("kontext.save_table does not support geopandas frames.")
        frame.to_parquet(buffer, index=False)
    else:
        parquet.write_table(frame, buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


_KONTEXT_ALIAS_MARKER = "_kontext_adapter_alias"


def _install_kontext_module_alias(adapter: _KontextAdapter) -> None:
    """Make ``import kontext`` resolve to the injected adapter.

    The shared policy whitelists ``kontext`` and guided code uses
    ``kontext.load_data(...)``, so agents write ``import kontext`` naturally —
    but this child has no such package (the harness is stdlib-only and the
    managed venv ships only the analysis stack), so the import passed the
    confined-import whitelist and then failed with ``ModuleNotFoundError``. A
    module alias whose attributes forward to the adapter keeps both spellings
    (ambient name and import) equivalent.

    The alias is refreshed on every injection rather than created once: the
    adapter instance changes per cell (``await_ready`` follows whether the
    script is wrapped asynchronously) and modules are cached in
    ``sys.modules``, so stale bound methods would keep the first cell's await
    semantics.
    """
    existing = sys.modules.get("kontext")
    if isinstance(existing, types.ModuleType) and getattr(existing, _KONTEXT_ALIAS_MARKER, False):
        module = existing
    else:
        module = types.ModuleType("kontext")
        module.__doc__ = "Injected Kontext data adapter (ambient in managed Python cells)."
        module.__dict__[_KONTEXT_ALIAS_MARKER] = True
        sys.modules["kontext"] = module
    # Attribute assignment through the module dict: the alias surface mirrors
    # the adapter's host-call methods, and the adapter instance changes per
    # cell (see the docstring about await-ready semantics).
    module.__dict__["execute_sql"] = adapter.execute_sql
    module.__dict__["load_data"] = adapter.load_data
    module.__dict__["list_data_sources"] = adapter.list_data_sources
    module.__dict__["save_table"] = adapter.save_table


def _to_dataframe(table: Any) -> Any:
    """Convert a tabular host-call payload into a DataFrame when pandas exists."""
    if not isinstance(table, dict):
        return table
    columns = table.get("columns")
    rows = table.get("rows")
    if columns is None or rows is None:
        return table
    with contextlib.suppress(Exception):
        import pandas as pd  # type: ignore[import-untyped]

        names = [
            str(column.get("name") if isinstance(column, dict) else column) for column in columns
        ]
        return pd.DataFrame(rows, columns=names or None)
    return table


def _payload_to_dataframe(payload: Any) -> Any:
    """Materialize an inline-data payload for user code.

    Prefers a DataFrame when pandas is importable and falls back to a list of
    row records otherwise.
    """
    if not isinstance(payload, dict):
        return payload
    table = payload.get("table") if isinstance(payload.get("table"), dict) else payload
    if not isinstance(table, dict):
        return table
    frame = _to_dataframe(table)
    if frame is not table:
        return frame
    columns = [
        str(column.get("name") if isinstance(column, dict) else column)
        for column in (table.get("columns") or [])
    ]
    rows = table.get("rows") or []
    records: list[dict[str, Any]] = []
    for row in rows:
        values = list(row or [])
        records.append(
            {
                (columns[index] if index < len(columns) else f"column_{index}"): (
                    values[index] if index < len(values) else None
                )
                for index in range(max(len(columns), len(values)))
            }
        )
    return records


def main() -> int:
    connection_path = Path(sys.argv[1]).resolve()

    with contextlib.suppress(Exception):
        import matplotlib  # type: ignore[import-untyped]

        matplotlib.use("Agg", force=True)

    # File access within the child is policy-scoped before anything else runs.
    _install_confined_open()

    # Bind before publishing the connection file so the parent never connects to
    # a port that is not yet listening (the classic connection-file race).
    shell_listener = _bind(0)
    iopub_listener = _bind(0)
    control_listener = _bind(0)
    heartbeat_listener = _bind(0)

    connection = {
        "transport": "tcp",
        "ip": "127.0.0.1",
        "shell_port": shell_listener.getsockname()[1],
        "iopub_port": iopub_listener.getsockname()[1],
        "control_port": control_listener.getsockname()[1],
        "heartbeat_port": heartbeat_listener.getsockname()[1],
        "key": _new_id(),
        "kernel_name": _KERNEL_NAME,
        "version": _PROTOCOL_VERSION,
    }
    pending_path = connection_path.with_suffix(".json.tmp")
    pending_path.write_text(json.dumps(connection), encoding="utf-8")
    pending_path.replace(connection_path)
    with contextlib.suppress(OSError):
        os.chmod(connection_path, 0o600)

    # Accept in a fixed order; each accept returns as soon as the parent connects.
    shell = _accept(shell_listener)
    iopub = _accept(iopub_listener)
    control = _accept(control_listener)
    heartbeat = _accept(heartbeat_listener)

    def _heartbeat_loop() -> None:
        while True:
            try:
                data = heartbeat.recv(4096)
            except OSError:
                return
            if not data:
                return
            with contextlib.suppress(OSError):
                heartbeat.sendall(data)

    threading.Thread(target=_heartbeat_loop, name="kernel-heartbeat", daemon=True).start()

    kernel = _Kernel(shell=shell, iopub=iopub, control=control, token=str(connection["key"]))
    kernel.start_background()
    with contextlib.suppress(KeyboardInterrupt):
        kernel.serve_shell()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
