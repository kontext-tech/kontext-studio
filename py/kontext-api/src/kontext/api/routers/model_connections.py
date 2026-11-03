"""Model connection and executable catalog endpoints for local mode."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from kontext.account import (
    ModelConnectionValidationError,
    UserProfile,
    create_model_connection,
    delete_model_connection,
    list_model_connections,
    update_model_connection,
)
from kontext.common import SiteFeature
from kontext.schema import (
    ModelAvailability,
    ModelCatalogEntry,
    ModelConnection,
    ModelProviderDefinition,
)

from ..dependencies import (
    CONNECTION_ID_PATH,
    require_site_feature,
)
from ..dependencies.local_auth import get_current_user

router = APIRouter(
    tags=["ModelConnections"],
    dependencies=[require_site_feature(SiteFeature.MODEL_CONNECTIONS)],
)

_CURRENT_USER_DEP = Depends(get_current_user)


def _build_catalog_entries() -> list[ModelCatalogEntry]:
    from kontext.llm import LanguageModelService, get_default_provider_model_name

    foundation_model_by_id = {
        model.canonical_model_id: model for model in LanguageModelService().list_model_definitions()
    }

    entries: list[ModelCatalogEntry] = []
    for connection in list_model_connections():
        if not connection.enabled or connection.validation_state != "valid":
            continue

        model_meta = foundation_model_by_id.get(connection.canonical_model_id)
        reasoning_supported = bool(model_meta.reasoning_supported) if model_meta else False

        provider_model_name = connection.provider_model_name
        if provider_model_name is None and model_meta is not None:
            provider_model_name = get_default_provider_model_name(
                model_meta, connection.connection_kind
            )

        entries.append(
            ModelCatalogEntry(
                selection_id=connection.id or "",
                canonical_model_id=connection.canonical_model_id,
                source_type=connection.source_type,
                display_name=connection.display_name,
                adapter_type=connection.adapter_type,
                connection_kind=connection.connection_kind,
                provider_config=connection.provider_config,
                provider_model_name=provider_model_name,
                endpoint_base_url=connection.endpoint_base_url,
                reasoning_effort=connection.reasoning_effort,
                reasoning_supported=reasoning_supported,
                availability=ModelAvailability.AVAILABLE,
                validation_state=connection.validation_state,
                enabled=connection.enabled,
            )
        )

    return entries


@router.get("/model-connections")
def get_model_connections(
    current_user: UserProfile = _CURRENT_USER_DEP,
) -> list[ModelConnection]:
    """Return all local model connections with secret-safe fields only."""
    _ = current_user
    return list_model_connections()


@router.get("/model-connections/providers")
def get_model_connection_providers(
    current_user: UserProfile = _CURRENT_USER_DEP,
) -> list[ModelProviderDefinition]:
    """Return provider definitions for model connection forms and validation."""
    _ = current_user
    from kontext.llm import LanguageModelService

    return LanguageModelService().list_provider_definitions()


@router.post("/model-connections", status_code=201)
def add_model_connection(
    connection: ModelConnection, current_user: UserProfile = _CURRENT_USER_DEP
) -> ModelConnection:
    """Create a new local model connection entry."""
    connection.id = str(uuid4())
    connection.owner_id = current_user.id
    try:
        return create_model_connection(connection)
    except ModelConnectionValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors) from exc


@router.put("/model-connections/{connectionId}")
def edit_model_connection(
    connection_id: Annotated[str, CONNECTION_ID_PATH],
    connection: ModelConnection,
    current_user: UserProfile = _CURRENT_USER_DEP,
) -> ModelConnection:
    """Update an existing local model connection entry."""
    connection.owner_id = current_user.id
    try:
        result = update_model_connection(connection_id, connection)
    except ModelConnectionValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Model connection not found.")
    return result


@router.delete("/model-connections/{connectionId}", status_code=204)
def remove_model_connection(
    connection_id: Annotated[str, CONNECTION_ID_PATH],
    current_user: UserProfile = _CURRENT_USER_DEP,
) -> None:
    """Delete a local model connection entry."""
    _ = current_user
    if not delete_model_connection(connection_id):
        raise HTTPException(status_code=404, detail="Model connection not found.")


@router.get("/models/catalog")
def get_model_catalog(
    current_user: UserProfile = _CURRENT_USER_DEP,
) -> list[ModelCatalogEntry]:
    """Return executable local model catalog entries."""
    _ = current_user
    return _build_catalog_entries()
