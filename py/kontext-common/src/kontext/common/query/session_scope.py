"""Shared helpers for resolving effective query-session scope.

Lives in ``kontext-common`` because it is used by job execution (which receives
a provider protocol rather than the concrete query service) and depends only on
the provider protocol plus the schema contract.
"""

from __future__ import annotations

from uuid import UUID

from kontext.common.protocols import IQuerySessionServiceProtocol
from kontext.schema import QueryEngineType


async def hydrate_session_scope(
    *,
    query_session_service: IQuerySessionServiceProtocol | None,
    project_id: UUID | str,
    session_id: UUID | str | None,
    catalog_connection_id: UUID | str | None,
    default_namespace: str | None,
    default_entity_id: UUID | str | None,
    engine_type: QueryEngineType,
) -> tuple[str | None, str | None, str | None, QueryEngineType]:
    """Backfill missing scope fields from the stored query session."""
    if query_session_service is None or not session_id:
        return (
            str(catalog_connection_id) if catalog_connection_id else None,
            default_namespace,
            str(default_entity_id) if default_entity_id else None,
            engine_type,
        )

    session_vm = await query_session_service.get_query_session(
        session_id=session_id,
        project_id=project_id,
    )
    if session_vm is None:
        return (
            str(catalog_connection_id) if catalog_connection_id else None,
            default_namespace,
            str(default_entity_id) if default_entity_id else None,
            engine_type,
        )

    return (
        str(catalog_connection_id or session_vm.catalog_connection_id)
        if (catalog_connection_id or session_vm.catalog_connection_id)
        else None,
        default_namespace or session_vm.default_namespace,
        str(default_entity_id or session_vm.default_entity_id)
        if (default_entity_id or session_vm.default_entity_id)
        else None,
        session_vm.engine_type or engine_type,
    )
