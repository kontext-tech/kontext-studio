"""
Standardized contracts for multi-engine query execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from kontext.schema import (
    DataTable,
    QueryEngineType,
    SchemaInfo,
    TableDiscoveryModel,
)

__all__ = ["QueryEngineRequest", "QueryEngineType", "QueryExecutionEngine"]


@dataclass(frozen=True)
class QueryEngineRequest:
    """Canonical, type-safe session request handed to engine resolution.

    This replaces the previous untyped ``**kwargs`` seam between orchestration
    and engine providers: the fields map one-to-one onto the session config
    models the concrete engines maintain (DuckDB sessions, live-SQL pushdown).
    ``project_id`` is mandatory. Implementations of
    :meth:`QueryEngineResolverProtocol.get_query_execution_engine` decide which
    fields their engine supports (for example, live-SQL pushdown requires
    ``catalog_connection_id`` and must reject the request without one).
    """

    project_id: str
    session_id: str | None = None
    catalog_connection_id: str | None = None
    default_namespace: str | None = None
    default_entity_id: str | None = None
    user_id: str | None = None
    session_name: str | None = None
    persistent: bool = True
    shadow: bool = False


class QueryExecutionEngine(Protocol):
    """
    Protocol defining the interface for all query execution engines.
    """

    async def connect(self) -> None: ...

    async def execute_query(self, sql: str, params: dict[str, Any] | None = None) -> Any: ...

    async def fetch_data_table(
        self, sql: str, params: dict[str, Any] | None = None, max_rows: int = 1000
    ) -> DataTable: ...

    async def validate_sql(self, sql: str) -> tuple[bool, str | None]: ...

    async def get_schema(self, schema_name: str | None = None) -> SchemaInfo | None: ...

    async def discover_table(
        self, schema_name: str, table_name: str
    ) -> TableDiscoveryModel | None: ...

    async def dispose(self) -> None: ...
