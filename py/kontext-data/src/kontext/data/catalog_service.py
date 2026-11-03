"""Project catalog persistence service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select

from kontext.common.catalog.connector_specs import get_catalog_connector_spec
from kontext.common.catalog.revision import compute_catalog_revision
from kontext.common.utils.datetime_utils import normalize_datetime_utc, utc_now
from kontext.common.utils.enum_utils import enum_value
from kontext.common.utils.json_compat import model_validate_stored
from kontext.schema import (
    CatalogColumn,
    CatalogConnection,
    CatalogConnectionAuthType,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogConnectionRequest,
    CatalogConnectionValidationResult,
    CatalogEntityDetail,
    CatalogEntitySummary,
    CatalogEntityType,
    CatalogExecutionMode,
    CatalogNamespaceSummary,
    CatalogSourceCategory,
    CatalogSourceKind,
    CatalogSyncStatus,
)

from .base_service import ProjectDataService
from .models import (
    CatalogColumnRecord,
    CatalogEntity,
    CatalogNamespace,
    CatalogSourceLink,
    CatalogSyncState,
)
from .models import (
    CatalogConnection as CatalogConnectionRecord,
)


@dataclass
class CatalogEntitySnapshot:
    """Provider-normalized entity snapshot."""

    namespace_name: str
    entity_name: str
    entity_type: CatalogEntityType
    description: str | None = None
    row_count: int | None = None
    location: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    columns: list[CatalogColumn] = field(default_factory=list)
    source_type: str | None = None
    source_id: str | None = None


def _default_source_category(
    provider_kind: CatalogSourceKind,
) -> CatalogSourceCategory:
    try:
        return get_catalog_connector_spec(provider_kind).source_category
    except KeyError:
        if provider_kind == CatalogSourceKind.HTTPAPIEXTERNAL:
            return CatalogSourceCategory.API
        return CatalogSourceCategory.SQL


def _default_auth_type(provider_kind: CatalogSourceKind) -> CatalogConnectionAuthType:
    try:
        spec = get_catalog_connector_spec(provider_kind)
    except KeyError:
        if provider_kind in {
            CatalogSourceKind.ICEBERGINTERNAL,
            CatalogSourceKind.SQLITEEXTERNAL,
        }:
            return CatalogConnectionAuthType.NONE
        if provider_kind == CatalogSourceKind.BIGQUERYEXTERNAL:
            return CatalogConnectionAuthType.SERVICEACCOUNT
        if provider_kind == CatalogSourceKind.HTTPAPIEXTERNAL:
            return CatalogConnectionAuthType.APIKEY
        return CatalogConnectionAuthType.SECRETREF
    return spec.auth_types[0] if spec.auth_types else CatalogConnectionAuthType.NONE


def _default_execution_mode(
    provider_kind: CatalogSourceKind,
) -> CatalogExecutionMode:
    try:
        spec = get_catalog_connector_spec(provider_kind)
    except KeyError:
        if provider_kind in {
            CatalogSourceKind.ICEBERGINTERNAL,
            CatalogSourceKind.POSTGRESQLEXTERNAL,
            CatalogSourceKind.SQLITEEXTERNAL,
        }:
            return CatalogExecutionMode.DUCKDBFEDERATED
        if provider_kind == CatalogSourceKind.HTTPAPIEXTERNAL:
            return CatalogExecutionMode.MATERIALIZED
        return CatalogExecutionMode.NATIVEPUSHDOWN
    return spec.execution_modes[0] if spec.execution_modes else CatalogExecutionMode.DUCKDBFEDERATED


def _capabilities_from_row(
    raw: dict[str, Any] | None,
    provider_kind: CatalogSourceKind,
) -> CatalogConnectionCapabilities:
    """Rebuild capabilities from persisted JSON, tolerating legacy keys.

    Rows written by older versions may contain capability flags that no longer
    exist in the schema (e.g. a removed ``supportsRelationshipDiscovery``).
    The generated model forbids extras, so stored JSON is read through the
    tolerant helper rather than failing to load an otherwise-valid connection.
    """
    if not raw:
        return _default_capabilities(provider_kind)
    return model_validate_stored(CatalogConnectionCapabilities, raw)


def _default_capabilities(
    provider_kind: CatalogSourceKind,
) -> CatalogConnectionCapabilities:
    try:
        spec = get_catalog_connector_spec(provider_kind)
    except KeyError:
        return CatalogConnectionCapabilities(
            supports_sync=False,
            supports_search=False,
            supports_query=False,
            supports_query_pushdown=False,
            supports_duckdb_federation=False,
            supports_materialization=False,
            supports_write=False,
        )
    if provider_kind == CatalogSourceKind.ICEBERGINTERNAL:
        return CatalogConnectionCapabilities(
            supports_sync=True,
            supports_search=True,
            supports_query=True,
            supports_query_pushdown=False,
            supports_duckdb_federation=True,
            supports_materialization=True,
            supports_write=True,
        )
    return CatalogConnectionCapabilities(
        supports_sync=True,
        supports_search=True,
        supports_query=True,
        supports_query_pushdown=(CatalogExecutionMode.NATIVEPUSHDOWN in spec.execution_modes),
        supports_duckdb_federation=(CatalogExecutionMode.DUCKDBFEDERATED in spec.execution_modes),
        supports_materialization=False,
        supports_write=False,
    )


def _normalized_enabled_value(
    requested_enabled: bool | None,
    existing_enabled: bool,
) -> bool:
    if requested_enabled is None:
        return existing_enabled
    return requested_enabled


def _derive_query_readiness(
    *,
    connection_kind: CatalogConnectionKind,
    enabled: bool,
    last_sync_status: str | None,
) -> tuple[bool, str | None]:
    if not enabled:
        return False, "disabled"

    if connection_kind == CatalogConnectionKind.INTERNAL:
        return True, None

    normalized_status = (last_sync_status or "").lower()
    if normalized_status == "succeeded":
        return True, None
    if normalized_status in {"queued", "running"}:
        return False, normalized_status
    if normalized_status == "failed":
        return False, "failed"
    return False, "not_synced"


def _connection_from_row(row: CatalogConnectionRecord) -> CatalogConnection:
    provider_kind = CatalogSourceKind(row.provider_kind)
    connection_kind = CatalogConnectionKind(row.connection_kind)
    is_query_ready, readiness_reason = _derive_query_readiness(
        connection_kind=connection_kind,
        enabled=row.enabled,
        last_sync_status=row.last_sync_status,
    )
    return CatalogConnection(
        id=str(row.id),
        project_id=str(row.project_id),
        provider_kind=provider_kind,
        connection_kind=connection_kind,
        display_name=row.display_name,
        description=row.description,
        enabled=row.enabled,
        owner_id=str(row.owner_id) if row.owner_id else None,
        source_category=(
            CatalogSourceCategory(row.source_category)
            if row.source_category
            else _default_source_category(provider_kind)
        ),
        auth_type=(
            CatalogConnectionAuthType(row.auth_type)
            if row.auth_type
            else _default_auth_type(provider_kind)
        ),
        execution_mode=(
            CatalogExecutionMode(row.execution_mode)
            if row.execution_mode
            else _default_execution_mode(provider_kind)
        ),
        config=model_validate_stored(CatalogConnectionConfig, row.connection_config_json or {}),
        secret_ref=row.secret_ref,
        secret_configured=bool(row.secret_configured or row.secret_value or row.secret_ref),
        capabilities=_capabilities_from_row(row.capabilities_json, provider_kind),
        health_status=row.health_status,
        last_validated_at=normalize_datetime_utc(row.last_validated_at),
        validation_error=row.validation_error,
        sync_mode=row.sync_mode,
        sync_schedule=row.sync_schedule,
        last_synced_at=normalize_datetime_utc(row.last_synced_at),
        last_sync_status=row.last_sync_status,
        last_sync_error=row.last_sync_error,
        catalog_revision=row.catalog_revision,
        is_query_ready=is_query_ready,
        readiness_reason=readiness_reason,
    )


def _entity_summary(
    row: CatalogEntity,
    namespace_name: str,
    column_count: int = 0,
) -> CatalogEntitySummary:
    return CatalogEntitySummary(
        id=str(row.id),
        connection_id=str(row.connection_id),
        namespace_id=str(row.namespace_id) if row.namespace_id else None,
        namespace_name=namespace_name,
        entity_name=row.entity_name,
        display_name=row.display_name,
        entity_type=CatalogEntityType(row.entity_type),
        description=row.description,
        row_count=row.row_count,
        location=row.location,
        column_count=column_count,
        metadata=row.metadata_json or {},
    )


class CatalogDataService(ProjectDataService):
    """CRUD and sync persistence for generic catalog metadata."""

    async def list_connections_async(self) -> list[CatalogConnection]:
        return await asyncio.to_thread(self.list_connections)

    def list_connections(self) -> list[CatalogConnection]:
        with self._session_scope(commit=False) as session:
            rows = (
                session.execute(
                    select(CatalogConnectionRecord)
                    .where(
                        CatalogConnectionRecord.project_id == self.project_uuid,
                        CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                    )
                    .order_by(CatalogConnectionRecord.display_name)
                )
                .scalars()
                .all()
            )
            return [_connection_from_row(row) for row in rows]

    async def get_connection_async(self, connection_id: UUID | str) -> CatalogConnection | None:
        return await asyncio.to_thread(self.get_connection, connection_id)

    def get_connection(self, connection_id: UUID | str) -> CatalogConnection | None:
        with self._session_scope(commit=False) as session:
            row = session.execute(
                select(CatalogConnectionRecord).where(
                    CatalogConnectionRecord.id == UUID(str(connection_id)),
                    CatalogConnectionRecord.project_id == self.project_uuid,
                    CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                )
            ).scalar_one_or_none()
            return _connection_from_row(row) if row else None

    async def get_connection_secret_async(self, connection_id: UUID | str) -> str | None:
        return await asyncio.to_thread(self.get_connection_secret, connection_id)

    def get_connection_secret(self, connection_id: UUID | str) -> str | None:
        with self._session_scope(commit=False) as session:
            row = session.execute(
                select(CatalogConnectionRecord.secret_value).where(
                    CatalogConnectionRecord.id == UUID(str(connection_id)),
                    CatalogConnectionRecord.project_id == self.project_uuid,
                    CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                )
            ).scalar_one_or_none()
            return row

    async def upsert_connection_async(
        self,
        request: CatalogConnectionRequest,
        *,
        owner_id: str | None = None,
        connection_id: UUID | str | None = None,
    ) -> CatalogConnection:
        return await asyncio.to_thread(
            self.upsert_connection,
            request,
            owner_id=owner_id,
            connection_id=connection_id,
        )

    def upsert_connection(
        self,
        request: CatalogConnectionRequest,
        *,
        owner_id: str | None = None,
        connection_id: UUID | str | None = None,
    ) -> CatalogConnection:
        with self._session_scope() as session:
            provider_kind = (
                request.provider_kind
                if isinstance(request.provider_kind, CatalogSourceKind)
                else CatalogSourceKind(str(request.provider_kind))
            )
            connection_kind = (
                request.connection_kind
                if isinstance(request.connection_kind, CatalogConnectionKind)
                else CatalogConnectionKind(str(request.connection_kind))
            )
            row = None
            if connection_id:
                row = session.execute(
                    select(CatalogConnectionRecord).where(
                        CatalogConnectionRecord.id == UUID(str(connection_id)),
                        CatalogConnectionRecord.project_id == self.project_uuid,
                        CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                    )
                ).scalar_one_or_none()

            existing_enabled = bool(row.enabled) if row is not None else True

            if row is None:
                row = CatalogConnectionRecord(
                    id=UUID(str(connection_id)) if connection_id else uuid4(),
                    project_id=self.project_uuid,
                    provider_kind=provider_kind.value,
                    connection_kind=connection_kind.value,
                    owner_id=UUID(str(owner_id)) if owner_id else None,
                    created_at=utc_now(),
                )
                session.add(row)

            row.provider_kind = provider_kind.value
            row.connection_kind = connection_kind.value
            row.display_name = request.display_name
            row.description = request.description
            row.enabled = _normalized_enabled_value(
                request.enabled,
                existing_enabled=existing_enabled,
            )
            row.source_category = (
                enum_value(request.source_category)
                if request.source_category
                else _default_source_category(provider_kind).value
            )
            row.auth_type = (
                enum_value(request.auth_type)
                if request.auth_type
                else _default_auth_type(provider_kind).value
            )
            row.execution_mode = (
                enum_value(request.execution_mode)
                if request.execution_mode
                else _default_execution_mode(provider_kind).value
            )
            row.connection_config_json = request.config.model_dump(by_alias=True)
            row.secret_ref = request.secret_ref
            if request.secret_value is not None:
                row.secret_value = request.secret_value
                row.secret_configured = bool(request.secret_value)
            elif row.secret_value:
                row.secret_configured = True
            capabilities = request.capabilities or _default_capabilities(provider_kind)
            row.capabilities_json = capabilities.model_dump(by_alias=True)
            row.sync_mode = request.sync_mode
            row.sync_schedule = request.sync_schedule
            if connection_kind == CatalogConnectionKind.EXTERNAL:
                row.health_status = None
                row.last_validated_at = None
                row.validation_error = None
                row.last_synced_at = None
                row.last_sync_status = None
                row.last_sync_error = None
                row.catalog_revision = None
            row.updated_at = utc_now()
            session.flush()
            session.refresh(row)
            return _connection_from_row(row)

    async def delete_connection_async(self, connection_id: UUID | str) -> bool:
        return await asyncio.to_thread(self.delete_connection, connection_id)

    def delete_connection(self, connection_id: UUID | str) -> bool:
        with self._session_scope() as session:
            row = session.execute(
                select(CatalogConnectionRecord).where(
                    CatalogConnectionRecord.id == UUID(str(connection_id)),
                    CatalogConnectionRecord.project_id == self.project_uuid,
                    CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            row.is_deleted = True
            row.deleted_at = utc_now()
            row.updated_at = utc_now()
            return True

    async def replace_connection_snapshot_async(
        self,
        connection_id: UUID | str,
        entities: list[CatalogEntitySnapshot],
        *,
        status: str = "succeeded",
        error_message: str | None = None,
    ) -> CatalogSyncStatus:
        return await asyncio.to_thread(
            self.replace_connection_snapshot,
            connection_id,
            entities,
            status=status,
            error_message=error_message,
        )

    def replace_connection_snapshot(
        self,
        connection_id: UUID | str,
        entities: list[CatalogEntitySnapshot],
        *,
        status: str = "succeeded",
        error_message: str | None = None,
    ) -> CatalogSyncStatus:
        """Reconcile persisted catalog rows with a fresh provider snapshot.

        Rows are diffed by their stable identity — namespace name and
        ``(namespace, entity_name)`` — instead of being dropped and re-inserted,
        so entity/namespace IDs survive a sync. Only entities that disappeared
        are deleted and only changed/new ones are rewritten; an unchanged sync
        leaves identifiers (and therefore any client references) intact.
        """
        connection_uuid = UUID(str(connection_id))
        with self._session_scope() as session:
            connection = session.execute(
                select(CatalogConnectionRecord).where(
                    CatalogConnectionRecord.id == connection_uuid,
                    CatalogConnectionRecord.project_id == self.project_uuid,
                    CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                )
            ).scalar_one()

            now = utc_now()
            catalog_revision = compute_catalog_revision(entities)

            namespaces = {
                row.namespace_name: row
                for row in session.execute(
                    select(CatalogNamespace).where(
                        CatalogNamespace.connection_id == connection_uuid,
                        CatalogNamespace.project_id == self.project_uuid,
                    )
                )
                .scalars()
                .all()
            }

            existing_entities = (
                session.execute(
                    select(CatalogEntity).where(
                        CatalogEntity.connection_id == connection_uuid,
                        CatalogEntity.project_id == self.project_uuid,
                    )
                )
                .scalars()
                .all()
            )
            existing_entities_by_key = {
                (row.namespace_id, row.entity_name): row for row in existing_entities
            }
            existing_links = (
                session.execute(
                    select(CatalogSourceLink).where(
                        CatalogSourceLink.connection_id == connection_uuid,
                        CatalogSourceLink.project_id == self.project_uuid,
                    )
                )
                .scalars()
                .all()
            )
            existing_links_by_key = {
                (link.source_type, link.source_id, link.entity_id): link for link in existing_links
            }

            seen_namespace_ids: set[UUID] = set()
            seen_entity_ids: set[UUID] = set()
            seen_link_ids: set[UUID] = set()

            for snapshot in entities:
                namespace = namespaces.get(snapshot.namespace_name)
                if namespace is None:
                    namespace = CatalogNamespace(
                        id=uuid4(),
                        project_id=self.project_uuid,
                        connection_id=connection_uuid,
                        namespace_name=snapshot.namespace_name,
                        display_name=snapshot.namespace_name,
                    )
                    session.add(namespace)
                    session.flush()
                    namespaces[snapshot.namespace_name] = namespace
                seen_namespace_ids.add(namespace.id)

                entity_key = (namespace.id, snapshot.entity_name)
                entity_row = existing_entities_by_key.get(entity_key)
                if entity_row is None:
                    entity_row = CatalogEntity(
                        id=uuid4(),
                        project_id=self.project_uuid,
                        connection_id=connection_uuid,
                        namespace_id=namespace.id,
                        entity_name=snapshot.entity_name,
                        display_name=snapshot.entity_name,
                        entity_type=snapshot.entity_type.value,
                    )
                    session.add(entity_row)
                    session.flush()
                    existing_entities_by_key[entity_key] = entity_row
                entity_row.display_name = snapshot.entity_name
                entity_row.entity_type = snapshot.entity_type.value
                entity_row.description = snapshot.description
                entity_row.row_count = snapshot.row_count
                entity_row.location = snapshot.location
                entity_row.metadata_json = snapshot.metadata
                seen_entity_ids.add(entity_row.id)

                # Columns have no natural key beyond the entity, so replace them
                # wholesale only when the set changed.
                existing_columns = {
                    column.column_name: column
                    for column in session.execute(
                        select(CatalogColumnRecord).where(
                            CatalogColumnRecord.entity_id == entity_row.id
                        )
                    )
                    .scalars()
                    .all()
                }
                desired_columns = {column.name: column for column in snapshot.columns}
                for column_name, column_row in existing_columns.items():
                    if column_name not in desired_columns:
                        session.delete(column_row)
                for index, column in enumerate(snapshot.columns):
                    column_row = existing_columns.get(column.name)
                    if column_row is None:
                        column_row = CatalogColumnRecord(
                            id=uuid4(),
                            project_id=self.project_uuid,
                            entity_id=entity_row.id,
                            column_name=column.name,
                        )
                        session.add(column_row)
                    column_row.ordinal_position = (
                        column.ordinal_position if column.ordinal_position is not None else index
                    )
                    column_row.data_type = column.data_type
                    column_row.nullable = column.nullable
                    column_row.description = column.description
                    column_row.metadata_json = column.metadata

                if snapshot.source_type and snapshot.source_id:
                    source_id = UUID(str(snapshot.source_id))
                    link_key = (snapshot.source_type, source_id, entity_row.id)
                    link = existing_links_by_key.get(link_key)
                    if link is None:
                        link = CatalogSourceLink(
                            id=uuid4(),
                            project_id=self.project_uuid,
                            source_type=snapshot.source_type,
                            source_id=source_id,
                            connection_id=connection_uuid,
                            namespace_id=namespace.id,
                            entity_id=entity_row.id,
                        )
                        session.add(link)
                        existing_links_by_key[link_key] = link
                    link.namespace_id = namespace.id
                    seen_link_ids.add(link.id)

            # Delete entities/links/namespaces that vanished from the snapshot.
            for entity_row in existing_entities_by_key.values():
                if entity_row.id in seen_entity_ids:
                    continue
                for column_row in (
                    session.execute(
                        select(CatalogColumnRecord).where(
                            CatalogColumnRecord.entity_id == entity_row.id
                        )
                    )
                    .scalars()
                    .all()
                ):
                    session.delete(column_row)
                session.delete(entity_row)
            for link in existing_links:
                if link.id not in seen_link_ids:
                    session.delete(link)
            for namespace in namespaces.values():
                if namespace.id not in seen_namespace_ids:
                    session.delete(namespace)

            sync_state = session.execute(
                select(CatalogSyncState).where(
                    CatalogSyncState.connection_id == connection_uuid,
                    CatalogSyncState.project_id == self.project_uuid,
                )
            ).scalar_one_or_none()
            if sync_state is None:
                sync_state = CatalogSyncState(
                    id=uuid4(),
                    project_id=self.project_uuid,
                    connection_id=connection_uuid,
                )
                session.add(sync_state)

            sync_state.status = status
            sync_state.entity_count = len(entities)
            sync_state.last_synced_at = now
            sync_state.error_message = error_message
            connection.last_synced_at = now
            connection.last_sync_status = status
            connection.last_sync_error = error_message
            connection.catalog_revision = catalog_revision
            connection.updated_at = now

            session.flush()

            return CatalogSyncStatus(
                connection_id=str(connection_uuid),
                status=status,
                last_synced_at=now,
                entity_count=len(entities),
                error_message=error_message,
                catalog_revision=catalog_revision,
            )

    async def update_sync_status_async(
        self,
        connection_id: UUID | str,
        *,
        status: str,
        entity_count: int | None = None,
        error_message: str | None = None,
    ) -> CatalogSyncStatus:
        return await asyncio.to_thread(
            self.update_sync_status,
            connection_id,
            status=status,
            entity_count=entity_count,
            error_message=error_message,
        )

    def update_sync_status(
        self,
        connection_id: UUID | str,
        *,
        status: str,
        entity_count: int | None = None,
        error_message: str | None = None,
    ) -> CatalogSyncStatus:
        connection_uuid = UUID(str(connection_id))
        with self._session_scope() as session:
            connection = session.execute(
                select(CatalogConnectionRecord).where(
                    CatalogConnectionRecord.id == connection_uuid,
                    CatalogConnectionRecord.project_id == self.project_uuid,
                    CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                )
            ).scalar_one()
            sync_state = session.execute(
                select(CatalogSyncState).where(
                    CatalogSyncState.connection_id == connection_uuid,
                    CatalogSyncState.project_id == self.project_uuid,
                )
            ).scalar_one_or_none()
            if sync_state is None:
                sync_state = CatalogSyncState(
                    id=uuid4(),
                    project_id=self.project_uuid,
                    connection_id=connection_uuid,
                )
                session.add(sync_state)

            now = utc_now()
            if entity_count is None:
                entity_count = int(
                    session.execute(
                        select(func.count(CatalogEntity.id)).where(
                            CatalogEntity.connection_id == connection_uuid,
                            CatalogEntity.project_id == self.project_uuid,
                        )
                    ).scalar()
                    or 0
                )
            sync_state.status = status
            sync_state.entity_count = entity_count
            sync_state.error_message = error_message
            connection.last_sync_status = status
            connection.last_sync_error = error_message
            connection.updated_at = now

            if status == "succeeded":
                sync_state.last_synced_at = now
                connection.last_synced_at = now

            return CatalogSyncStatus(
                connection_id=str(connection_uuid),
                status=status,
                last_synced_at=(now if status == "succeeded" else connection.last_synced_at),
                entity_count=entity_count,
                error_message=error_message,
            )

    async def update_validation_status_async(
        self,
        connection_id: UUID | str,
        *,
        status: str,
        message: str | None = None,
        error_message: str | None = None,
    ) -> CatalogConnectionValidationResult:
        return await asyncio.to_thread(
            self.update_validation_status,
            connection_id,
            status=status,
            message=message,
            error_message=error_message,
        )

    def update_validation_status(
        self,
        connection_id: UUID | str,
        *,
        status: str,
        message: str | None = None,
        error_message: str | None = None,
    ) -> CatalogConnectionValidationResult:
        connection_uuid = UUID(str(connection_id))
        with self._session_scope() as session:
            connection = session.execute(
                select(CatalogConnectionRecord).where(
                    CatalogConnectionRecord.id == connection_uuid,
                    CatalogConnectionRecord.project_id == self.project_uuid,
                    CatalogConnectionRecord.is_deleted == False,  # noqa: E712
                )
            ).scalar_one()
            now = utc_now()
            connection.health_status = "healthy" if status == "succeeded" else "error"
            connection.last_validated_at = now
            connection.validation_error = error_message
            connection.updated_at = now
            return CatalogConnectionValidationResult(
                connection_id=str(connection_uuid),
                status=status,
                validated_at=now,
                message=message,
                error_message=error_message,
            )

    async def list_namespaces_async(
        self, connection_id: UUID | str
    ) -> list[CatalogNamespaceSummary]:
        return await asyncio.to_thread(self.list_namespaces, connection_id)

    def list_namespaces(self, connection_id: UUID | str) -> list[CatalogNamespaceSummary]:
        connection_uuid = UUID(str(connection_id))
        with self._session_scope(commit=False) as session:
            rows = session.execute(
                select(
                    CatalogNamespace,
                    func.count(CatalogEntity.id),
                )
                .outerjoin(CatalogEntity, CatalogEntity.namespace_id == CatalogNamespace.id)
                .where(
                    CatalogNamespace.connection_id == connection_uuid,
                    CatalogNamespace.project_id == self.project_uuid,
                )
                .group_by(CatalogNamespace.id)
                .order_by(CatalogNamespace.namespace_name)
            ).all()
            return [
                CatalogNamespaceSummary(
                    id=str(namespace.id),
                    connection_id=str(namespace.connection_id),
                    name=namespace.namespace_name,
                    display_name=namespace.display_name,
                    entity_count=int(entity_count or 0),
                )
                for namespace, entity_count in rows
            ]

    async def list_entities_async(
        self,
        *,
        connection_id: UUID | str | None = None,
        namespace_name: str | None = None,
    ) -> list[CatalogEntitySummary]:
        return await asyncio.to_thread(
            self.list_entities,
            connection_id=connection_id,
            namespace_name=namespace_name,
        )

    def list_entities(
        self,
        *,
        connection_id: UUID | str | None = None,
        namespace_name: str | None = None,
    ) -> list[CatalogEntitySummary]:
        with self._session_scope(commit=False) as session:
            stmt = (
                select(
                    CatalogEntity,
                    CatalogNamespace.namespace_name,
                    func.count(CatalogColumnRecord.id),
                )
                .join(
                    CatalogNamespace,
                    CatalogNamespace.id == CatalogEntity.namespace_id,
                    isouter=True,
                )
                .outerjoin(
                    CatalogColumnRecord,
                    CatalogColumnRecord.entity_id == CatalogEntity.id,
                )
                .where(CatalogEntity.project_id == self.project_uuid)
                .group_by(CatalogEntity.id, CatalogNamespace.namespace_name)
                .order_by(CatalogNamespace.namespace_name, CatalogEntity.entity_name)
            )
            if connection_id:
                stmt = stmt.where(CatalogEntity.connection_id == UUID(str(connection_id)))
            if namespace_name:
                stmt = stmt.where(CatalogNamespace.namespace_name == namespace_name)

            return [
                _entity_summary(row, namespace_name_value or "default", int(column_count or 0))
                for row, namespace_name_value, column_count in session.execute(stmt).all()
            ]

    async def get_entity_detail_async(self, entity_id: UUID | str) -> CatalogEntityDetail | None:
        return await asyncio.to_thread(self.get_entity_detail, entity_id)

    def get_entity_detail(self, entity_id: UUID | str) -> CatalogEntityDetail | None:
        with self._session_scope(commit=False) as session:
            entity_row = session.execute(
                select(CatalogEntity, CatalogNamespace.namespace_name)
                .join(
                    CatalogNamespace,
                    CatalogNamespace.id == CatalogEntity.namespace_id,
                    isouter=True,
                )
                .where(
                    CatalogEntity.id == UUID(str(entity_id)),
                    CatalogEntity.project_id == self.project_uuid,
                )
            ).first()
            if entity_row is None:
                return None
            entity, namespace_name = entity_row
            columns = (
                session.execute(
                    select(CatalogColumnRecord)
                    .where(CatalogColumnRecord.entity_id == entity.id)
                    .order_by(CatalogColumnRecord.ordinal_position)
                )
                .scalars()
                .all()
            )
            return CatalogEntityDetail(
                entity=_entity_summary(
                    entity,
                    namespace_name or "default",
                    column_count=len(columns),
                ),
                columns=[
                    CatalogColumn(
                        id=str(column.id),
                        entity_id=str(column.entity_id),
                        name=column.column_name,
                        ordinal_position=column.ordinal_position,
                        data_type=column.data_type,
                        nullable=column.nullable,
                        description=column.description,
                        metadata=column.metadata_json or {},
                    )
                    for column in columns
                ],
            )

    async def list_entity_details_for_connection_async(
        self, connection_id: UUID | str
    ) -> list[CatalogEntityDetail]:
        return await asyncio.to_thread(self.list_entity_details_for_connection, connection_id)

    def list_entity_details_for_connection(
        self, connection_id: UUID | str
    ) -> list[CatalogEntityDetail]:
        summaries = self.list_entities(connection_id=connection_id)
        details: list[CatalogEntityDetail] = []
        for summary in summaries:
            detail = self.get_entity_detail(summary.id)
            if detail is not None:
                details.append(detail)
        return details

    async def list_source_links_async(
        self, *, source_type: str, source_id: UUID | str
    ) -> list[CatalogSourceLink]:
        return await asyncio.to_thread(
            self.list_source_links,
            source_type=source_type,
            source_id=source_id,
        )

    def list_source_links(
        self, *, source_type: str, source_id: UUID | str
    ) -> list[CatalogSourceLink]:
        with self._session_scope(commit=False) as session:
            return list(
                session.execute(
                    select(CatalogSourceLink).where(
                        CatalogSourceLink.project_id == self.project_uuid,
                        CatalogSourceLink.source_type == source_type,
                        CatalogSourceLink.source_id == UUID(str(source_id)),
                    )
                )
                .scalars()
                .all()
            )

    async def list_source_links_for_connection_async(
        self, connection_id: UUID | str
    ) -> list[CatalogSourceLink]:
        return await asyncio.to_thread(self.list_source_links_for_connection, connection_id)

    def list_source_links_for_connection(
        self, connection_id: UUID | str
    ) -> list[CatalogSourceLink]:
        connection_uuid = UUID(str(connection_id))
        with self._session_scope(commit=False) as session:
            return list(
                session.execute(
                    select(CatalogSourceLink).where(
                        CatalogSourceLink.project_id == self.project_uuid,
                        CatalogSourceLink.connection_id == connection_uuid,
                    )
                )
                .scalars()
                .all()
            )
