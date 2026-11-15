"""Managed Python environment: bootstrap, inspection, and interpreter resolution.

The kernel (and any Python execution) runs in a per-profile managed virtualenv so
notebook code has numpy/pandas/matplotlib available. This module owns that venv:

* :func:`resolve_managed_python_executable` — the interpreter to launch a kernel
  with (falls back to the current interpreter when the venv is not prepared).
* :func:`get_managed_python_environment_info` / :func:`prepare_managed_python_environment`
  — the data behind ``/account/python-environment``.
* :func:`install_user_python_packages` — the user-facing extra-package install
  behind ``/account/python-environment/install``; distributions added this way
  are recorded in ``user-packages.json`` next to the venv and join the import
  whitelist through :func:`sync_user_installed_packages`.

It is intentionally independent of *how* code executes (the kernel), so the
environment can be inspected and prepared without spawning anything.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import venv
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kontext.common.python_execution.policy import (
    BLACKLISTED_MODULES,
    set_user_installed_modules,
)
from kontext.kernel.contracts import DEFAULT_RUNTIME_PROFILE as _DEFAULT_RUNTIME_PROFILE
from kontext.runtime.local.config import get_local_data_dir
from kontext.schema import (
    PythonEnvironmentInfo,
    PythonEnvironmentPackage,
    PythonPackageSource,
)

logger = logging.getLogger(__name__)

_MANAGED_BACKEND_ID = "managed_cpython_local"
_WHEELHOUSE_ENV = "KONTEXT_PYTHON_RUNTIME_WHEELHOUSE"
_DEFAULT_PACKAGES = (
    "numpy==2.2.5",
    "pandas==2.2.3",
    "pyarrow==19.0.1",
    "scipy==1.15.3",
    "statsmodels==0.14.4",
    "patsy==1.0.1",
    "duckdb==1.3.2",
    # DuckDB needs pytz to return TIMESTAMPTZ values (e.g. current_timestamp).
    "pytz==2025.2",
    "matplotlib==3.10.1",
    # scikit-learn is opt-in (KONTEXT_PYTHON_RUNTIME_PACKAGES): ordinary
    # analysis does not need it, and its scipy dependency dominates the
    # offline wheelhouse otherwise shared with statsmodels.
)

# One bootstrap at a time within a process; the venv build is not concurrency-safe.
# User installs share the lock: they must not pip-install into a venv that a
# bootstrap is rebuilding, and two concurrent installs would race their
# baseline diff of installed distributions.
_BOOTSTRAP_LOCK = threading.Lock()

_USER_PACKAGES_FILE = "user-packages.json"

# Upper bound mirrors the schema request model; both exist because installs
# shell out to pip and an unbounded list would hang the UI request.
_MAX_USER_PACKAGE_SPECS = 20

# The only pip requests the install endpoint forwards: distribution names,
# optional extras, optional single ``==`` pin. Ranges, markers, URLs, local
# paths and every pip flag are rejected — installs ride the same
# offline-first pipeline as the bootstrap, and argv injection of pip options
# (``--index-url``, ``--config-settings``) must be impossible.
_USER_PACKAGE_SPEC_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
    r"(?:\[[A-Za-z0-9,._-]*\])?(?:==[A-Za-z0-9._!*+~-]+)?$"
)


@dataclass(frozen=True)
class ManagedEnvironment:
    """Paths describing a managed virtualenv for a runtime profile."""

    root_dir: Path
    python_executable: Path
    state_path: Path


@dataclass(frozen=True)
class UserInstalledPackage:
    """A distribution a user added to the prepared venv after bootstrapping.

    ``modules`` carries the distribution's importable top-level names (the
    distribution name alone is unreliable, e.g. ``beautifulsoup4`` imports as
    ``bs4``); those, not the distribution name, join the import whitelist.
    The registry lives next to ``state.json``, so it is destroyed together
    with the venv on a rebuild — it never survives a venv it doesn't match.
    """

    name: str
    spec: str
    modules: tuple[str, ...]


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


def default_runtime_packages() -> tuple[str, ...]:
    """Return the shipped kernel package pins.

    This is the public source of truth for the offline desktop wheelhouse; it
    intentionally ignores the deployment-time package override.
    """
    return _DEFAULT_PACKAGES


def _runtime_wheelhouse() -> Path | None:
    """Return the configured offline wheelhouse, or ``None``.

    The desktop bundle ships wheels for the kernel packages so first use does
    not depend on the network. A configured-but-missing directory is a
    deployment error, not a silent fallback to PyPI.
    """
    raw = os.getenv(_WHEELHOUSE_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeError(f"{_WHEELHOUSE_ENV} points to a missing directory: {path}")
    return path


def _parse_package_spec(spec: str) -> tuple[str, str]:
    normalized = spec.strip()
    parts = re.split(r"(==|>=|<=|~=|>|<)", normalized, maxsplit=1)
    if len(parts) >= 3:
        return parts[0].strip(), parts[2].strip()
    return normalized, normalized


def _canonical_distribution_name(spec: str) -> str:
    """PEP 503-normalize a spec down to its bare distribution name."""
    name = re.split(r"[\[=<>,!~]", spec.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name.lower())


def _validate_user_package_specs(
    specs: list[str],
    *,
    runtime_profile: str,
) -> list[str]:
    """Normalize pip spec strings and reject anything pip must not receive.

    Raises :class:`ValueError` with an operator-friendly message on the first
    bad spec; returns the deduplicated, order-preserving accepted list.
    """
    if not specs:
        raise ValueError("No packages were requested.")

    managed_names = {
        _parse_package_spec(package)[0].lower()
        for package in _runtime_packages_for_profile(runtime_profile)
    }
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in specs:
        spec = (raw or "").strip()
        if not spec or not _USER_PACKAGE_SPEC_PATTERN.match(spec):
            raise ValueError(
                f"'{raw}' is not a valid package spec. Use a distribution name, "
                "optionally with extras or an '==version' pin; options, ranges "
                "and URLs are not accepted."
            )
        canonical = _canonical_distribution_name(spec)
        if canonical in managed_names:
            raise ValueError(
                f"'{canonical}' is provisioned by the managed runtime itself "
                "and cannot be installed again. Deployment-level overrides go "
                "through KONTEXT_PYTHON_RUNTIME_PACKAGES."
            )
        if {canonical, canonical.replace("-", "_")} & BLACKLISTED_MODULES:
            raise ValueError(
                f"'{canonical}' provides a module notebook execution forbids, "
                "so installing it can never make it importable."
            )
        if canonical not in seen:
            seen.add(canonical)
            normalized.append(spec)
    if len(normalized) > _MAX_USER_PACKAGE_SPECS:
        raise ValueError(f"Install at most {_MAX_USER_PACKAGE_SPECS} packages per request.")
    return normalized


def _user_packages_registry_path(runtime_profile: str) -> Path:
    return managed_environment_for_profile(runtime_profile).root_dir / _USER_PACKAGES_FILE


def _read_user_installed_packages(
    runtime_profile: str,
) -> dict[str, UserInstalledPackage]:
    """The persisted user-package registry, keyed by distribution name.

    The venv is the source of truth for what is importable; callers must not
    treat a registry hit as proof of installation.
    """
    try:
        payload = json.loads(_user_packages_registry_path(runtime_profile).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, list):
        return {}

    packages: dict[str, UserInstalledPackage] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        modules = tuple(
            sorted(
                {
                    str(module).strip()
                    for module in entry.get("modules") or []
                    if str(module).strip()
                }
            )
        )
        spec = str(entry.get("spec") or "").strip()
        packages[name.lower()] = UserInstalledPackage(name=name, spec=spec or name, modules=modules)
    return packages


def _write_user_installed_packages(
    runtime_profile: str,
    packages: dict[str, UserInstalledPackage],
) -> None:
    payload = [
        {"name": package.name, "spec": package.spec, "modules": list(package.modules)}
        for package in sorted(packages.values(), key=lambda item: item.name)
    ]
    # Written atomically: concurrent readers sync the whitelist from this
    # file, and a torn read would momentarily empty the extension set.
    target = _user_packages_registry_path(runtime_profile)
    tmp = target.with_name(f"{target.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", "utf-8")
    os.replace(tmp, target)


def sync_user_installed_packages(
    *,
    runtime_profile: str = _DEFAULT_RUNTIME_PROFILE,
) -> frozenset[str]:
    """Replace this process's whitelist extension from the persisted registry.

    Installing syncs in-process, so this only matters after a restart or a
    bootstrap rebuild, which wipes the registry together with the venv.
    Composition roots call it before kernels spawn — the kernel's import gate
    receives the whitelist through its environment at spawn time.
    """
    modules: set[str] = set()
    for package in _read_user_installed_packages(runtime_profile).values():
        modules.update(package.modules)
    return set_user_installed_modules(modules)


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
    # User-installed distributions come from the registry but are only
    # reported when the live venv still has them: a bootstrap rebuild wipes
    # both the packages and the registry, and a stale row must never claim a
    # module the sandbox no longer ships.
    for user in _read_user_installed_packages(runtime_profile).values():
        version = installed_versions.get(user.name.lower())
        if version is None:
            continue
        packages.append(
            PythonEnvironmentPackage(
                name=user.name,
                version=version,
                spec=user.spec or f"{user.name}=={version}",
                user_installed=True,
            )
        )
    return packages


def _report_environment(
    runtime_profile: str,
    *,
    initialized: bool,
) -> PythonEnvironmentInfo:
    """Build the response payload for the info/prepare/install endpoints."""
    desired_state = _desired_environment_state(runtime_profile)
    package_source = PythonPackageSource.CONFIGURED
    packages = _configured_python_environment_packages(runtime_profile)

    if initialized:
        environment = managed_environment_for_profile(
            runtime_profile,
            python_version=str(desired_state["pythonVersion"]),
        )
        with suppress(Exception):
            packages = _installed_python_environment_packages(
                runtime_profile,
                environment.python_executable,
            )
            package_source = PythonPackageSource.INSTALLED

    return PythonEnvironmentInfo(
        available=True,
        initialized=bool(initialized),
        display_label=_display_label_for_environment(runtime_profile),
        backend=str(desired_state["backend"]),
        runtime_profile=runtime_profile,
        python_version=str(desired_state["pythonVersion"]),
        package_source=package_source,
        packages=packages,
    )


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
    return _report_environment(runtime_profile, initialized=initialized)


def prepare_managed_python_environment(
    *,
    runtime_profile: str = _DEFAULT_RUNTIME_PROFILE,
) -> PythonEnvironmentInfo:
    """Create the managed environment if needed and report its packages."""
    ensure_managed_python_environment(runtime_profile)
    return _report_environment(runtime_profile, initialized=True)


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


def _ensure_bootstrap_logging() -> None:
    """Make bootstrap progress visible even when the host lowers log levels.

    The desktop profile runs its HTTP layer at WARNING, and progress records
    from this module would be dropped before reaching the ``desktop.log`` the
    UI points at for support. A dedicated INFO handler keeps the milestones
    reportable in that bundle; regular servers are unaffected.
    """
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [python-environment] %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def ensure_managed_python_environment(
    runtime_profile: str = _DEFAULT_RUNTIME_PROFILE,
) -> ManagedEnvironment:
    """Build the managed venv for *runtime_profile* if it is missing or stale.

    Guarded by a process-wide lock and built in a temp directory then swapped in
    atomically, so a partially-built environment is never used.
    """
    with _BOOTSTRAP_LOCK:
        return _ensure_environment_locked(runtime_profile)


def _ensure_environment_locked(
    runtime_profile: str,
) -> ManagedEnvironment:
    """The :func:`ensure_managed_python_environment` body, lock already held."""
    started_at = time.monotonic()
    _ensure_bootstrap_logging()
    desired_state = _desired_environment_state(runtime_profile)
    environment = managed_environment_for_profile(
        runtime_profile,
        python_version=str(desired_state["pythonVersion"]),
    )
    runtime_root = environment.root_dir

    if _is_environment_initialized(environment, desired_state):
        logger.info(
            "bootstrap skipped: env at %s already matches desired state",
            runtime_root,
        )
        return environment

    # Only needed for a fresh bootstrap; an existing venv keeps working
    # even if the bundled wheelhouse is removed or moved.
    wheelhouse = _runtime_wheelhouse()
    packages = _runtime_packages_for_profile(runtime_profile)
    logger.info(
        "bootstrap start: profile=%s root=%s base_python=%s packages=%d wheelhouse=%s",
        runtime_profile,
        runtime_root,
        desired_state["pythonVersion"],
        len(packages),
        wheelhouse if wheelhouse is not None else "network",
    )

    tmp_root = runtime_root.with_name(f"{runtime_root.name}.tmp")
    shutil.rmtree(tmp_root, ignore_errors=True)
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp_env_dir = tmp_root / "venv"

    logger.info("bootstrap: creating venv at %s", tmp_env_dir)
    _create_managed_venv(tmp_env_dir)

    tmp_python = _python_executable_path(tmp_env_dir)
    if wheelhouse is None:
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

    install_command = [
        str(tmp_python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--only-binary=:all:",
    ]
    if wheelhouse is not None:
        install_command.extend(["--no-index", "--find-links", str(wheelhouse)])
    install_command.extend(packages)
    logger.info(
        "bootstrap: installing %d packages via pip (%s; %.0fs elapsed so far)",
        len(packages),
        "offline wheelhouse" if wheelhouse is not None else "network",
        time.monotonic() - started_at,
    )
    subprocess.run(install_command, check=True)

    (tmp_root / "state.json").write_text(
        json.dumps(desired_state, ensure_ascii=True, indent=2),
        "utf-8",
    )
    shutil.rmtree(runtime_root, ignore_errors=True)
    os.replace(tmp_root, runtime_root)
    # The rebuild destroyed any previous venv together with user installs and
    # their registry; drop the in-process whitelist extension to match so
    # removed modules are denied again until they are reinstalled.
    sync_user_installed_packages(runtime_profile=runtime_profile)

    logger.info(
        "bootstrap complete: env at %s ready (%.1fs)",
        environment.root_dir,
        time.monotonic() - started_at,
    )
    return managed_environment_for_profile(
        runtime_profile,
        python_version=str(desired_state["pythonVersion"]),
    )


class UserPackageInstallError(RuntimeError):
    """pip could not install the requested extra packages."""


_TOP_LEVEL_DISCOVERY_SCRIPT = """\
import json
from importlib.metadata import distributions

result = {}
for distribution in distributions():
    name = (distribution.metadata.get("Name") or "").lower()
    top_level = (distribution.read_text("top_level.txt") or "").split()
    if not top_level:
        top_level = [name.replace("-", "_")]
    result[name] = sorted(set(top_level))
print(json.dumps(result))
"""


def _discover_import_modules(
    python_executable: Path,
) -> dict[str, tuple[str, ...]]:
    """Map every installed distribution to its importable top-level names.

    Best effort: a failure here degrades to the name-guess heuristic in the
    caller, not to a failed install.
    """
    try:
        response = subprocess.run(
            [str(python_executable), "-I", "-c", _TOP_LEVEL_DISCOVERY_SCRIPT],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(response.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.warning("Could not discover importable module names: %s", exc)
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        name.lower(): tuple(modules)
        for name, modules in payload.items()
        if isinstance(name, str) and isinstance(modules, list)
    }


def _pip_install_command(
    python_executable: Path,
    specs: list[str],
    *,
    wheelhouse: Path | None,
) -> list[str]:
    command = [
        str(python_executable),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--only-binary=:all:",
    ]
    if wheelhouse is not None:
        command.extend(["--no-index", "--find-links", str(wheelhouse)])
    command.extend(specs)
    return command


def _pip_output_tail(
    completed: subprocess.CompletedProcess[str],
    *,
    lines: int = 8,
) -> str:
    """The last actionable lines of a failed pip run, for error details."""
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    relevant = [line.strip() for line in output.splitlines() if line.strip()]
    return "; ".join(relevant[-lines:]) or f"pip exited with code {completed.returncode}"


def install_user_python_packages(
    specs: list[str],
    *,
    runtime_profile: str = _DEFAULT_RUNTIME_PROFILE,
) -> PythonEnvironmentInfo:
    """Install user-requested extra packages into the prepared managed venv.

    Offline first: a configured wheelhouse is tried with ``--no-index
    --find-links`` and PyPI is used as the fallback, since the bundle ships
    only the kernel stack. New distributions (their dependencies included)
    are recorded in ``user-packages.json`` together with their importable
    top-level names, which join the in-process import whitelist. The registry
    share a lifetime with the venv: a bootstrap rebuild removes both.

    Raises :class:`ValueError` for rejected specs and
    :class:`UserPackageInstallError` when pip fails both attempts.
    """
    requested = _validate_user_package_specs(list(specs), runtime_profile=runtime_profile)

    with _BOOTSTRAP_LOCK:
        environment = _ensure_environment_locked(runtime_profile)
        python_executable = environment.python_executable
        baseline = _list_installed_package_versions(python_executable)

        try:
            wheelhouse = _runtime_wheelhouse()
        except RuntimeError as exc:
            logger.warning("Proceeding without the offline wheelhouse: %s", exc)
            wheelhouse = None

        offline = (
            subprocess.run(
                _pip_install_command(python_executable, requested, wheelhouse=wheelhouse),
                check=False,
                capture_output=True,
                text=True,
            )
            if wheelhouse is not None
            else None
        )
        completed = offline
        if offline is None or offline.returncode != 0:
            completed = subprocess.run(
                _pip_install_command(python_executable, requested, wheelhouse=None),
                check=False,
                capture_output=True,
                text=True,
            )
        if completed is not None and completed.returncode != 0:
            detail = _pip_output_tail(completed)
            if offline is not None and completed is not offline:
                detail = f"offline wheelhouse: {_pip_output_tail(offline)}; PyPI: {detail}"
            raise UserPackageInstallError(detail)

        current = _list_installed_package_versions(python_executable)
        added = {
            name: version
            for name, version in current.items()
            if name not in baseline or baseline[name] != version
        }

        if added:
            modules_by_name = _discover_import_modules(python_executable)
            registry = _read_user_installed_packages(runtime_profile)
            for name, version in added.items():
                spec = next(
                    (raw for raw in requested if _canonical_distribution_name(raw) == name),
                    "",
                )
                registry[name] = UserInstalledPackage(
                    name=name,
                    spec=spec or f"{name}=={version}",
                    modules=modules_by_name.get(name, (name.replace("-", "_"),)),
                )
            _write_user_installed_packages(runtime_profile, registry)
            sync_user_installed_packages(runtime_profile=runtime_profile)
            logger.info(
                "Installed user packages: %s",
                ", ".join(f"{name}=={version}" for name, version in sorted(added.items())),
            )

    return _report_environment(runtime_profile, initialized=True)
