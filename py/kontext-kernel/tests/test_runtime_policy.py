"""End-to-end tests for confined dynamic execution in the kernel child.

The pre-flight AST policy bans ``exec``/``eval``/``compile``/``__import__`` as
*names*, but the real builtins dict is reachable through dynamic paths
(``vars(module)['builtins']``) that no AST policy can see. Enforcement happens
on the builtins themselves in the kernel child: stubs apply the
whitelist/blacklist rules only when the immediate caller frame runs in the
persistent user namespace, and delegate to the originals for library frames
(numpy/pandas internally import ``os`` — that must keep working).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from kontext.kernel import harness
from kontext.kernel.session_runner import SessionRunner
from kontext.kernel.sessions import SessionKernelManager

pytestmark = pytest.mark.asyncio


def test_supervisor_env_names_stay_in_sync_with_shared_constants() -> None:
    """The stdlib-only child mirrors these names as literals.

    A rename on either side would silently disable runtime confinement (the
    child would read an unset variable), so pin the pairing here.
    """
    from kontext.common.constants.env_vars import StorageEnvVars

    assert harness._OPEN_ROOTS_ENV == StorageEnvVars.OPEN_ROOTS
    assert harness._WHITELISTED_MODULES_ENV == StorageEnvVars.WHITELISTED_MODULES
    assert harness._BLACKLISTED_MODULES_ENV == StorageEnvVars.BLACKLISTED_MODULES


def test_env_module_set_distinguishes_unconfigured_from_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unconfigured list must degrade to pre-flight-only, not deny-all."""
    monkeypatch.delenv("KONTEXT_WHITELISTED_MODULES", raising=False)
    assert harness._env_module_set("KONTEXT_WHITELISTED_MODULES") is None

    monkeypatch.setenv("KONTEXT_WHITELISTED_MODULES", "")
    assert harness._env_module_set("KONTEXT_WHITELISTED_MODULES") is None

    monkeypatch.setenv("KONTEXT_WHITELISTED_MODULES", "json")
    assert harness._env_module_set("KONTEXT_WHITELISTED_MODULES") == frozenset({"json"})


async def _boot(tmp_path: Path) -> tuple[SessionKernelManager, SessionRunner]:
    manager = SessionKernelManager(workspace_root=tmp_path / "workspaces")
    await manager.start()
    return manager, SessionRunner(manager)


def _stdout(result) -> str:
    return " ".join(
        str(output.get("content", ""))
        for output in result.outputs or []
        if output.get("type") == "text"
    )


async def test_runtime_import_deny_blacklisted_module(tmp_path: Path) -> None:
    """The dict route to ``__import__`` must mirror the import blacklist."""
    manager, runner = await _boot(tmp_path)
    try:
        result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "os_module = builtins_dict['__import__']('os')\n"
                "print(os_module.getpid() > 0)"
            ),
        )
    finally:
        await manager.shutdown()

    assert not result.success
    assert "Forbidden import: 'os'" in (result.error or "")


async def test_runtime_import_deny_unwhitelisted_module(tmp_path: Path) -> None:
    manager, runner = await _boot(tmp_path)
    try:
        result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "mod = builtins_dict['__import__']('sympy')\n"
                "print('imported')"
            ),
        )
    finally:
        await manager.shutdown()

    assert not result.success
    assert "not in the managed-cells whitelist" in (result.error or "")


async def test_runtime_allowed_import_still_works(tmp_path: Path) -> None:
    """Confinement is a policy check, not a blanket deny; bindings persist."""
    manager, runner = await _boot(tmp_path)
    try:
        result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "json_mod = builtins_dict['__import__']('json')\n"
                "json_mod.dumps({'a': 1})"
            ),
        )
        follow = await runner.run(session_id="s1", code="json.dumps({'a': 1})")
    finally:
        await manager.shutdown()

    assert result.success, result.error
    assert follow.success, follow.error
    assert '{"a": 1}' in _stdout(follow)


async def test_runtime_exec_eval_compile_denied(tmp_path: Path) -> None:
    """exec/eval/compile reached dynamically must not run user-supplied code."""
    manager, runner = await _boot(tmp_path)
    try:
        exec_result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "builtins_dict['exec'](\"import os\\nprint(os.getpid())\")"
            ),
        )
        eval_result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "builtins_dict['eval']('2 ** 10')"
            ),
        )
        compile_result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "builtins_dict['compile']('1 + 1', '<cell>', 'eval')"
            ),
        )
    finally:
        await manager.shutdown()

    for result in (exec_result, eval_result, compile_result):
        assert not result.success
        assert "Dynamic execution" in (result.error or ""), result.error


async def test_library_frames_delegate(tmp_path: Path) -> None:
    """Whitelisted stdlib packages whose internals import more modules keep working.

    ``dataclasses`` imports ``inspect``/``copy`` machinery at module-exec time;
    under the confinement those frames are library frames, so the stub must
    delegate instead of applying the whitelist.
    """
    manager, runner = await _boot(tmp_path)
    try:
        result = await runner.run(
            session_id="s1",
            code=(
                "import dataclasses\n"
                "import json\n"
                "point = dataclasses.make_dataclass('Point', [('x', int)])\n"
                "json.dumps([point.x for point in [point(3)]])"
            ),
        )
    finally:
        await manager.shutdown()

    assert result.success, result.error
    assert "[3]" in _stdout(result)


async def test_exec_denied_is_independent_of_supervisor_lists(tmp_path: Path) -> None:
    """Dynamic execution stays denied even if the parent env lacks the lists.

    The supervisor injects the whitelist/blacklist into the child's scrubbed
    environment, and the exec/eval/compile stubs do not consult them at all —
    only import confinement does. (A truly unconfigured child, e.g. a manual
    ``harness.py`` spawn, degrades to unconfined imports; that is covered by
    the ``_env_module_set`` unit test.)
    """
    manager, runner = await _boot(tmp_path)
    try:
        exec_result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "builtins_dict['exec']('print(\"escaped\")')"
            ),
        )
        import_result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "print(builtins_dict['__import__']('json').dumps({}))"
            ),
        )
    finally:
        await manager.shutdown()

    assert not exec_result.success
    assert "Dynamic execution" in (exec_result.error or "")
    assert import_result.success, import_result.error


async def test_import_kontext_resolves_injected_adapter(tmp_path: Path) -> None:
    """``import kontext`` must resolve to the injected adapter.

    The policy whitelists ``kontext`` and guided code uses ``kontext.*``, so
    agents write ``import kontext`` naturally. That import passed the confined
    whitelist and then failed with ``ModuleNotFoundError`` because the child
    has no such package; the kernel registers a module alias whose attributes
    forward to the adapter.
    """
    manager, runner = await _boot(tmp_path)
    try:
        result = await runner.run(
            session_id="s1",
            code=(
                "import kontext\n"
                "from kontext import load_data\n"
                "print(callable(kontext.load_data) and callable(load_data)"
                " and callable(kontext.list_data_sources)"
                " and callable(kontext.save_table))"
            ),
        )
    finally:
        await manager.shutdown()

    assert result.success, result.error
    assert "True" in _stdout(result)


async def test_kontext_alias_tracks_await_ready(tmp_path: Path) -> None:
    """The module alias must expose the *current* cell's adapter.

    Cells are injected per execution with an adapter whose ``await_ready``
    follows whether the cell is wrapped asynchronously; a once-frozen alias
    would keep the first cell's await semantics and break later
    ``await kontext.load_data(...)`` cells.
    """
    manager, runner = await _boot(tmp_path)
    try:
        sync_cell = await runner.run(
            session_id="s1",
            code=("import kontext\nmarker = callable(kontext.load_data)\nmarker"),
        )
        await_cell = await runner.run(
            session_id="s1",
            code="sources = await kontext.list_data_sources()\nsources",
        )
    finally:
        await manager.shutdown()

    assert sync_cell.success, sync_cell.error
    assert await_cell.success, await_cell.error
    assert await_cell.outputs, await_cell.error
    assert "[]" in str(await_cell.outputs[0].get("content", ""))


_KONTEXT_DELEGATION_PROBE = r'''
"""Probe for namespace-faithful delegation of the confined builtins.

Runs in a scratch interpreter: installing the confinement patches this
process's builtins, so the probe isolates the effect. The caller frames here
(module level, then a function) are *library-like* — neither runs in the
persistent user namespace — so the stubs must delegate while preserving the
caller's implicit namespaces.
"""

from kontext.kernel import harness

user_ns = {"__name__": "__main__"}
harness._install_confined_execution(user_ns)

# Module-level ``exec('del ' + name)`` with implicit namespaces — how
# ``scipy.stats._distn_infrastructure`` tears module names down. The del must
# resolve names in THIS module's dict, not in the stub's frame.
_doc_allmethods = object()
for _obj in ("_doc_allmethods",):
    exec("del " + _obj)
assert "_doc_allmethods" not in globals(), "module-level exec del failed"

# Function-frame ``eval`` with implicit locals — how ``numpy.f2py.auxfuncs``
# builds lambdas. The lambda's default ``f=f`` must resolve from the caller.
def l_not(f):
    return eval("lambda v,f=f:not f(v)")

assert l_not(lambda v: not v)(True) is True

# User-originated dynamic execution stays denied.
try:
    wrapper = compile("eval('1 + 1')", "<kontext-generated>", "exec")
    exec(wrapper, user_ns)
except harness._PolicyDenied:
    pass
else:
    raise AssertionError("user-frame eval was not denied")

print("PROBE-OK")
'''


def test_confined_stubs_delegate_implicit_namespaces(tmp_path: Path) -> None:
    """``exec``/``eval`` stubs keep caller-frame namespace semantics.

    Regression for the scipy.stats / sklearn-breakage found in a live session:
    delegation from the stub's own frame resolved implicit globals/locals
    against the harness module, breaking every whitelisted package whose
    internals use module-level ``exec``/``eval``.
    """
    script = tmp_path / "delegation_probe.py"
    script.write_text(_KONTEXT_DELEGATION_PROBE)
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"probe failed:\n{proc.stdout}\n{proc.stderr}"
    assert "PROBE-OK" in proc.stdout
