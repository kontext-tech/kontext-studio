"""Tests for the managed Python environment and the runner contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from kontext.common.python_execution.policy import validate_python_code
from kontext.kernel.contracts import PythonRunnerRequest, PythonRunnerResult
from kontext.runtime import create_python_runner_backend
from kontext.runtime.python_environment import (
    ManagedEnvironment,
    _runtime_packages_for_profile,
    get_managed_python_environment_info,
    prepare_managed_python_environment,
    resolve_managed_python_executable,
)


def test_runtime_packages_support_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "KONTEXT_PYTHON_RUNTIME_PACKAGES",
        "numpy==1.0.0, pandas==2.0.0",
    )

    assert _runtime_packages_for_profile("ml-default") == (
        "numpy==1.0.0",
        "pandas==2.0.0",
    )


def test_create_python_runner_backend_returns_kernel() -> None:
    from kontext.kernel.runner import KernelPythonRunnerBackend

    backend = create_python_runner_backend("kernel")
    assert isinstance(backend, KernelPythonRunnerBackend)


def test_create_python_runner_backend_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported python runner backend"):
        create_python_runner_backend("unknown-backend")


def test_get_managed_python_environment_info_uses_configured_packages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kontext.runtime.python_environment.get_local_data_dir", lambda: tmp_path)

    info = get_managed_python_environment_info()

    assert info.available is True
    # A fresh data dir has no venv, so the environment is not initialized.
    assert info.initialized is False
    assert info.package_source == "configured"
    assert "Managed CPython Local" in (info.display_label or "")
    assert any(package.name == "numpy" for package in info.packages)


def test_prepare_managed_python_environment_returns_installed_package_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_env = ManagedEnvironment(
        root_dir=tmp_path,
        python_executable=tmp_path / "python",
        state_path=tmp_path / "state.json",
    )
    monkeypatch.setattr(
        "kontext.runtime.python_environment.ensure_managed_python_environment",
        lambda _profile: fake_env,
    )
    monkeypatch.setattr(
        "kontext.runtime.python_environment._list_installed_package_versions",
        lambda _exe: {"numpy": "9.9.9", "matplotlib": "3.10.1"},
    )

    info = prepare_managed_python_environment()

    assert info.available is True
    assert info.initialized is True
    assert info.package_source == "installed"
    versions = {package.name: package.version for package in info.packages}
    assert versions["matplotlib"] == "3.10.1"


def test_resolve_managed_python_executable_falls_back_when_unprepared(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kontext.runtime.python_environment.get_local_data_dir", lambda: tmp_path)

    import sys

    assert resolve_managed_python_executable() == sys.executable


def test_validate_python_code_rejects_forbidden_imports() -> None:
    is_valid, issues = validate_python_code("import subprocess\nprint('x')")
    assert is_valid is False
    assert "Forbidden import: 'subprocess'" in issues


@pytest.mark.parametrize(
    ("code", "expected_import"),
    [
        ("values = np.array([1, 2, 3])", "import numpy as np"),
        ("frame = pd.DataFrame({'x': [1]})", "import pandas as pd"),
        ("plt.figure()", "import matplotlib.pyplot as plt"),
    ],
)
def test_validate_python_code_rejects_missing_common_alias_imports(
    code: str,
    expected_import: str,
) -> None:
    is_valid, issues = validate_python_code(code)
    assert is_valid is False
    assert any(expected_import in issue for issue in issues)


def test_runner_contract_types_are_importable() -> None:
    request = PythonRunnerRequest(code="1 + 1", data_payloads={})
    result = PythonRunnerResult(
        success=True, message="ok", error=None, outputs=[], stdout="", stderr=""
    )
    assert request.timeout_seconds == 300
    assert request.memory_limit_mb == 8192
    assert request.workspace_limit_bytes == 1073741824
    assert result.success is True
