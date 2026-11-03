"""Consistency between the managed venv and the shared import policy.

``MANAGED_VENV_PACKAGES``/``MANAGED_VENV_MODULES`` is what agent prompts teach
and what ``validate_python_code`` plus the kernel import hook enforce; the
runtime package list is what the managed venv actually installs. Out of
lockstep, submitted code is either denied a module its sandbox ships or
allowed a module that is missing there — both cost an execution round, and a
version mismatch teaches agents stale environment facts.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from kontext.common.python_execution.policy import (
    DISTRIBUTION_TO_IMPORT_NAME,
    MANAGED_VENV_MODULES,
    MANAGED_VENV_PACKAGES,
)
from kontext.kernel.contracts import DEFAULT_RUNTIME_PROFILE
from kontext.runtime.python_environment import (
    _create_managed_venv,
    _parse_package_spec,
    _python_executable_path,
    _runtime_packages_for_profile,
)


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
