"""Agent-facing Python execution retry policy.

External (paused-run) Python executions are driven by an agent loop: each
failure resumes the run and the agent may call the tool again. When the
execution *infrastructure* fails back-to-back (kernel process cannot start,
run wedges), an open-ended retry loop holds the chat hostage for the user.
This module's cap bounds that loop to consecutive infra failures only — an
ordinary user-code error resets the streak, so legitimate iteration is never
capped.
"""

import os

from .env_vars import PythonExecutionEnvVars

# Upper bound for a single submitted Python cell/script. This mirrors the
# `max(10000)` constraint on `ExecutePythonScriptRequest` in ts/schema so the
# tool schema and the executed job params cannot drift apart (they previously
# did: the job capped code at 4000 while the tool advertised 10000).
MAX_PYTHON_CODE_CHARS = 10_000

# Default: three consecutive infrastructure failures fail the execution with
# an explicit stop-retrying message instead of letting the agent loop.
DEFAULT_MAX_CONSECUTIVE_KERNEL_FAILURES = 3


def max_consecutive_kernel_failures() -> int:
    """Resolve the consecutive-infra-failure cap from the environment."""
    raw = os.getenv(PythonExecutionEnvVars.MAX_CONSECUTIVE_KERNEL_FAILURES)
    if not raw:
        return DEFAULT_MAX_CONSECUTIVE_KERNEL_FAILURES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_CONSECUTIVE_KERNEL_FAILURES
    return max(value, 1)
