"""Runtime package for Kontext composition and deployment profiles.

This is the composition layer: it selects providers/backends and wires them
together. Execution contracts and validation policy live in ``kontext-kernel``;
the managed virtualenv a kernel runs in lives in
:mod:`kontext.runtime.python_environment`.
"""

from kontext.kernel.contracts import DEFAULT_RUNTIME_PROFILE

from .python_environment import (
    get_managed_python_environment_info,
    prepare_managed_python_environment,
)

_DEFAULT_RUNTIME_BACKEND = "kernel"


def create_python_runner_backend(
    backend_name: str = _DEFAULT_RUNTIME_BACKEND,
    *,
    runtime_profile: str = DEFAULT_RUNTIME_PROFILE,
):
    """Return the runner backend for *backend_name*.

    Backend selection is composition, so it lives here rather than in the
    dependency-free contract layer. Only ``kernel`` is supported: Python
    executes in a separate ``kontext-kernel`` process, launched with the managed
    interpreter for *runtime_profile*.
    """
    if backend_name != _DEFAULT_RUNTIME_BACKEND:
        raise ValueError(f"Unsupported python runner backend: {backend_name}")

    from kontext.kernel.runner import KernelPythonRunnerBackend

    from .python_environment import resolve_managed_python_executable

    return KernelPythonRunnerBackend(
        python_executable=resolve_managed_python_executable(runtime_profile=runtime_profile)
    )


__all__ = [
    "create_python_runner_backend",
    "get_managed_python_environment_info",
    "prepare_managed_python_environment",
]
