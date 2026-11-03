"""Shared message collection and host-call bridging for kernel executions.

Both the one-shot runner (:mod:`runner`) and the session runner
(:mod:`session_runner`) drive a kernel and turn its message stream into a
:class:`~kontext.kernel.contracts.PythonRunnerResult`. The kernel-facing
work is identical, so it lives here once:

* :class:`ExecutionCollector` accumulates IOPub/reply messages.
* :func:`make_host_call_handler` builds the async handler the kernel calls for
  platform operations (``execute_sql``, ``load_data``, ``list_data_sources``).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Any

from kontext.common.python_execution.helpers import classify_data_source_names
from kontext.common.python_execution.policy import validate_python_code
from kontext.kernel.contracts import PythonRunnerHostBridge, PythonRunnerResult

from .protocol import ERROR, EXECUTE_REPLY, EXECUTE_RESULT, STREAM


def _truncate(text: str, limit_bytes: int | None) -> str:
    """Cap *text* to *limit_bytes*, appending a marker when cut."""
    if not text or limit_bytes is None:
        return text
    raw = text.encode("utf-8")
    if len(raw) <= limit_bytes:
        return text
    return raw[:limit_bytes].decode("utf-8", "replace") + "\n...[truncated]"


class ExecutionCollector:
    """Accumulate IOPub/reply messages into a PythonRunnerResult."""

    def __init__(
        self,
        *,
        stdout_limit_bytes: int | None = None,
        stderr_limit_bytes: int | None = None,
    ) -> None:
        self.outputs: list[dict[str, Any]] = []
        self.stdout: list[str] = []
        self.stderr: list[str] = []
        self.error: str | None = None
        self.reply: dict[str, Any] = {}
        self._stdout_limit = stdout_limit_bytes
        self._stderr_limit = stderr_limit_bytes

    def consume(self, message: dict[str, Any]) -> None:
        msg_type = message.get("msg_type")
        content = message.get("content") or {}
        if msg_type == STREAM:
            text = str(content.get("text") or "")
            if content.get("name") == "stdout":
                self.stdout.append(text)
            else:
                self.stderr.append(text)
        elif msg_type == EXECUTE_RESULT:
            self.outputs.extend(content.get("outputs") or [])
        elif msg_type == ERROR:
            self.error = str(content.get("traceback") or content.get("evalue") or "")
        elif msg_type == EXECUTE_REPLY:
            self.reply = content
            if content.get("status") == "error" and self.error is None:
                self.error = str(content.get("error") or "Execution failed.")

    def to_result(self) -> PythonRunnerResult:
        error_text = self.error
        success = error_text is None and self.reply.get("status") == "ok"
        if not success and error_text is None:
            error_text = "Python execution failed."

        # Mirror the retired file-bridge output shape: stdout is prepended, and
        # stderr/error are appended as text outputs, so callers see no change.
        # Both the structured outputs and the raw stdout/stderr fields are capped
        # by the request's byte limits.
        outputs = list(self.outputs)
        raw_stdout = _truncate("".join(self.stdout), self._stdout_limit)
        raw_stderr = _truncate("".join(self.stderr), self._stderr_limit)
        stdout_text = raw_stdout.strip()
        stderr_text = raw_stderr.strip()
        if stdout_text:
            outputs.insert(0, {"type": "text", "mimeType": "text/plain", "content": stdout_text})
        if stderr_text:
            outputs.append({"type": "text", "mimeType": "text/plain", "content": stderr_text})
        if error_text:
            outputs.append({"type": "text", "mimeType": "text/plain", "content": error_text})

        return PythonRunnerResult(
            success=success,
            message=(
                "Python execution completed successfully."
                if success
                else "Python execution failed."
            ),
            error=error_text,
            outputs=outputs,
            stdout=raw_stdout,
            stderr=raw_stderr,
        )


async def drain(
    stream: AsyncGenerator[dict[str, Any], None], collector: ExecutionCollector
) -> None:
    """Feed every message from *stream* into *collector*."""
    async for message in stream:
        collector.consume(message)


def validation_failure(code: str, *, shared_namespace: bool = False) -> PythonRunnerResult | None:
    """Return a failed result if *code* violates policy, else ``None``."""
    is_valid, issues = validate_python_code(code, shared_namespace=shared_namespace)
    if is_valid:
        return None
    return PythonRunnerResult(
        success=False,
        message="Python code validation failed.",
        error=", ".join(issues),
        outputs=[],
        stdout="",
        stderr="",
    )


async def execute_and_collect(
    stream: AsyncGenerator[dict[str, Any], None],
    collector: ExecutionCollector,
    *,
    timeout_seconds: int,
) -> PythonRunnerResult:
    """Drain *stream* into *collector* with a timeout, returning the result.

    Wraps the stream in ``aclosing`` so a cancellation mid-stream still runs the
    generator's cleanup (releasing any per-session lock). Raises ``TimeoutError``
    so the caller can apply its own timeout handling; propagates
    ``asyncio.CancelledError`` unchanged.
    """
    async with aclosing(stream):
        await asyncio.wait_for(drain(stream, collector), timeout=timeout_seconds)
    return collector.to_result()


def timeout_result(timeout_seconds: int) -> PythonRunnerResult:
    return PythonRunnerResult(
        success=False,
        message=f"Python execution timed out after {timeout_seconds} seconds.",
        error="Execution timed out.",
        outputs=[],
        stdout="",
        stderr="",
    )


def make_host_call_handler(
    bridge: PythonRunnerHostBridge | None,
    data_payloads: dict[str, str] | None = None,
) -> Any:
    """Build the async host-call handler the kernel calls for platform ops.

    Supported ops: ``execute_sql`` (via *bridge*) and ``load_data`` /
    ``list_data_sources`` (served from *data_payloads*). The handler always returns
    ``(success, result, error)`` so failures are relayed to the kernel rather
    than raised across the socket.
    """
    payloads = data_payloads or {}

    async def handler(op: str, content: dict[str, Any]) -> tuple[bool, Any, str | None]:
        try:
            if op == "execute_sql":
                if bridge is None:
                    return False, None, "SQL execution is not available in this context."
                table = await bridge.execute_sql(
                    str(content.get("sql") or ""), content.get("title")
                )
                return True, _serialize(table), None
            if op == "load_data":
                data_id = str(content.get("data_id") or "")
                payload = payloads.get(data_id)
                if payload is None:
                    return False, None, f"Data '{data_id}' is not available."
                return True, json.loads(payload), None
            if op == "list_data_sources":
                return True, classify_data_source_names(payloads), None
            if op == "save_table":
                if bridge is None:
                    return False, None, "Saving tables is not available in this context."
                return True, _serialize(await bridge.save_table(content)), None
            return False, None, f"Unsupported host call: {op}"
        except Exception as exc:
            return False, None, str(exc)

    return handler


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True)
    return value
