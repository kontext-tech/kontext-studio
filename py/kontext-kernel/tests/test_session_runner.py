"""End-to-end tests for SessionRunner (session kernel + host bridge)."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest

from kontext.kernel.session_runner import SessionRunner
from kontext.kernel.sessions import SessionKernelManager

pytestmark = pytest.mark.asyncio


async def test_session_runner_reuses_namespace_across_runs(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        first = await runner.run(session_id="s1", code="counter = 41")
        assert first.success

        second = await runner.run(session_id="s1", code="counter + 1")
        assert second.success
        assert second.outputs[0]["content"] == "42"
    finally:
        await manager.shutdown()


async def test_session_runner_serves_load_data_from_payloads(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        guid = "22222222-3333-4444-5555-666666666666"
        table = '{"table": {"columns": [{"name": "amount"}], "rows": [[10], [20]]}}'
        payloads = {"sales": table, guid: table}
        # Whether pandas is installed (DataFrame) or not (records), the data is
        # reachable through the adapter and the loadable names are advertised,
        # split by flavor: slug-shaped names are aliases, GUIDs are durable ids.
        result = await runner.run(
            session_id="s1",
            code=(
                "sources = kontext.list_data_sources()\n"
                "data = kontext.load_data('sales')\n"
                f"sources['aliases'] == ['sales'] and sources['data_ids'] == ['{guid}']"
            ),
            data_payloads=payloads,
        )
        assert result.success, result.error
        assert result.outputs[-1]["content"] == "True"
    finally:
        await manager.shutdown()


async def test_session_runner_supports_await_style_load_data(tmp_path: Path) -> None:
    """Agent code is guided towards ``await kontext.load_data(...)``.

    The generated async wrapper used to glue ``return (...)`` onto the last
    body line (``ast.unparse`` emits no trailing newline), making every async
    script a SyntaxError. The wrapper must compile, and awaiting an adapter
    result must yield the loaded data.
    """
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        payloads = {"sales": ('{"table": {"columns": [{"name": "amount"}], "rows": [[10], [20]]}}')}
        code = (
            "rows = await kontext.load_data('sales')\nprint('loaded rows:', len(rows))\nlen(rows)"
        )
        result = await runner.run(session_id="s1", code=code, data_payloads=payloads)
        assert result.success, result.error
        assert any("loaded rows: 2" in output.get("content", "") for output in result.outputs)
        assert any(output.get("content") == "2" for output in result.outputs)
    finally:
        await manager.shutdown()


async def test_session_runner_allows_sync_adapter_calls_inside_async_scripts(
    tmp_path: Path,
) -> None:
    """A sync-style call in an async script must still see the loaded data."""
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        payloads = {"sales": ('{"table": {"columns": [{"name": "amount"}], "rows": [[10], [20]]}}')}
        code = "sources = await kontext.list_data_sources()\nlen(kontext.load_data('sales'))"
        result = await runner.run(session_id="s1", code=code, data_payloads=payloads)
        assert result.success, result.error
        assert result.outputs[0]["content"] == "2"
    finally:
        await manager.shutdown()


async def test_session_runner_reports_missing_data(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        result = await runner.run(
            session_id="s1",
            code="kontext.load_data('missing')",
            data_payloads={},
        )
        assert not result.success
        assert "missing" in (result.error or "")
    finally:
        await manager.shutdown()


async def test_session_runner_rejects_forbidden_code(tmp_path: Path) -> None:
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        result = await runner.run(session_id="s1", code="import subprocess")
        assert not result.success
        assert "Forbidden import" in (result.error or "")
    finally:
        await manager.shutdown()


class _SaveTableBridge:
    """Minimal host-bridge stub capturing the kernel's save_table call."""

    def __init__(self) -> None:
        self.content: dict | None = None

    async def save_table(self, content: dict) -> dict:
        self.content = content
        return {"dataTableId": "11111111-2222-3333-4444-555555555555", "rowCount": 2}

    async def execute_sql(self, sql: str, title: str | None = None) -> object:
        raise NotImplementedError("execute_sql is not part of this test bridge")


async def test_session_runner_save_table_roundtrip(tmp_path: Path) -> None:
    """``kontext.save_table`` encodes the frame as Parquet and returns the summary.

    The kernel adapter serializes an Arrow table to base64 Parquet bytes, the
    host serves the op through the bridge, and the summary dict is returned to
    the cell so the code can continue with the durable id.
    """
    bridge = _SaveTableBridge()
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        code = (
            "import pyarrow as pa\n"
            "table = pa.table({'amount': [10.0, None], 'label': ['a', 'b']})\n"
            "saved = kontext.save_table(table, 'ATM summary')\n"
            "saved['dataTableId']\n"
        )
        result = await runner.run(session_id="chat:test", code=code, host_bridge=bridge)
    finally:
        await manager.shutdown()

    assert result.success, result.error
    assert result.outputs[0]["content"] == "11111111-2222-3333-4444-555555555555"
    assert bridge.content is not None
    assert bridge.content["title"] == "ATM summary"
    decoded = base64.b64decode(bridge.content["data"])
    assert decoded[:4] == b"PAR1", "adapter payload is not Parquet"


async def test_session_runner_save_table_reports_type_errors(tmp_path: Path) -> None:
    """Non-table objects fail the host call with a clear message."""
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        result = await runner.run(
            session_id="chat:test",
            code="kontext.save_table({'not': 'a table'}, 't')",
            host_bridge=_SaveTableBridge(),
        )
    finally:
        await manager.shutdown()

    assert not result.success
    assert "expects a pandas DataFrame" in (result.error or "")


async def test_session_runner_save_table_via_imported_kontext(tmp_path: Path) -> None:
    """The ``import kontext`` alias must expose ``save_table`` too.

    Guided code writes ``import kontext`` and then uses both spellings
    interchangeably; the alias forwards to the same adapter, so the imported
    module surface must cover every host-call method.
    """
    bridge = _SaveTableBridge()
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        result = await runner.run(
            session_id="chat:test",
            code=(
                "import pyarrow as pa\n"
                "import kontext\n"
                "table = pa.table({'amount': [10.0]})\n"
                "saved = kontext.save_table(table, 'Imported call')\n"
                "saved['dataTableId']\n"
            ),
            host_bridge=bridge,
        )
    finally:
        await manager.shutdown()

    assert result.success, result.error
    assert result.outputs[0]["content"] == "11111111-2222-3333-4444-555555555555"
    assert bridge.content is not None
    assert bridge.content["title"] == "Imported call"


async def test_session_runner_interrupts_kernel_on_cancellation(tmp_path: Path) -> None:
    """Cancelling a running session run interrupts the kernel and re-raises."""
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        # A long pure-Python loop is interruptible by the kernel's SIGINT.
        code = "print('ready', flush=True)\nwhile True:\n    pass"
        task = asyncio.ensure_future(runner.run(session_id="s1", code=code))
        await asyncio.sleep(1.5)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # The kernel must survive (interrupted, not killed) and be usable.
        assert manager.active_session_ids() == ["s1"]
        follow_up = await runner.run(session_id="s1", code="1 + 1")
        assert follow_up.success
        assert follow_up.outputs[0]["content"] == "2"
    finally:
        await manager.shutdown()


async def test_session_runner_persists_variables_bound_in_await_cells(tmp_path: Path) -> None:
    """Variables assigned in an ``await``-using cell must persist to later cells.

    ``await``-using scripts are compiled inside an async wrapper, so without
    ``global`` declarations their assignments stay function locals and vanish,
    breaking session-wide variable sharing.
    """
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        payloads = {"sales": ('{"table": {"columns": [{"name": "amount"}], "rows": [[10], [20]]}}')}
        first = await runner.run(
            session_id="s1",
            code="rows = await kontext.load_data('sales')\nlen(rows)",
            data_payloads=payloads,
        )
        assert first.success, first.error

        # The binding from the previous async cell is visible in a later cell.
        second = await runner.run(session_id="s1", code="len(rows)")
        assert second.success, second.error
        assert second.outputs[0]["content"] == "2"

        # Imports inside an async cell also persist (a plain `import` is not
        # subject to the per-cell alias-isolation check).
        third = await runner.run(
            session_id="s1",
            code="import numpy\nprobe = await kontext.list_data_sources()\nnumpy.abs(-3)",
        )
        assert third.success, third.error
        fourth = await runner.run(session_id="s1", code="numpy.zeros(1).shape[0]")
        assert fourth.success, fourth.error
        assert fourth.outputs[0]["content"] == "1"
    finally:
        await manager.shutdown()


async def test_session_runner_allows_persisted_aliases_across_cells(tmp_path: Path) -> None:
    """Aliases imported in an earlier cell must be usable in later cells.

    The alias-isolation guidance exists for one-shot runs; inside a persistent
    session kernel it would falsely reject a follow-up cell that uses ``np``
    after ``import numpy as np`` in an earlier cell.
    """
    manager = SessionKernelManager(workspace_root=tmp_path)
    await manager.start()
    runner = SessionRunner(manager)
    try:
        first = await runner.run(session_id="s1", code="import numpy as np\ndim = 2\ndim")
        assert first.success, first.error

        second = await runner.run(session_id="s1", code="np.ones(dim).size")
        assert second.success, second.error
        assert second.outputs[0]["content"] == "2"
    finally:
        await manager.shutdown()
