"""Consistency between the managed venv and the shared import policy.

``MANAGED_VENV_PACKAGES``/``MANAGED_VENV_MODULES`` is what agent prompts teach
and what ``validate_python_code`` plus the kernel import hook enforce; the
runtime package list is what the managed venv actually installs. Out of
lockstep, submitted code is either denied a module its sandbox ships or
allowed a module that is missing there — both cost an execution round, and a
version mismatch teaches agents stale environment facts. The user-package
installer shares those stakes: its registry feeds the same whitelist.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import kontext.common.python_execution.policy as python_policy
from kontext.common.python_execution.policy import (
    DISTRIBUTION_TO_IMPORT_NAME,
    MANAGED_VENV_MODULES,
    MANAGED_VENV_PACKAGES,
)
from kontext.kernel.contracts import DEFAULT_RUNTIME_PROFILE
from kontext.runtime.python_environment import (
    UserPackageInstallError,
    _create_managed_venv,
    _desired_environment_state,
    _parse_package_spec,
    _python_executable_path,
    _runtime_packages_for_profile,
    default_runtime_packages,
    ensure_managed_python_environment,
    install_user_python_packages,
    managed_environment_for_profile,
)
from kontext.schema import PythonPackageSource


@pytest.fixture
def _clean_whitelist_extension(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the process-wide whitelist extension between tests."""
    monkeypatch.setattr(python_policy, "_USER_INSTALLED_MODULES", frozenset())


def test_whitelist_matches_managed_venv_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The policy's venv manifest and the default package list are identical."""
    # Pin the built-in defaults: the KONTEXT_PYTHON_RUNTIME_PACKAGES override
    # is a deployment choice, and the policy must track the shipped default.
    monkeypatch.delenv("KONTEXT_PYTHON_RUNTIME_PACKAGES", raising=False)

    installed = dict(
        _parse_package_spec(spec) for spec in _runtime_packages_for_profile(DEFAULT_RUNTIME_PROFILE)
    )
    # Import-facing names for the lockstep comparison; the raw distribution
    # names are checked separately below.
    installed_by_import_name = {
        DISTRIBUTION_TO_IMPORT_NAME.get(name, name): version for name, version in installed.items()
    }
    pinned = {
        DISTRIBUTION_TO_IMPORT_NAME.get(name, name): version
        for name, version in (spec.split("==", 1) for spec in MANAGED_VENV_PACKAGES)
    }

    # Names and versions must line up both directions; every declared
    # distribution-name mapping must actually exist in the runtime manifest.
    assert installed_by_import_name == pinned
    assert set(DISTRIBUTION_TO_IMPORT_NAME) <= set(installed)
    assert set(pinned) == MANAGED_VENV_MODULES


def test_ensure_managed_python_environment_uses_offline_wheelhouse(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A desktop wheelhouse must install without touching an index."""
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    monkeypatch.setenv("KONTEXT_PYTHON_RUNTIME_WHEELHOUSE", str(wheelhouse))
    monkeypatch.delenv("KONTEXT_PYTHON_RUNTIME_PACKAGES", raising=False)
    monkeypatch.setattr(
        "kontext.runtime.python_environment.get_local_data_dir",
        lambda: tmp_path,
    )

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0)

    def fake_create_venv(env_dir: Path) -> None:
        env_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "kontext.runtime.python_environment._create_managed_venv",
        fake_create_venv,
    )

    ensure_managed_python_environment()

    # The pip/setuptools upgrade step is skipped: those wheels may not be in
    # the bundle, and ensurepip already provided a working pip.
    assert len(calls) == 1
    install = calls[0]
    assert "--no-index" in install
    assert "--find-links" in install
    assert str(wheelhouse) in install
    assert "--upgrade" not in install


def test_missing_wheelhouse_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "KONTEXT_PYTHON_RUNTIME_WHEELHOUSE",
        str(tmp_path / "missing"),
    )

    with pytest.raises(RuntimeError, match="missing directory"):
        ensure_managed_python_environment()


def test_default_runtime_packages_ignores_the_deployment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The desktop wheelhouse must use the shipped pins, not a deployment override."""
    monkeypatch.setenv("KONTEXT_PYTHON_RUNTIME_PACKAGES", "numpy==1.0")

    packages = default_runtime_packages()

    assert "numpy==2.2.5" in packages
    assert "numpy==1.0" not in packages


def test_managed_venv_interpreter_can_run_pip(tmp_path: Path) -> None:
    """The created interpreter must start and import pip.

    A copied uv-managed CPython cannot find libpython relative to the venv
    binary, so ensurepip aborts during creation. Symlinked interpreters keep
    the base layout and run normally.
    """
    env_dir = tmp_path / "venv"
    _create_managed_venv(env_dir)

    python = _python_executable_path(env_dir)
    if os.name != "nt":
        assert python.is_symlink()

    result = subprocess.run(
        [str(python), "-c", "import pip; print(pip.__version__)"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


# ── user-package installs ────────────────────────────────────────────────────


def _prepared_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A managed environment that looks initialized without building a venv."""
    monkeypatch.setattr("kontext.runtime.python_environment.get_local_data_dir", lambda: tmp_path)
    environment = managed_environment_for_profile(DEFAULT_RUNTIME_PROFILE)
    environment.root_dir.mkdir(parents=True, exist_ok=True)
    environment.python_executable.parent.mkdir(parents=True, exist_ok=True)
    environment.python_executable.touch()
    environment.root_dir.joinpath("state.json").write_text(
        json.dumps(_desired_environment_state(DEFAULT_RUNTIME_PROFILE)), "utf-8"
    )
    return environment


def test_install_rejects_specs_pip_must_not_receive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _clean_whitelist_extension: None,
) -> None:
    _prepared_environment(tmp_path, monkeypatch)

    for bad_spec in ("-r requirements.txt", "sympy>=1.5", "http://x/pkg.whl", "sympy m"):
        with pytest.raises(ValueError, match="not a valid package spec"):
            install_user_python_packages([bad_spec])

    with pytest.raises(ValueError, match="provisioned by the managed runtime"):
        install_user_python_packages(["numpy"])

    with pytest.raises(ValueError, match="notebook execution forbids"):
        install_user_python_packages(["requests"])

    with pytest.raises(ValueError, match="No packages"):
        install_user_python_packages([])


def test_install_tries_the_wheelhouse_then_falls_back_to_pypi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _clean_whitelist_extension: None,
) -> None:
    """Offline find-links runs first; the fallback installs and records deps."""
    environment = _prepared_environment(tmp_path, monkeypatch)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    monkeypatch.setenv("KONTEXT_PYTHON_RUNTIME_WHEELHOUSE", str(wheelhouse))

    installed_versions = {"numpy": "2.2.5"}

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        cmd = list(command)
        if "-c" in cmd:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"sympy": ["sympy"], "mpmath": ["mpmath"]}),
                stderr="",
            )
        if cmd[2:4] == ["pip", "list"]:
            payload = [
                {"name": name, "version": version} for name, version in installed_versions.items()
            ]
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")
        if cmd[3] == "install":
            if "--no-index" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 1, stdout="", stderr="ERROR: No matching distribution found for sympy"
                )
            assert "--no-index" not in cmd
            installed_versions.update({"sympy": "1.13.1", "mpmath": "1.3.0"})
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Successfully installed mpmath sympy", stderr=""
            )
        raise AssertionError(f"Unexpected subprocess call: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    info = install_user_python_packages(["sympy==1.13.1"])

    entries = {
        entry["name"]: entry
        for entry in json.loads(
            environment.root_dir.joinpath("user-packages.json").read_text("utf-8")
        )
    }
    assert set(entries) == {"sympy", "mpmath"}
    assert entries["sympy"]["spec"] == "sympy==1.13.1"
    assert entries["sympy"]["modules"] == ["sympy"]
    assert entries["mpmath"]["modules"] == ["mpmath"]

    assert python_policy.user_installed_modules() == frozenset({"sympy", "mpmath"})

    extras = [(pkg.name, pkg.version) for pkg in info.packages if pkg.user_installed]
    assert sorted(extras) == [("mpmath", "1.3.0"), ("sympy", "1.13.1")]
    assert info.package_source == PythonPackageSource.INSTALLED


def test_install_prefers_the_offline_wheelhouse_when_it_has_the_wheel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _clean_whitelist_extension: None,
) -> None:
    """A successful offline run never touches the network fallback."""
    _prepared_environment(tmp_path, monkeypatch)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    monkeypatch.setenv("KONTEXT_PYTHON_RUNTIME_WHEELHOUSE", str(wheelhouse))

    installed_versions = {"numpy": "2.2.5"}

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        cmd = list(command)
        if "-c" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps({"sympy": ["sympy"]}), stderr=""
            )
        if cmd[2:4] == ["pip", "list"]:
            payload = [
                {"name": name, "version": version} for name, version in installed_versions.items()
            ]
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")
        assert cmd[3] == "install" and "--no-index" in cmd
        installed_versions.update({"sympy": "1.13.1"})
        return subprocess.CompletedProcess(cmd, 0, stdout="Successfully installed sympy", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    install_user_python_packages(["sympy==1.13.1"])

    assert python_policy.user_installed_modules() == frozenset({"sympy"})


def test_install_failure_reports_pip_output_and_records_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _clean_whitelist_extension: None,
) -> None:
    environment = _prepared_environment(tmp_path, monkeypatch)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    monkeypatch.setenv("KONTEXT_PYTHON_RUNTIME_WHEELHOUSE", str(wheelhouse))

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        cmd = list(command)
        if cmd[2:4] == ["pip", "list"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps([{"name": "numpy", "version": "2.2.5"}]), stderr=""
            )
        assert cmd[3] == "install"
        message = "offline" if "--no-index" in cmd else "pypi"
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=f"No wheels: {message}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(
        UserPackageInstallError,
        match=r"offline wheelhouse: .*No wheels: offline.*PyPI: .*No wheels: pypi",
    ):
        install_user_python_packages(["sympy==1.13.1"])

    assert not environment.root_dir.joinpath("user-packages.json").exists()
    assert python_policy.user_installed_modules() == frozenset()


def test_rebootstrap_removes_user_installs_and_their_whitelist_extension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _clean_whitelist_extension: None,
) -> None:
    """The registry lives with the venv: a rebuild must not leave stale trusts."""
    environment = _prepared_environment(tmp_path, monkeypatch)
    monkeypatch.setattr(python_policy, "_USER_INSTALLED_MODULES", frozenset({"sympy"}))

    user_packages_file = environment.root_dir / "user-packages.json"
    user_packages_file.write_text(
        json.dumps([{"name": "sympy", "spec": "sympy==1.13.1", "modules": ["sympy"]}]),
        "utf-8",
    )
    # Make the recorded state stale so ensure rebuilds the venv.
    environment.root_dir.joinpath("state.json").write_text('{"stale": true}', "utf-8")

    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    monkeypatch.setenv("KONTEXT_PYTHON_RUNTIME_WHEELHOUSE", str(wheelhouse))

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def fake_create_venv(env_dir: Path) -> None:
        env_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("kontext.runtime.python_environment._create_managed_venv", fake_create_venv)

    ensure_managed_python_environment()

    assert not user_packages_file.exists()
    assert python_policy.user_installed_modules() == frozenset()
