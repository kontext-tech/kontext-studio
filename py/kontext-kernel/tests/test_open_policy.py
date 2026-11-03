"""End-to-end tests for the kernel's policy-scoped file access.

The supervisor resolves the allowed open roots with the shared path policy and
passes them to the stdlib-only kernel child through the environment; the child
patches the real builtins dict, so ``open`` reached by name, via ``io.open``,
or dynamically (``vars(module)['builtins']['open']``) is confined alike.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kontext.kernel.session_runner import SessionRunner
from kontext.kernel.sessions import SessionKernelManager

pytestmark = pytest.mark.asyncio


def _policy_env(
    monkeypatch: pytest.MonkeyPatch,
    storage: Path,
    allowed_path: Path | None = None,
) -> None:
    """Roots are resolved by the *parent* into ``KONTEXT_OPEN_ROOTS``."""
    monkeypatch.setenv("FILE_STORAGE_PATH", str(storage))
    if allowed_path is None:
        monkeypatch.delenv("KONTEXT_ALLOWED_PATHS", raising=False)
    else:
        monkeypatch.setenv("KONTEXT_ALLOWED_PATHS", str(allowed_path))


async def _boot(
    tmp_path: Path,
    python_executable: str | None = None,
) -> tuple[SessionKernelManager, SessionRunner]:
    manager = SessionKernelManager(
        workspace_root=tmp_path / "workspaces",
        python_executable=python_executable,
    )
    await manager.start()
    return manager, SessionRunner(manager)


def _result_text(result) -> str | None:
    for output in result.outputs or []:
        if output.get("type") == "text":
            return str(output.get("content", ""))
    return None


def _managed_python() -> str:
    from kontext.runtime.python_environment import resolve_managed_python_executable

    return resolve_managed_python_executable()


def _managed_python_with(*modules: str) -> str:
    """Resolve the managed interpreter, skipping when it lacks ``modules``.

    Kernels run in the managed venv (numpy/pandas/matplotlib) once it has been
    prepared. When it has not -- e.g. in CI -- ``resolve_managed_python_executable``
    falls back to the current interpreter, which need not carry these optional
    libraries; the scenario then cannot be staged, so skip instead of failing.
    """
    executable = _managed_python()
    probe = subprocess.run(
        [executable, "-c", "import " + ", ".join(modules)],
        capture_output=True,
    )
    if probe.returncode != 0:
        pytest.skip(
            f"managed Python at {executable!r} cannot import {', '.join(modules)}; "
            "prepare the managed environment to run this test"
        )
    return executable


async def test_open_inside_storage_root_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    target = storage / "projects" / "p1" / "out.txt"
    _policy_env(monkeypatch, storage)
    target.parent.mkdir(parents=True)
    manager, runner = await _boot(tmp_path)
    try:
        result = await runner.run(
            session_id="s1",
            code=(
                f"path = {str(target)!r}\n"
                "with open(path, 'w') as handle:\n"
                "    handle.write('hello-from-kernel')\n"
                "open(path).read()"
            ),
        )
    finally:
        await manager.shutdown()

    assert result.success, result.error
    assert "hello-from-kernel" in (_result_text(result) or "")
    assert target.read_text() == "hello-from-kernel"


async def test_open_outside_roots_is_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    _policy_env(monkeypatch, storage)
    manager, runner = await _boot(tmp_path)
    try:
        result = await runner.run(session_id="s1", code="open('/etc/passwd', 'rb').read()[:4]")
    finally:
        await manager.shutdown()

    assert not result.success
    assert "outside the kernel's allowed open roots" in (result.error or "")


async def test_dynamic_paths_to_open_are_confined_alike(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """vars()/io.open routes to `open` must hit the same confined wrapper.

    This is the case a pre-flight AST policy cannot cover and the reason the
    confinement is installed on the builtins dict itself.
    """
    storage = tmp_path / "storage"
    storage.mkdir()
    _policy_env(monkeypatch, storage)
    manager, runner = await _boot(tmp_path)
    try:
        vars_result = await runner.run(
            session_id="s1",
            code=(
                "import json\n"
                "builtins_dict = vars(json).get('__builtins__')\n"
                "builtins_dict['open']('/etc/passwd','rb').read()[:4]"
            ),
        )
        io_result = await runner.run(
            session_id="s1",
            code=("import io\nio.open('/etc/passwd','rb').read()[:4]"),
        )
    finally:
        await manager.shutdown()

    for result in (vars_result, io_result):
        assert not result.success
        assert "outside the kernel's allowed open roots" in (result.error or "")


async def test_whitelisted_library_reads_its_own_package_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Libraries must be able to load bundled data (matplotlib style files).

    They read their package resources through Python ``open``; denying that
    would break whitelisted capabilities, so read-only access to the
    interpreter's own library roots is permitted.
    """
    storage = tmp_path / "storage"
    storage.mkdir()
    _policy_env(monkeypatch, storage)
    manager, runner = await _boot(tmp_path, python_executable=_managed_python_with("matplotlib"))
    try:
        result = await runner.run(
            session_id="s1",
            code=(
                "import matplotlib\n"
                "matplotlib.use('Agg')\n"
                "import matplotlib.pyplot as plt\n"
                "fig, ax = plt.subplots()\n"
                "ax.plot([1, 2], [1, 4])\n"
                "fig.savefig('chart.png')\n"
                "print('chart saved')"
            ),
        )
    finally:
        await manager.shutdown()

    assert result.success, result.error
    assert "chart saved" in (_result_text(result) or "")


async def test_library_reads_do_not_grant_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read-only library access must not become a write foothold."""
    storage = tmp_path / "storage"
    storage.mkdir()
    _policy_env(monkeypatch, storage)
    manager, runner = await _boot(tmp_path, python_executable=_managed_python_with("matplotlib"))
    try:
        # `inspect.getfile` avoids the dunder-attribute ban on `__file__`.
        # Target a *new* filename next to a library so a policy regression
        # cannot corrupt an installed package.
        seed = await runner.run(
            session_id="s1",
            code=(
                "import inspect\n"
                "import matplotlib\n"
                "lib_dir = inspect.getfile(matplotlib).rpartition('/')[0]\n"
                "probe_path = lib_dir + '/.kontext-write-probe'"
            ),
        )
        write_attempt = await runner.run(
            session_id="s1", code="open(probe_path, 'w').write('nope')"
        )
    finally:
        await manager.shutdown()

    assert seed.success, seed.error
    assert not write_attempt.success
    assert "outside the kernel's allowed open roots" in (write_attempt.error or "")


async def test_io_fileio_takes_the_same_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`io.FileIO` is a second construction path and must be confined alike."""
    storage = tmp_path / "storage"
    storage.mkdir()
    target = storage / "projects" / "p1" / "data.txt"
    target.parent.mkdir(parents=True)
    target.write_text("payload", encoding="utf-8")
    _policy_env(monkeypatch, storage)
    manager, runner = await _boot(tmp_path)
    try:
        inside = await runner.run(
            session_id="s1",
            code=f"import io\nio.FileIO({str(target)!r}, 'rb').read(7).decode()",
        )
        outside = await runner.run(
            session_id="s1",
            code="import io\nio.FileIO('/etc/passwd', 'rb').read(4)",
        )
        write_outside = await runner.run(
            session_id="s1",
            code=f"import io\nio.FileIO({str(target)!r}, 'w')",
        )
    finally:
        await manager.shutdown()

    assert inside.success, inside.error
    assert "payload" in (_result_text(inside) or "")
    assert not outside.success
    assert "outside the kernel's allowed open roots" in (outside.error or "")
    # A path inside the roots is writable, so the read case above is not a
    # blanket block; outside-root writes remain denied.
    assert write_outside.success, write_outside.error


async def test_escape_hatch_allows_extra_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    extra = tmp_path / "datasets"
    extra.mkdir()
    (extra / "note.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    _policy_env(monkeypatch, storage, allowed_path=extra)

    manager, runner = await _boot(tmp_path, python_executable=_managed_python_with("pandas"))
    try:
        read_result = await runner.run(
            session_id="s1",
            code=(
                "import pandas as pd\n"
                f"df = pd.read_csv({str(extra / 'note.csv')!r})\n"
                "int(df['a'].sum())"
            ),
        )
        # Outside both the storage root and the KONTEXT_ALLOWED_PATHS hatch.
        denied = await runner.run(session_id="s1", code="open('/etc/hosts','rb').read()[:4]")
    finally:
        await manager.shutdown()

    assert read_result.success, read_result.error
    assert (_result_text(read_result) or "").strip() == "4"
    assert not denied.success
    assert "outside the kernel's allowed open roots" in (denied.error or "")
