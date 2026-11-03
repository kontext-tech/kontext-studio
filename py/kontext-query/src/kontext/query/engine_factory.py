"""Query-engine resolution.

The single engine-resolution seam of ``kontext-query``. Engines are created
only through the caller's ``QueryRuntimeProviderProtocol`` — a concrete engine
package is never imported here, so engine swaps stay composition changes.

The session shape travels as a typed :class:`QueryEngineRequest`; no loose
kwargs cross the port.
"""

from __future__ import annotations

from kontext.common.protocols import (
    IQuerySessionServiceProtocol,
    QueryRuntimeProviderProtocol,
)
from kontext.common.query.engine import (
    QueryEngineRequest,
    QueryEngineType,
    QueryExecutionEngine,
)


async def resolve_engine_for_session(
    *,
    engine_type: QueryEngineType = QueryEngineType.DUCKDB,
    runtime_provider: QueryRuntimeProviderProtocol | None = None,
    request: QueryEngineRequest,
    query_session_service: IQuerySessionServiceProtocol | None = None,
) -> QueryExecutionEngine:
    """Resolve an execution engine for *engine_type*, defaulting to DuckDB.

    Args:
        engine_type: Engine to resolve. Planned-but-absent backends raise
            ``NotImplementedError``.
        runtime_provider: Composition root owning engine creation.
        request: Typed session request (project, session id, catalog
            connection, namespace/entity defaults, owner, shadow mode).
        query_session_service: Optional session service handed to the engine.

    Raises:
        RuntimeError: When no runtime provider is given, or it cannot resolve
            an engine for *engine_type* (unsupported engine types land here
            too).
        ValueError: When the request violates the resolved engine's
            requirements (e.g. missing ``catalog_connection_id`` for live
            pushdown engines).
    """
    if engine_type == QueryEngineType.SNOWFLAKE:
        # Phase 3
        raise NotImplementedError("Snowflake engine is not implemented yet.")

    if engine_type == QueryEngineType.POSTGRESQL:
        # Phase 4
        raise NotImplementedError("PostgreSQL engine is not implemented yet.")

    if runtime_provider is None:
        raise RuntimeError("Query engine resolution requires a runtime_provider.")

    engine = runtime_provider.get_query_execution_engine(
        engine_type=engine_type,
        request=request,
        query_session_service=query_session_service,
    )
    if engine is None:
        raise RuntimeError(f"No query execution engine available for {engine_type}.")
    return engine
