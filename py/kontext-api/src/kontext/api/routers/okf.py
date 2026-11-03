"""Open Knowledge Format (OKF v0.2) concept curation endpoints.

Exposes a project's curated OKF concepts for read (list/get/search), write
(create/update/delete), and portable bundle export/import. Curated concepts are
the durable home for business context (metric definitions, join semantics,
golden queries) that agents reference. Writes update both the durable ``.okf``
store and its disposable knowledge-index projection.
"""

from __future__ import annotations

import io
import logging
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from kontext.auth import ProjectPermissions
from kontext.catalog.knowledge_service import coerce_concept
from kontext.common.protocols import IKnowledgeServiceProtocol
from kontext.okf import (
    OkfBundle,
    OkfConceptStore,
    load_bundle,
    validate_bundle,
    write_bundle,
)
from kontext.schema import OkfConcept

from ..dependencies import (
    PROJECT_ID_QUERY,
    AuthContext,
    create_auth_dependency,
)
from ..services.runtime import build_authorized_runtime_provider
from ..transport_adapters import build_query_access_context

logger = logging.getLogger(__name__)

router = APIRouter()

#: Module-level singleton for the file upload default (avoids B008).
UPLOAD_FILE = File(...)

CATALOG_READ_AUTH = create_auth_dependency(required_permissions=[ProjectPermissions.READ])
CATALOG_WRITE_AUTH = create_auth_dependency(required_permissions=[ProjectPermissions.UPDATE])


async def _service(auth_context: AuthContext[Any]) -> IKnowledgeServiceProtocol:
    """Resolve the project's knowledge service through the canonical composition.

    OKF curation never dispatches background runs, so the authorized provider
    is built without a queue client. Storage paths and the knowledge index are
    resolved through the provider (project-scoped), never from request headers.
    """
    runtime_provider = build_authorized_runtime_provider(
        project_id=str(auth_context.project_id),
        access_context=build_query_access_context(auth_context),
        queue_client=None,
    )
    service = runtime_provider.get_knowledge_service()
    if service is None:
        raise RuntimeError("The OKF knowledge service is unavailable in this runtime.")
    return service


@router.get("/concepts", operation_id="ListOkfConcepts")
async def list_okf_concepts(
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = CATALOG_READ_AUTH,
) -> list[OkfConcept]:
    """List all curated OKF concepts in the project."""
    service = await _service(auth_context)
    return await service.list_concepts()


@router.get("/concepts/search", operation_id="SearchOkfConcepts")
async def search_okf_concepts(
    project_id: PROJECT_ID_QUERY,
    query: str,
    limit: int = 10,
    auth_context: AuthContext[Any] = CATALOG_READ_AUTH,
) -> list[OkfConcept]:
    """Semantic + lexical search over curated OKF concepts."""
    service = await _service(auth_context)
    return await service.search_concepts(query, limit=limit)


@router.get("/proposals", operation_id="ListOkfProposals")
async def list_okf_proposals(
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = CATALOG_READ_AUTH,
) -> list[OkfConcept]:
    """List agent-proposed concepts awaiting human approval."""
    service = await _service(auth_context)
    return await service.list_proposals()


@router.post("/proposals/{concept_id:path}/approve", operation_id="ApproveOkfProposal")
async def approve_okf_proposal(
    project_id: PROJECT_ID_QUERY,
    concept_id: str,
    auth_context: AuthContext[Any] = CATALOG_WRITE_AUTH,
) -> OkfConcept:
    """Approve a proposed concept, activating it and recording verification."""
    service = await _service(auth_context)
    # Record who verified it using the OKF actor convention (``human:<id>``).
    approved_by = auth_context.actor_label if auth_context.user is not None else "human:unknown"
    approved = await service.approve_concept(concept_id, approved_by=approved_by)
    if approved is None:
        raise HTTPException(status_code=404, detail=f"OKF concept '{concept_id}' not found")
    return approved


@router.get("/concepts/{concept_id:path}", operation_id="GetOkfConcept")
async def get_okf_concept(
    project_id: PROJECT_ID_QUERY,
    concept_id: str,
    auth_context: AuthContext[Any] = CATALOG_READ_AUTH,
) -> OkfConcept:
    """Fetch a single curated OKF concept by id."""
    service = await _service(auth_context)
    concept = await service.get_concept(concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail=f"OKF concept '{concept_id}' not found")
    return concept


@router.put("/concepts/{concept_id:path}", operation_id="UpsertOkfConcept")
async def upsert_okf_concept(
    project_id: PROJECT_ID_QUERY,
    concept_id: str,
    concept: OkfConcept,
    auth_context: AuthContext[Any] = CATALOG_WRITE_AUTH,
) -> OkfConcept:
    """Create or replace a curated OKF concept, refreshing the knowledge index."""
    payload = concept.model_copy(update={"id": concept_id})
    service = await _service(auth_context)
    return await service.upsert_concept(coerce_concept(payload))


@router.delete("/concepts/{concept_id:path}", operation_id="DeleteOkfConcept")
async def delete_okf_concept(
    project_id: PROJECT_ID_QUERY,
    concept_id: str,
    auth_context: AuthContext[Any] = CATALOG_WRITE_AUTH,
) -> dict[str, Any]:
    """Delete a curated OKF concept and its knowledge-index projection."""
    service = await _service(auth_context)
    deleted = await service.delete_concept(concept_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"OKF concept '{concept_id}' not found")
    return {"projectId": str(project_id), "conceptId": concept_id, "deleted": True}


@router.get("/export", operation_id="ExportOkfBundle")
async def export_okf_bundle(
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = CATALOG_READ_AUTH,
) -> StreamingResponse:
    """Export the project's durable OKF concepts as a downloadable bundle."""
    concepts = OkfConceptStore.for_project(str(project_id)).list_concepts()
    bundle = OkfBundle(name=str(project_id), concepts=concepts)

    # Write to a temp dir, then stream a tar.gz of it so we never hold the full
    # archive in memory for large corpora.
    with tempfile.TemporaryDirectory(prefix="kontext-okf-export-") as tmp:
        bundle_dir = Path(tmp) / "bundle"
        write_bundle(bundle, bundle_dir)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            tar.add(bundle_dir, arcname="bundle")
        buffer.seek(0)

    download_name = f"okf-bundle-{project_id}.tar.gz"
    return StreamingResponse(
        buffer,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.post("/import", status_code=200, operation_id="ImportOkfBundle")
async def import_okf_bundle(
    project_id: PROJECT_ID_QUERY,
    file: UploadFile = UPLOAD_FILE,
    auth_context: AuthContext[Any] = CATALOG_WRITE_AUTH,
) -> dict[str, Any]:
    """Import an OKF bundle (``.tar.gz``) into the project's durable OKF store."""
    if not file.filename or not file.filename.endswith(".tar.gz"):
        raise HTTPException(status_code=400, detail="Upload must be a .tar.gz bundle")

    payload = await file.read()
    try:
        buffer = io.BytesIO(payload)
        with (
            tarfile.open(fileobj=buffer, mode="r:gz") as tar,
            tempfile.TemporaryDirectory(prefix="kontext-okf-import-") as tmp,
        ):
            tar.extractall(tmp, filter="data")
            bundle_dir = Path(tmp) / "bundle"
            if not bundle_dir.is_dir():
                # Allow bundles that were not wrapped in a ``bundle/`` dir.
                bundle_dir = Path(tmp)
            bundle = load_bundle(bundle_dir)
            # Surface (but do not reject on) OKF §11 conformance issues in the
            # structural files we skip during load. The concept rules already
            # gate `load_bundle`, so a non-conformant bundle fails above; this
            # reports softer reserved-file problems to the caller.
            conformance = validate_bundle(bundle_dir)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("OKF import failed for project %s: %s", project_id, exc)
        detail = f"Invalid OKF bundle: {exc}"
        raise HTTPException(status_code=400, detail=detail) from exc

    service = await _service(auth_context)
    for concept in bundle:
        await service.upsert_concept(coerce_concept(concept))

    warnings = (
        [f"{issue.path}: {issue.message}" for issue in conformance.issues]
        if not conformance.conformant
        else []
    )

    return {
        "projectId": str(project_id),
        "importedConceptCount": len(bundle),
        "conformanceWarnings": warnings,
        "conceptIds": [concept.id for concept in bundle],
    }
