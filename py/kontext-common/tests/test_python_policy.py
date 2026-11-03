"""Tests for the managed-Python validation policy flags."""

from __future__ import annotations

import pytest

from kontext.common.python_execution.policy import validate_python_code


def test_alias_guidance_flags_missing_import_by_default() -> None:
    """First cells in an isolated namespace get the add-the-import guidance."""
    is_valid, issues = validate_python_code("print(np.zeros(1))")

    assert not is_valid
    assert any("import numpy as np" in issue for issue in issues)


def test_shared_namespace_skips_only_the_alias_check() -> None:
    """Cells in a persistent session kernel may reuse aliases from earlier cells."""
    is_valid, issues = validate_python_code("print(np.zeros(1))", shared_namespace=True)

    assert is_valid, issues


def test_shared_namespace_keeps_every_other_policy_rule() -> None:
    """The persistence flag must not weaken the security guardrails."""
    is_valid, issues = validate_python_code(
        "import os\nsecret = (lambda: 1).__globals__", shared_namespace=True
    )

    assert not is_valid
    joined = ", ".join(issues)
    assert "Forbidden import: 'os'" in joined
    assert "escape vector" in joined


def test_unwhitelisted_import_is_still_rejected_in_shared_namespace() -> None:
    is_valid, issues = validate_python_code("import sympy", shared_namespace=True)

    assert not is_valid
    assert any("not in the whitelist" in issue for issue in issues)


@pytest.mark.parametrize(
    "module",
    [
        # Data/analytics stack.
        "pandas",
        "numpy",
        "pyarrow",
        "duckdb",
        "sklearn",
        "statsmodels",
        "scipy",
        "patsy",
        "matplotlib",
        # File/network/process/exec-free stdlib utilities.
        "inspect",
        "functools",
        "textwrap",
        "copy",
        "warnings",
        "time",
        "enum",
        "dataclasses",
        "decimal",
        "fractions",
        "uuid",
        "hashlib",
        "secrets",
        "operator",
        "string",
        "abc",
        "numbers",
        "struct",
        "csv",
        "zlib",
        "platform",
        "types",
    ],
)
def test_whitelist_accepts_analytics_and_safe_stdlib_modules(module: str) -> None:
    is_valid, issues = validate_python_code(f"import {module}")

    assert is_valid, issues


def test_restricted_capability_modules_stay_rejected() -> None:
    """File/network/process/exec-capable modules keep the isolation line."""
    for module in ("os", "sys", "subprocess", "socket", "pathlib", "logging", "gzip"):
        is_valid, issues = validate_python_code(f"import {module}")

        assert not is_valid, module
        assert any("whitelist" in issue or "Forbidden" in issue for issue in issues), (
            module,
            issues,
        )


def test_introspection_reads_are_allowed() -> None:
    """Reflection *reads* pass pre-flight: the real gates live at kernel runtime.

    These are the idioms that used to cost agent rounds: typing an exception,
    reading a package version, optional-capability detection, frame-free
    introspection equivalents.
    """
    code = (
        "label = type(error).__name__\n"
        "version = pandas.__version__\n"
        "shape = data.__dict__\n"
        "handle = getattr(source, 'head', None)\n"
        "namespace = vars(source)\n"
    )

    is_valid, issues = validate_python_code(code)

    assert is_valid, issues


def test_dunder_writes_stay_rejected() -> None:
    """Allowing introspection reads must not reopen builtin/namespace tampering."""
    for statement in (
        "target.__class__ = int",
        "del target.__doc__",
    ):
        is_valid, issues = validate_python_code(statement, shared_namespace=True)

        assert not is_valid, statement
        assert any("modification" in issue for issue in issues), (statement, issues)


def test_escape_vector_dunders_stay_rejected() -> None:
    """The sandbox-escape toolkit (globals, code objects, class climbing) stays denied."""
    for statement in (
        "seed = (lambda: 1).__globals__",
        "code = sample.__code__",
        "kids = parent.__subclasses__",
        "chain = parent.__mro__",
    ):
        is_valid, issues = validate_python_code(statement, shared_namespace=True)

        assert not is_valid, statement
        assert any("escape vector" in issue for issue in issues), (statement, issues)


def test_sys_and_importlib_rejections_teach_the_alternative() -> None:
    """Version-reporting needs point straight at the sanctioned in-cell path."""
    for code, needle in (
        ("import sys", "platform.python_version()"),
        ("import importlib.metadata", "__version__"),
        ("from importlib import metadata", "__version__"),
    ):
        is_valid, issues = validate_python_code(code, shared_namespace=True)

        assert not is_valid, code
        assert any(needle in issue for issue in issues), (code, issues)


def test_open_is_allowed_at_validation_and_confined_at_runtime() -> None:
    """`open()` is no longer banned pre-flight; the kernel confines it instead."""
    is_valid, issues = validate_python_code("handle = open('/tmp/x')")

    assert is_valid, issues
