"""API adapters for query-execution application services."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from kontext.file.factories import create_file_service
from kontext.query import (
    QueryServiceError,
    execute_query_async,
    execute_query_sync,
    get_session_query_history,
)
from kontext.schema import (
    DataRef,
    ExecutionRunModel,
    NotebookDocument,
    QueryExecRequest,
    QueryResponse,
    SqlBlock,
)

from ..dependencies import AuthContext
from ..transport_adapters import (
    build_query_access_context,
    domain_error_to_http,
)

logger = logging.getLogger(__name__)


def _find_sql_stamp_target(
    notebook: NotebookDocument, block_id: str, notebook_id: str
) -> SqlBlock | None:
    """The SQL block to stamp, or ``None`` after warning when absent/wrong-type."""
    for block in notebook.blocks:
        root = block.root
        if root is None or str(root.id) != block_id:
            continue
        if not isinstance(root, SqlBlock):
            logger.warning(
                "Notebook alias binding skipped: block %s in %s is not a SQL block",
                block_id,
                notebook_id,
            )
            return None
        return root
    logger.warning(
        "Notebook alias binding skipped: block %s not found in notebook %s",
        block_id,
        notebook_id,
    )
    return None


async def bind_notebook_sql_block_alias(
    project_id: str,
    notebook_id: str,
    block_id: str,
    data_id: str,
) -> str | None:
    """Bind the executing SQL block's notebook-scoped alias server-side.

    Manual UI runs persist their result through the query pipeline, which
    carries no notebook state of its own — the client stamps ``dataRef`` into
    its local document only after this response. Binding here keeps the
    ``df_N`` numbering a server-side authority: the data ref and alias land on
    the block in the persisted document, travel back on the response so the UI
    shows the chip immediately, and converge when the client saves the edited
    document (which carries the same values).

    Never fails the query: binding is additive, so any storage or validation
    error logs a warning and returns ``None`` (the alias simply binds later,
    e.g. at the next python-block execution).
    """
    try:
        service = create_file_service(UUID(project_id))
        content = await service.get_file_content(project_id, notebook_id)
        notebook = NotebookDocument.model_validate_json(content)
        stamp_target = _find_sql_stamp_target(notebook, block_id, notebook_id)
        if stamp_target is None:
            return None

        stamp_target.data.data_ref = DataRef(data_id=data_id)
        await service.update_notebook(
            project_id=project_id,
            file_id=notebook_id,
            notebook=notebook,
        )
        alias = stamp_target.data.alias
        if alias:
            logger.info(
                "Bound SQL block %s in notebook %s to alias %s (table %s)",
                block_id,
                notebook_id,
                alias,
                data_id,
            )
        return alias
    except Exception:
        logger.warning(
            "Notebook alias binding failed for notebook %s block %s (non-fatal)",
            notebook_id,
            block_id,
            exc_info=True,
        )
        return None


async def execute_query_service(
    *,
    request: QueryExecRequest,
    auth_context: AuthContext[Any],
    queue_client,
) -> QueryResponse:
    try:
        query_response = await execute_query_sync(
            request=request,
            access_context=build_query_access_context(auth_context),
            queue_client=queue_client,
        )
        if (
            query_response.success
            and request.notebook_id
            and request.block_id
            and query_response.data_id
        ):
            query_response.alias = await bind_notebook_sql_block_alias(
                project_id=str(auth_context.project_id),
                notebook_id=request.notebook_id,
                block_id=request.block_id,
                data_id=query_response.data_id,
            )
        return query_response
    except QueryServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def execute_query_async_service(
    *,
    request: QueryExecRequest,
    auth_context: AuthContext[Any],
    queue_client,
) -> ExecutionRunModel:
    try:
        return await execute_query_async(
            request=request,
            access_context=build_query_access_context(auth_context),
            queue_client=queue_client,
        )
    except QueryServiceError as exc:
        raise domain_error_to_http(exc) from exc


def get_session_query_history_service(
    *,
    project_id: str,
    session_id: str,
    page_index: int,
    page_size: int,
) -> dict[str, object]:
    return get_session_query_history(
        project_id=project_id,
        session_id=session_id,
        page_index=page_index,
        page_size=page_size,
    )
