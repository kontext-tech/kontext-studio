"""Shared Python validation policy for managed execution."""

from __future__ import annotations

import ast
import logging
import symtable

logger = logging.getLogger(__name__)

# Version-pinned manifest of the third-party stack the managed execution venv
# ships. Kept in exact lockstep with ``_DEFAULT_PACKAGES`` in py/kontext-runtime
# (``kontext/runtime/python_environment.py``); that package's tests pin the two
# together at name *and* version, because every mismatch costs an execution
# round: whitelisted-but-uninstalled imports die with ModuleNotFoundError, and
# installed-but-unlisted imports are denied. The versions also feed the agent
# prompt environment line, so they must stay accurate. Import-facing names:
# ``scikit-learn`` provides top-level ``sklearn``; ``pytz`` ships only for
# duckdb's TIMESTAMPTZ handling but is importable.
MANAGED_VENV_PACKAGES = (
    "numpy==2.2.5",
    "pandas==2.2.3",
    "pyarrow==19.0.1",
    "scikit-learn==1.6.1",
    "scipy==1.15.3",
    "statsmodels==0.14.4",
    "patsy==1.0.1",
    "duckdb==1.3.2",
    "pytz==2025.2",
    "matplotlib==3.10.1",
)

# PyPI distribution names that differ from their top-level import name. Public
# so prompt builders can present pin-faithful display names.
DISTRIBUTION_TO_IMPORT_NAME = {"scikit-learn": "sklearn"}

MANAGED_VENV_MODULES = frozenset(
    DISTRIBUTION_TO_IMPORT_NAME.get(spec.split("==", 1)[0], spec.split("==", 1)[0])
    for spec in MANAGED_VENV_PACKAGES
)

# Curated stdlib: execution-free utilities safe to import in submitted cells.
_SAFE_STDLIB_MODULES = frozenset(
    {
        # Introspection (frames are as reachable via vars() as via
        # currentframe(), so this adds no new capability class to the sandbox).
        "inspect",
        "abc",
        "copy",
        "csv",
        "dataclasses",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "hashlib",
        "numbers",
        "operator",
        "platform",
        "secrets",
        "string",
        "struct",
        "textwrap",
        "time",
        "types",
        "uuid",
        "warnings",
        "zlib",
        "collections",
        "datetime",
        "itertools",
        "math",
        "random",
        "re",
        "statistics",
        "typing",
        "json",
        "io",
        "base64",
    }
)

# Injected platform helpers: preloaded into submitted cells, so imports are
# accepted for cells that do it explicitly.
_PLATFORM_MODULES = frozenset({"kontext"})

WHITELISTED_MODULES = MANAGED_VENV_MODULES | _SAFE_STDLIB_MODULES | _PLATFORM_MODULES

BLACKLISTED_BUILTINS = {
    # Dynamic code creation and namespace/builtin tampering — the capability
    # bans that the runtime gates re-enforce for user frames. Reflection
    # *reads* (``getattr``, ``globals``, ``locals``) are deliberately absent:
    # they are trivially equivalent to allowed constructs (``vars(obj)``,
    # ``vars()``), so banning them cost agent rounds without buying
    # protection. ``open`` is also absent: the kernel child confines file
    # access at runtime instead, so submitted code may write/read within the
    # allowed roots.
    "__import__",
    "exec",
    "eval",
    "compile",
    "setattr",
    "delattr",
    "input",
    "breakpoint",
}

BLACKLISTED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "shutil",
    "threading",
    "multiprocessing",
    "ctypes",
    # importlib must stay blocked: importlib.import_module() reaches the
    # import machinery directly, without calling builtins.__import__, so the
    # kernel's confined-import gate cannot catch it.
    "importlib",
    "pickle",
    "marshal",
    "runpy",
    "shelve",
    "dbm",
}

# Rejections whose legitimate need has a sanctioned in-cell alternative are
# taught inline, so one rejection costs the agent no extra reasoning round.
_BLACKLIST_HINTS = {
    "sys": (
        "capture versions with `platform.python_version()` and package dunder "
        "reads (e.g. `pandas.__version__`)"
    ),
    "importlib": (
        "read package versions via package dunders (e.g. `pandas.__version__`); "
        "importlib stays blocked because import_module bypasses the import gate"
    ),
}

COMMON_ALIAS_IMPORTS = {
    "np": "import numpy as np",
    "pd": "import pandas as pd",
    "plt": "import matplotlib.pyplot as plt",
}

# Dunder reads that make up the classic sandbox-escape toolkit (climbing to
# module globals/builtins or fabricating function objects). Plain introspection
# dunders (`__name__`, `__version__`, `__dict__`, `__class__`, ...) stay
# allowed for loads: reading them is routine in analysis cells, while the
# runtime import/exec gates plus process isolation carry the real containment.
_SANDBOX_ESCAPE_DUNDERS = frozenset(
    {
        "__globals__",
        "__builtins__",
        "__code__",
        "__closure__",
        "__subclasses__",
        "__bases__",
        "__mro__",
    }
)


def _collect_missing_common_alias_issues(code: str) -> list[str]:
    try:
        root_table = symtable.symtable(code, "<submitted-python>", "exec")
    except SyntaxError:
        return []

    issues: set[str] = set()

    def visit_scope(
        table: symtable.SymbolTable,
        inherited_names: set[str],
    ) -> None:
        local_names = {
            symbol.get_name()
            for symbol in table.get_symbols()
            if symbol.is_imported() or symbol.is_assigned() or symbol.is_parameter()
        }
        visible_names = inherited_names | local_names

        for alias, import_statement in COMMON_ALIAS_IMPORTS.items():
            if alias not in table.get_identifiers():
                continue

            symbol = table.lookup(alias)
            if symbol.is_referenced() and alias not in visible_names:
                issues.add(
                    f"Alias '{alias}' is used but not defined. Add "
                    f"`{import_statement}` before using it. Managed Python "
                    "execution runs submitted code in isolation, so include "
                    "required imports in the code you execute."
                )

        for child in table.get_children():
            child_inherited_names = visible_names
            if table.get_type() == "class" and child.get_type() == "function":
                child_inherited_names = inherited_names
            visit_scope(child, child_inherited_names)

    visit_scope(root_table, set())
    return sorted(issues)


def validate_python_code(code: str, *, shared_namespace: bool = False) -> tuple[bool, list[str]]:
    """Validate Python code using AST-based guardrails.

    :param code: Submitted source code.
    :param shared_namespace: Whether the code runs in a persistent session
        kernel whose namespace may already contain imports and variables from
        earlier cells. When True, the "alias used but not defined" guidance is
        skipped: a genuinely missing import surfaces at execution time as a
        normal ``NameError`` the agent can fix by importing.
    """
    issues: list[str] = []

    if not code or not code.strip():
        return True, []

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [f"Syntax Error: {exc.msg} at line {exc.lineno}"]
    except Exception as exc:
        logger.error("Failed to parse Python code: %s", exc)
        return False, [f"Parse Error: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base_module = alias.name.split(".")[0]
                if base_module in BLACKLISTED_MODULES:
                    message = f"Forbidden import: '{alias.name}'"
                    hint = _BLACKLIST_HINTS.get(base_module)
                    issues.append(message if hint is None else f"{message} — {hint}")
                elif base_module not in WHITELISTED_MODULES:
                    issues.append(
                        f"Module '{alias.name}' is not in the whitelist. Contact support if you need this library."
                    )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                base_module = node.module.split(".")[0]
                if base_module in BLACKLISTED_MODULES:
                    message = f"Forbidden import from: '{node.module}'"
                    hint = _BLACKLIST_HINTS.get(base_module)
                    issues.append(message if hint is None else f"{message} — {hint}")
                elif base_module not in WHITELISTED_MODULES:
                    issues.append(
                        f"Module '{node.module}' is not in the whitelist. Contact support if you need this library."
                    )

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLACKLISTED_BUILTINS:
                issues.append(f"Forbidden function call: '{node.func.id}'")
            elif isinstance(node.func, ast.Attribute) and node.func.attr in {
                "system",
                "popen",
                "spawn",
            }:
                issues.append(f"Forbidden attribute call: '{node.func.attr}'")

        elif isinstance(node, ast.Attribute):
            if node.attr in _SANDBOX_ESCAPE_DUNDERS:
                issues.append(f"Forbidden access to sandbox escape vector: '{node.attr}'")
            elif node.attr.startswith("__") and not isinstance(node.ctx, ast.Load):
                issues.append(f"Forbidden modification of dunder attribute: '{node.attr}'")

        elif (
            isinstance(node, ast.Name)
            and node.id in BLACKLISTED_BUILTINS
            and not isinstance(node.ctx, ast.Load)
        ):
            issues.append(f"Forbidden modification of built-in: '{node.id}'")

    if not shared_namespace:
        issues.extend(_collect_missing_common_alias_issues(code))

    unique_issues = sorted(set(issues))
    return len(unique_issues) == 0, unique_issues
