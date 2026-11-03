"""Unit tests for the async-cell binding collector in the kernel harness.

``await``-using cells are compiled inside an async wrapper, so a variable only
survives into later cells when the wrapper declares it ``global``. These tests
pin the binding rules directly on the AST without spawning a kernel process.
"""

from __future__ import annotations

import ast

from kontext.kernel.harness import _collect_function_scope_bindings


def _bindings(code: str) -> list[str]:
    tree = ast.parse(code)
    return _collect_function_scope_bindings(tree.body)


def test_collects_top_level_assignments_and_tuple_unpacking() -> None:
    code = "x = 1\na, b = f()\nfirst, *rest = g()"
    assert _bindings(code) == ["x", "a", "b", "first", "rest"]


def test_collects_for_and_with_targets() -> None:
    code = "for i, item in enumerate(rows):\n    pass\nwith open_context() as handle:\n    pass"
    assert _bindings(code) == ["i", "item", "handle"]


def test_collects_import_bound_names() -> None:
    code = (
        "import numpy as np\nimport pandas\nfrom statsmodels.api import OLS as Ols\nfrom x import *"
    )
    assert _bindings(code) == ["np", "pandas", "Ols"]


def test_collects_augassign_and_delete_targets() -> None:
    code = "total += 1\ndel scratch"
    assert _bindings(code) == ["total", "scratch"]


def test_collects_bound_names_inside_control_flow() -> None:
    code = (
        "if flag:\n    found = 1\nelse:\n    found = 0\n"
        "try:\n    value = load()\nexcept ValueError:\n    value = None\n"
        "while False:\n    other = 2\n"
        "for _ in items:\n    inner = _\n"
        "try:\n    pass\nfinally:\n    last = 3"
    )
    assert set(_bindings(code)) == {"found", "value", "other", "_", "inner", "last"}


def test_collects_walrus_bindings_in_any_position() -> None:
    code = "if (matched := probe()):\n    pass\nkeep = (kept := 1)"
    assert set(_bindings(code)) == {"matched", "keep", "kept"}


def test_collects_match_pattern_captures_but_not_the_subject() -> None:
    code = (
        "match payload:\n"
        "    case {'amount': amount, **rest}:\n"
        "        pass\n"
        "    case [head, *tail]:\n"
        "        pass\n"
        "    case other:\n"
        "        pass"
    )
    assert set(_bindings(code)) == {"amount", "rest", "head", "tail", "other"}


def test_excludes_nested_scopes_and_comprehension_targets() -> None:
    code = (
        "def helper():\n    hidden = 1\n"
        "class Box:\n    attr = 2\n"
        "fn = lambda: lam_local\n"
        "vals = [entry for entry in source]\n"
        "paired = {key: value for key, value in pairs}"
    )
    assert set(_bindings(code)) == {"helper", "Box", "fn", "vals", "paired"}


def test_filters_import_from_star_and_dunder_names() -> None:
    code = "__version__ = 1\n__all__ = []\nfrom mod import *"
    assert _bindings(code) == []
