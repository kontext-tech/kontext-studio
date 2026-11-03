"""Python execution contracts.

Shared contract for running a block of Python. It lives in ``kontext-common``
because it is referenced by the job/execution caller, the runtime provider that
*selects* a backend, and the ``kontext-kernel`` implementation.

* :class:`PythonRunnerRequest` / :class:`PythonRunnerResult` — the execution
  contract (code, data, limits, outputs).
* :class:`PythonRunnerHostBridge` / :class:`PythonRunnerBackend` — the protocols
  a backend and its platform bridge implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# Canonical name of the managed runtime profile. Owned here because this is the
# dependency-free contract layer; the managed-venv builder (in
# ``kontext-runtime``) imports it rather than redeclaring it.
DEFAULT_RUNTIME_PROFILE = "ml-default"


class PythonRunnerHostBridge(Protocol):
    async def execute_sql(self, sql: str, title: str | None = None) -> Any: ...

    async def save_table(self, content: dict[str, Any]) -> dict[str, Any]:
        """Materialize a table sent by kernel code as a durable data table.

        ``content`` carries ``{"title": ..., "data": "<base64 Parquet bytes>"}``
        as sent by the kernel adapter; the return is a summary dict for the cell
        (``dataTableId``/``rowCount``/``title``).
        """
        ...


@dataclass(frozen=True)
class PythonRunnerRequest:
    code: str
    data_payloads: dict[str, str]
    host_bridge: PythonRunnerHostBridge | None = None
    timeout_seconds: int = 300
    memory_limit_mb: int = 8192
    stdout_limit_bytes: int = 131072
    stderr_limit_bytes: int = 131072
    workspace_limit_bytes: int = 1073741824
    runtime_profile: str = DEFAULT_RUNTIME_PROFILE
    run_id: str | None = None


@dataclass(frozen=True)
class PythonRunnerResult:
    success: bool
    message: str
    error: str | None
    outputs: list[dict[str, Any]]
    stdout: str
    stderr: str


class PythonRunnerBackend(Protocol):
    async def run(self, request: PythonRunnerRequest) -> PythonRunnerResult: ...


class PythonSessionRunner(Protocol):
    """Run code in a process-shared, namespace-reusing session kernel.

    When a supervisor (worker) owns session kernels it exposes a runner
    through this protocol so consecutive cells of the same session share
    state. Providers return ``None`` when no supervisor is installed in the
    current process (e.g. a one-shot CLI run), and callers must fall back to
    the single-use :class:`PythonRunnerBackend`.
    """

    async def run(
        self,
        *,
        session_id: str,
        code: str,
        host_bridge: PythonRunnerHostBridge | None = None,
        data_payloads: dict[str, str] | None = None,
        timeout_seconds: int = 300,
        stdout_limit_bytes: int | None = None,
        stderr_limit_bytes: int | None = None,
        ephemeral: bool = False,
    ) -> PythonRunnerResult: ...
