"""Tests for the managed Python bridge's save_table (kernel -> data table)."""

from __future__ import annotations

import base64
import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from kontext.execution.job_definitions.execute_python_script_job import (
    ExecutePythonScriptParams,
    _ManagedPythonBridge,
)
from kontext.schema import (
    ArtifactOrigin,
    TriggerActorModel,
    TriggerActorType,
)

_SESSION_ID = str(uuid4())


def _encoded_table() -> str:
    table = pa.table({"amount": [10.0, None, 30.0], "label": ["a", "b", "c"]})
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _bridge(
    *,
    file_service: Any = None,
    runtime_provider: Any = None,
    chat_session_id: str | None = None,
    triggered_by: TriggerActorModel | None = None,
) -> _ManagedPythonBridge:
    from unittest.mock import AsyncMock

    context = MagicMock()
    context.project_id = str(uuid4())
    context.job_run_id = str(uuid4())
    context.log_info = AsyncMock()
    context.log_warning = AsyncMock()
    context.get_file_service.return_value = file_service
    context.get_runtime_provider.return_value = runtime_provider
    return _ManagedPythonBridge(
        context=context,
        parameters=ExecutePythonScriptParams(
            code='saved = kontext.save_table(df, "t")',
            chat_session_id=chat_session_id,
            triggered_by=triggered_by,
        ),
    )


async def test_save_table_materializes_with_agent_provenance() -> None:
    durable_id = str(uuid4())
    file_service = MagicMock()
    file_service.materialize_parquet_inline_data = AsyncMock(return_value=durable_id)
    file_service.materialize_inline_data = AsyncMock()
    bridge = _bridge(
        file_service=file_service,
        chat_session_id=_SESSION_ID,
        triggered_by=TriggerActorModel(type=TriggerActorType.AGENT, id="python_tool"),
    )

    result = await bridge.save_table({"title": "ATM summary", "data": _encoded_table()})

    assert result["dataTableId"] == durable_id
    assert bridge.saved_tables == [
        {"dataTableId": durable_id, "rowCount": 3, "title": "ATM summary"}
    ]
    assert result["rowCount"] == 3
    assert result["title"] == "ATM summary"
    kwargs = file_service.materialize_parquet_inline_data.call_args.kwargs
    provenance = kwargs["provenance"]
    assert provenance.origin == ArtifactOrigin.AGENTPYTHON
    assert provenance.created_by.type == "Agent"
    assert provenance.execution_run_id == bridge._context.job_run_id
    assert provenance.identity_key is None

    # The original Parquet bytes are handed over untouched: the file service
    # builds the preview/row store, so the bridge never decodes rows.
    parquet_bytes = kwargs["parquet_bytes"]
    assert parquet_bytes[:4] == b"PAR1"
    table = pq.read_table(io.BytesIO(parquet_bytes))
    assert table.num_rows == 3
    assert table.schema.names == ["amount", "label"]
    file_service.materialize_inline_data.assert_not_called()


async def test_save_table_rejects_oversized_payloads() -> None:
    from kontext.execution.job_definitions.execute_python_script_job import (
        _SAVE_TABLE_MAX_ROWS,
    )

    table = pa.table({"a": list(range(_SAVE_TABLE_MAX_ROWS + 1))})
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    bridge = _bridge(file_service=MagicMock())
    with pytest.raises(ValueError, match="at most"):
        await bridge.save_table({"title": "big", "data": encoded})


async def test_save_table_links_artifact_to_chat_session() -> None:
    file_service = MagicMock()
    file_service.materialize_parquet_inline_data = AsyncMock(return_value=str(uuid4()))
    chat_session_service = MagicMock()
    chat_session_service.upsert_artifact = AsyncMock()
    runtime_provider = MagicMock()
    runtime_provider.get_chat_session_service.return_value = chat_session_service

    bridge = _bridge(
        file_service=file_service,
        runtime_provider=runtime_provider,
        chat_session_id=_SESSION_ID,
    )

    saved = await bridge.save_table({"title": "saved", "data": _encoded_table()})

    chat_session_service.upsert_artifact.assert_awaited_once()
    kwargs = chat_session_service.upsert_artifact.call_args.kwargs
    assert kwargs["session_id"] == _SESSION_ID
    assert kwargs["artifact_id"] == saved["dataTableId"]
    assert kwargs["meta"]["provenance"]["origin"] == "agent_python"
