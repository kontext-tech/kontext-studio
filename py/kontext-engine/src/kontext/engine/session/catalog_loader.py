"""Catalog loading utilities for DuckDB session bootstrap."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from kontext.data import CatalogDataService
from kontext.schema import CatalogConnection, CatalogEntityDetail


@dataclass
class ProjectCatalogLoadResult:
    """Loaded catalog metadata scoped for a query session."""

    connection: CatalogConnection
    entities_by_namespace: dict[str, list[CatalogEntityDetail]]
    total_entities: int


class CatalogLoader:
    """Loads normalized catalog entities for DuckDB session bootstrap."""

    def __init__(self, project_id: str, logger: logging.Logger | None = None) -> None:
        self.project_id = str(project_id)
        self.logger = logger or logging.getLogger(__name__)
        self._catalog_data_service = CatalogDataService(self.project_id)

    async def load_project_catalog(
        self,
        *,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
    ) -> ProjectCatalogLoadResult:
        connections = await self._catalog_data_service.list_connections_async()
        enabled_connections = [connection for connection in connections if connection.enabled]
        if not enabled_connections:
            raise RuntimeError("No enabled catalog connections found for project")

        if catalog_connection_id:
            connection = next(
                (
                    item
                    for item in enabled_connections
                    if str(item.id) == str(catalog_connection_id)
                ),
                None,
            )
            if connection is None:
                raise RuntimeError(f"Catalog connection {catalog_connection_id} not found")
        else:
            connection = enabled_connections[0]

        entities = await self._catalog_data_service.list_entity_details_for_connection_async(
            connection.id or ""
        )
        entities_by_namespace: dict[str, list[CatalogEntityDetail]] = {}
        for entity in entities:
            namespace_name = entity.entity.namespace_name or "default"
            if default_namespace and namespace_name != default_namespace:
                continue
            entities_by_namespace.setdefault(namespace_name, []).append(entity)

        total_entities = sum(len(items) for items in entities_by_namespace.values())
        self.logger.info(
            "Loaded %d catalog entities across %d namespaces for connection %s",
            total_entities,
            len(entities_by_namespace),
            connection.id,
        )
        return ProjectCatalogLoadResult(
            connection=connection,
            entities_by_namespace=entities_by_namespace,
            total_entities=total_entities,
        )
