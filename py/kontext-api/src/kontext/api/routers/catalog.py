"""Catalog connection and search endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from kontext.auth import ProjectPermissions
from kontext.catalog import CatalogSyncDispatchService
from kontext.common.messaging import IQueueClient
from kontext.common.protocols import ICatalogManagementServiceProtocol
from kontext.schema import (
    CatalogConnection,
    CatalogConnectionKind,
    CatalogConnectionRequest,
    CatalogConnectionValidationResult,
    CatalogEntityDetail,
    CatalogEntitySummary,
    CatalogNamespaceSummary,
    CatalogProviderDefinition,
    CatalogSearchItem,
    CatalogSyncStatus,
)

from ..dependencies import (
    CONNECTION_ID_PATH,
    ENTITY_ID_PATH,
    PROJECT_ID_QUERY,
    QUEUE_CLIENT_DEP,
    AuthContext,
    create_auth_dependency,
)
from ..services.runtime import LOCAL_HEADERS_RUNTIME_FACTORY

router = APIRouter()

CONNECTION_ID_QUERY = Query(default=None, alias="connectionId")
NAMESPACE_NAME_QUERY = Query(default=None, alias="namespaceName")
SEARCH_QUERY = Query(...)
LIMIT_QUERY = Query(default=5, ge=1, le=50)

CATALOG_READ_AUTH = create_auth_dependency(required_permissions=[ProjectPermissions.READ])
CATALOG_WRITE_AUTH = create_auth_dependency(required_permissions=[ProjectPermissions.UPDATE])


async def _service(
    project_id: UUID,
    request: Request,
) -> ICatalogManagementServiceProtocol:
    runtime_provider = await LOCAL_HEADERS_RUNTIME_FACTORY.create_runtime_provider(
        project_id=str(project_id),
        headers=dict(request.headers),
    )
    service = runtime_provider.get_catalog_service()
    if service is None:
        raise RuntimeError("Catalog management is unavailable in this runtime.")
    return service


@router.get("/providers", response_model=list[CatalogProviderDefinition])
async def list_catalog_providers(
    request: Request,
    project_id: PROJECT_ID_QUERY,
    _: AuthContext[Any] = CATALOG_READ_AUTH,
) -> list[CatalogProviderDefinition]:
    service = await _service(project_id, request)
    return await service.list_provider_definitions()


@router.get("/connections", response_model=list[CatalogConnection])
async def list_catalog_connections(
    request: Request,
    project_id: PROJECT_ID_QUERY,
    _: AuthContext[Any] = CATALOG_READ_AUTH,
) -> list[CatalogConnection]:
    service = await _service(project_id, request)
    return await service.list_connections()


@router.post("/connections", response_model=CatalogConnection, status_code=201)
async def create_catalog_connection(
    request: CatalogConnectionRequest,
    http_request: Request,
    project_id: PROJECT_ID_QUERY,
    auth: AuthContext[Any] = CATALOG_WRITE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> CatalogConnection:
    try:
        service = await _service(project_id, http_request)
        connection = await service.create_connection(
            request,
            owner_id=str(auth.user_id) if auth.user else None,
        )
        if connection.connection_kind == CatalogConnectionKind.EXTERNAL:
            dispatch_service = CatalogSyncDispatchService(
                project_id=project_id,
                queue_client=queue_client,
            )
            await dispatch_service.queue_initial_sync(
                connection,
                triggered_by=auth.trigger_actor,
            )
            refreshed = await service.list_connections()
            match = next(
                (item for item in refreshed if item.id == connection.id),
                None,
            )
            if match is not None:
                return match
        return connection
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/connections/{connectionId}", response_model=CatalogConnection)
async def update_catalog_connection(
    connection_id: Annotated[str, CONNECTION_ID_PATH],
    request: CatalogConnectionRequest,
    http_request: Request,
    project_id: PROJECT_ID_QUERY,
    auth: AuthContext[Any] = CATALOG_WRITE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> CatalogConnection:
    try:
        service = await _service(project_id, http_request)
        connection = await service.update_connection(
            connection_id,
            request,
            owner_id=str(auth.user_id) if auth.user else None,
        )
        if connection.connection_kind == CatalogConnectionKind.EXTERNAL:
            dispatch_service = CatalogSyncDispatchService(
                project_id=project_id,
                queue_client=queue_client,
            )
            await dispatch_service.queue_initial_sync(
                connection,
                triggered_by=auth.trigger_actor,
            )
            refreshed = await service.list_connections()
            match = next(
                (item for item in refreshed if item.id == connection.id),
                None,
            )
            if match is not None:
                return match
        return connection
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/connections/{connectionId}", status_code=204)
async def delete_catalog_connection(
    connection_id: Annotated[str, CONNECTION_ID_PATH],
    request: Request,
    project_id: PROJECT_ID_QUERY,
    _: AuthContext[Any] = CATALOG_WRITE_AUTH,
) -> None:
    service = await _service(project_id, request)
    deleted = await service.delete_connection(connection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Catalog connection not found.")


@router.post(
    "/connections/{connectionId}/validate",
    response_model=CatalogConnectionValidationResult,
)
async def validate_catalog_connection(
    connection_id: Annotated[str, CONNECTION_ID_PATH],
    request: Request,
    project_id: PROJECT_ID_QUERY,
    _: AuthContext[Any] = CATALOG_WRITE_AUTH,
) -> CatalogConnectionValidationResult:
    try:
        service = await _service(project_id, request)
        return await service.validate_connection(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/connections/{connectionId}/sync", response_model=CatalogSyncStatus)
async def sync_catalog_connection(
    connection_id: Annotated[str, CONNECTION_ID_PATH],
    request: Request,
    project_id: PROJECT_ID_QUERY,
    _: AuthContext[Any] = CATALOG_WRITE_AUTH,
) -> CatalogSyncStatus:
    try:
        service = await _service(project_id, request)
        return await service.sync_connection(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/entities", response_model=list[CatalogEntitySummary])
async def list_catalog_entities(
    request: Request,
    project_id: PROJECT_ID_QUERY,
    connection_id: str | None = CONNECTION_ID_QUERY,
    namespace_name: str | None = NAMESPACE_NAME_QUERY,
    _: AuthContext[Any] = CATALOG_READ_AUTH,
) -> list[CatalogEntitySummary]:
    service = await _service(project_id, request)
    return await service.list_entities(
        connection_id=connection_id,
        namespace_name=namespace_name,
    )


@router.get("/namespaces", response_model=list[CatalogNamespaceSummary])
async def list_catalog_namespaces(
    request: Request,
    project_id: PROJECT_ID_QUERY,
    connection_id: str | None = CONNECTION_ID_QUERY,
    _: AuthContext[Any] = CATALOG_READ_AUTH,
) -> list[CatalogNamespaceSummary]:
    service = await _service(project_id, request)
    return await service.list_namespaces(connection_id=connection_id)


@router.get("/entities/{entityId}", response_model=CatalogEntityDetail)
async def get_catalog_entity(
    entity_id: Annotated[str, ENTITY_ID_PATH],
    request: Request,
    project_id: PROJECT_ID_QUERY,
    _: AuthContext[Any] = CATALOG_READ_AUTH,
) -> CatalogEntityDetail:
    service = await _service(project_id, request)
    entity = await service.get_entity_detail(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Catalog entity not found.")
    return entity


@router.post("/entities/{entityId}/refresh", response_model=CatalogSyncStatus)
async def refresh_catalog_entity(
    entity_id: Annotated[str, ENTITY_ID_PATH],
    request: Request,
    project_id: PROJECT_ID_QUERY,
    _: AuthContext[Any] = CATALOG_WRITE_AUTH,
) -> CatalogSyncStatus:
    try:
        service = await _service(project_id, request)
        return await service.refresh_entity(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/search", response_model=list[CatalogSearchItem])
async def search_catalog(
    request: Request,
    project_id: PROJECT_ID_QUERY,
    query: str = SEARCH_QUERY,
    connection_id: str | None = CONNECTION_ID_QUERY,
    limit: int = LIMIT_QUERY,
    _: AuthContext[Any] = CATALOG_READ_AUTH,
) -> list[CatalogSearchItem]:
    service = await _service(project_id, request)
    return await service.search(
        query=query,
        connection_id=connection_id,
        limit=limit,
    )
