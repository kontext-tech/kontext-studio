"""Managed Python environment: bootstrap, inspection, and interpreter resolution.

The kernel (and any Python execution) runs in a per-profile managed virtualenv so
notebook code has numpy/pandas/matplotlib available. This module owns that venv:

* :func:`resolve_managed_python_executable` — the interpreter to launch a kernel
  with (falls back to the current interpreter when the venv is not prepared).
* :func:`get_managed_python_environment_info` / :func:`prepare_managed_python_environment`
  — the data behind ``/account/python-environment``.

It is intentionally independent of *how* code executes (the kernel), so the
environment can be inspected and prepared without spawning anything.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import venv
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kontext.kernel.contracts import DEFAULT_RUNTIME_PROFILE as _DEFAULT_RUNTIME_PROFILE
from kontext.runtime.local.config import get_local_data_dir
from kontext.schema import (
    PythonEnvironmentInfo,
    PythonEnvironmentPackage,
    PythonPackageSource,
)

_MANAGED_BACKEND_ID = "managed_cpython_local"
_DEFAULT_PACKAGES = (
    "numpy==2.2.5",
    "pandas==2.2.3",
    "pyarrow==19.0.1",
    "scikit-learn==1.6.1",
    "scipy==1.15.3",
    "statsmodels==0.14.4",
    "patsy==1.0.1",
    "duckdb==1.3.2",
    # DuckDB needs pytz to return TIMESTAMPTZ values (e.g. current_timestamp).
    "pytz==2025.2",
    "matplotlib==3.10.1",
)

# One bootstrap at a time within a process; the venv build is not concurrency-safe.
_BOOTSTRAP_LOCK = threading.Lock()


@dataclass(frozen=True)
class ManagedEnvironment:
    """Paths describing a managed virtualenv for a runtime profile."""

    root_dir: Path
    python_executable: Path
    state_path: Path


def _current_python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _python_executable_path(env_dir: Path) -> Path:
    if os.name == "nt":
        return env_dir / "Scripts" / "python.exe"
    return env_dir / "bin" / "python"


def _create_managed_venv(env_dir: Path) -> None:
    """Create the venv with symlinked interpreters on POSIX.

    uv-managed CPython builds resolve libpython relative to the executable
    (``@executable_path/../lib``). Copying the interpreter into the venv leaves
    that library behind and ensurepip aborts, so keep the base executable as a
    symlink. Windows keeps the copy behaviour because symlinks need privileges.
    """
    builder = venv.EnvBuilder(
        with_pip=True,
        clear=True,
        symlinks=os.name != "nt",
    )
    builder.create(env_dir)


def managed_environment_for_profile(
    runtime_profile: str,
    *,
    python_version: str | None = None,
) -> ManagedEnvironment:
    effective_python_version = python_version or _current_python_version()
    runtime_root = (
        get_local_data_dir()
        / "python-runtimes"
        / _MANAGED_BACKEND_ID
        / runtime_profile
        / f"cpython-{effective_python_version}"
    )
    return ManagedEnvironment(
        root_dir=runtime_root,
        python_executable=_python_executable_path(runtime_root / "venv"),
        state_path=runtime_root / "state.json",
    )


def _desired_environment_state(runtime_profile: str) -> dict[str, Any]:
    return {
        "backend": _MANAGED_BACKEND_ID,
        "runtimeProfile": runtime_profile,
        "baseExecutable": sys.executable,
        "pythonVersion": _current_python_version(),
        "packages": list(_runtime_packages_for_profile(runtime_profile)),
    }


def _is_environment_initialized(
    environment: ManagedEnvironment,
    desired_state: dict[str, Any],
) -> bool:
    if not environment.python_executable.exists() or not environment.state_path.exists():
        return False

    with suppress(Exception):
        current_state = json.loads(environment.state_path.read_text("utf-8"))
        return current_state == desired_state

    return False


def _display_label_for_environment(runtime_profile: str) -> str:
    return f"Managed CPython Local ({runtime_profile})"


def _runtime_packages_for_profile(runtime_profile: str) -> tuple[str, ...]:
    if runtime_profile != _DEFAULT_RUNTIME_PROFILE:
        raise ValueError(f"Unsupported python runtime profile: {runtime_profile}")

    override = os.getenv("KONTEXT_PYTHON_RUNTIME_PACKAGES", "").strip()
    if override:
        return tuple(spec.strip() for spec in override.split(",") if spec.strip())

    return _DEFAULT_PACKAGES


def _parse_package_spec(spec: str) -> tuple[str, str]:
    normalized = spec.strip()
    parts = re.split(r"(==|>=|<=|~=|>|<)", normalized, maxsplit=1)
    if len(parts) >= 3:
        return parts[0].strip(), parts[2].strip()
    return normalized, normalized


def _configured_python_environment_packages(
    runtime_profile: str,
) -> list[PythonEnvironmentPackage]:
    packages: list[PythonEnvironmentPackage] = []
    for spec in _runtime_packages_for_profile(runtime_profile):
        name, version = _parse_package_spec(spec)
        packages.append(PythonEnvironmentPackage(name=name, version=version, spec=spec))
    return packages


def _list_installed_package_versions(python_executable: Path) -> dict[str, str]:
    response = subprocess.run(
        [
            str(python_executable),
            "-m",
            "pip",
            "list",
            "--disable-pip-version-check",
            "--format=json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(response.stdout or "[]")
    installed: dict[str, str] = {}
    if not isinstance(payload, list):
        return installed

    for entry in payload:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        version = str(entry.get("version") or "").strip()
        if name and version:
            installed[name.lower()] = version
    return installed


def _installed_python_environment_packages(
    runtime_profile: str,
    python_executable: Path,
) -> list[PythonEnvironmentPackage]:
    installed_versions = _list_installed_package_versions(python_executable)
    packages: list[PythonEnvironmentPackage] = []
    for configured in _configured_python_environment_packages(runtime_profile):
        packages.append(
            PythonEnvironmentPackage(
                name=configured.name,
                version=installed_versions.get(configured.name.lower(), configured.version),
                spec=configured.spec,
            )
        )
    return packages


def get_managed_python_environment_info(
    *,
    runtime_profile: str = _DEFAULT_RUNTIME_PROFILE,
) -> PythonEnvironmentInfo:
    """Report the managed environment's state without preparing it."""
    desired_state = _desired_environment_state(runtime_profile)
    environment = managed_environment_for_profile(
        runtime_profile,
        python_version=str(desired_state["pythonVersion"]),
    )
    initialized = _is_environment_initialized(environment, desired_state)
    package_source = PythonPackageSource.CONFIGURED
    packages = _configured_python_environment_packages(runtime_profile)

    if initialized:
        with suppress(Exception):
            packages = _installed_python_environment_packages(
                runtime_profile,
                environment.python_executable,
            )
            package_source = PythonPackageSource.INSTALLED

    return PythonEnvironmentInfo(
        available=True,
        initialized=initialized,
        display_label=_display_label_for_environment(runtime_profile),
        backend=str(desired_state["backend"]),
        runtime_profile=runtime_profile,
        python_version=str(desired_state["pythonVersion"]),
        package_source=package_source,
        packages=packages,
    )


def prepare_managed_python_environment(
    *,
    runtime_profile: str = _DEFAULT_RUNTIME_PROFILE,
) -> PythonEnvironmentInfo:
    """Create the managed environment if needed and report its packages."""
    environment = ensure_managed_python_environment(runtime_profile)
    desired_state = _desired_environment_state(runtime_profile)

    package_source = PythonPackageSource.CONFIGURED
    packages = _configured_python_environment_packages(runtime_profile)
    with suppress(Exception):
        packages = _installed_python_environment_packages(
            runtime_profile,
            environment.python_executable,
        )
        package_source = PythonPackageSource.INSTALLED

    return PythonEnvironmentInfo(
        available=True,
        initialized=True,
        display_label=_display_label_for_environment(runtime_profile),
        backend=str(desired_state["backend"]),
        runtime_profile=runtime_profile,
        python_version=str(desired_state["pythonVersion"]),
        package_source=package_source,
        packages=packages,
    )


def resolve_managed_python_executable(
    *,
    runtime_profile: str = _DEFAULT_RUNTIME_PROFILE,
) -> str:
    """Return the managed interpreter path, or the current interpreter.

    Kernels run in the managed venv (numpy/pandas/matplotlib) when it exists. If
    it has not been prepared yet, fall back to the current interpreter rather
    than paying a multi-minute bootstrap at kernel startup.
    """
    environment = managed_environment_for_profile(runtime_profile)
    if environment.python_executable.exists():
        return str(environment.python_executable)
    return sys.executable


def ensure_managed_python_environment(
    runtime_profile: str = _DEFAULT_RUNTIME_PROFILE,
) -> ManagedEnvironment:
    """Build the managed venv for *runtime_profile* if it is missing or stale.

    Guarded by a process-wide lock and built in a temp directory then swapped in
    atomically, so a partially-built environment is never used.
    """
    desired_state = _desired_environment_state(runtime_profile)
    environment = managed_environment_for_profile(
        runtime_profile,
        python_version=str(desired_state["pythonVersion"]),
    )
    runtime_root = environment.root_dir

    with _BOOTSTRAP_LOCK:
        if _is_environment_initialized(environment, desired_state):
            return environment

        tmp_root = runtime_root.with_name(f"{runtime_root.name}.tmp")
        shutil.rmtree(tmp_root, ignore_errors=True)
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_env_dir = tmp_root / "venv"

        _create_managed_venv(tmp_env_dir)

        tmp_python = _python_executable_path(tmp_env_dir)
        subprocess.run(
            [
                str(tmp_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--upgrade",
                "pip",
                "setuptools",
                "wheel",
            ],
            check=True,
        )
        subprocess.run(
            [
                str(tmp_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--only-binary=:all:",
                *_runtime_packages_for_profile(runtime_profile),
            ],
            check=True,
        )

        (tmp_root / "state.json").write_text(
            json.dumps(desired_state, ensure_ascii=True, indent=2),
            "utf-8",
        )
        shutil.rmtree(runtime_root, ignore_errors=True)
        os.replace(tmp_root, runtime_root)

    return managed_environment_for_profile(
        runtime_profile,
        python_version=str(desired_state["pythonVersion"]),
    )
