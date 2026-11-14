"""
File API endpoints for file uploads, downloads, and metadata management.

These endpoints manage files associated with projects.
"""

import logging
import os
from io import BytesIO
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from kontext.auth import FilePermissions
from kontext.common.jobs.trigger_actor import notebook_actor
from kontext.common.messaging import IQueueClient
from kontext.file import file_to_model, infer_file_type
from kontext.file.factories import create_file_service
from kontext.file.factories import get_file_resource as load_file_resource
from kontext.jobs import (
    NotebookPythonExecutionError,
    NotebookPythonExecutionService,
)
from kontext.schema import (
    ArtifactOrigin,
    ArtifactProvenance,
    CreateMultipleFilesResponse,
    FileFormatType,
    FileModel,
    FileUploadResponse,
    InlineData,
    PaginatedFileResponse,
    PythonExecutionResult,
)

from ..dependencies import (
    BLOCK_ID_PATH,
    FILE_ID_PATH,
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_QUERY,
    QUEUE_CLIENT_DEP,
    AuthContext,
    create_auth_dependency,
    extract_path_param,
    get_client_ip,
)
from ..validators import (
    BulkFileIdsRequest,
    CreateFileRequest,
    UpdateFileRequest,
    UpdateFileSchemaRequest,
)

logger = logging.getLogger(__name__)


async def get_file_resource(request: Request, auth_context: AuthContext[Any]) -> Any | None:
    """Fetch a file record for ownership checks."""
    file_id = extract_path_param(request, "file_id")
    if not file_id:
        return None
    return await load_file_resource(
        auth_context.project_id,
        UUID(str(file_id)),
    )


router = APIRouter()


class ExecuteNotebookPythonRequest(BaseModel):
    """Optional draft execution payload for notebook Python blocks."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    code_override: str | None = Field(default=None, alias="codeOverride")
    run_id: UUID | None = Field(
        default=None,
        alias="runId",
        description=(
            "Optional client-supplied run ID (idempotency key). Supplying it lets "
            "the caller cancel the run while it is still executing."
        ),
    )


# =============================================================================
# Type Aliases for FastAPI Dependencies
# =============================================================================

FileUpload = Annotated[UploadFile, File(description="File to upload")]
MultipleFileUpload = Annotated[list[UploadFile], File(description="Files to upload")]


# =============================================================================
# Authorization Dependencies
# =============================================================================

FILE_CREATE_AUTH = create_auth_dependency(required_permissions=[FilePermissions.CREATE])
FILE_READ_AUTH = create_auth_dependency(
    required_permissions=[FilePermissions.READ],
    resource_getter=get_file_resource,
    allow_owner=True,
)
FILE_UPDATE_AUTH = create_auth_dependency(
    required_permissions=[FilePermissions.UPDATE],
    resource_getter=get_file_resource,
    allow_owner=True,
)
FILE_DELETE_AUTH = create_auth_dependency(
    required_permissions=[FilePermissions.DELETE],
    resource_getter=get_file_resource,
    allow_owner=True,
)

# Additional query parameters specific to files
FILE_TYPES_QUERY: list[FileFormatType] | None = Query(
    None, alias="fileTypes", description="Filter by file types"
)
FILTER_STRING_QUERY: str | None = Query(None, alias="filterString", description="Filter by name")
PREFIX_QUERY: str | None = Query(
    None,
    alias="prefix",
    description=("Filter by logical folder prefix. Omit for the legacy flat project-wide list."),
)
MY_FILES_ONLY_QUERY: bool = Query(
    False,
    alias="myFilesOnly",
    description="Whether to return only the current user's owned resources",
)
INCLUDE_SYSTEM_PREFIXES_QUERY: bool = Query(
    True,
    alias="includeSystemPrefixes",
    description=("Whether root folder listings should include system-managed virtual folders"),
)
ALLOW_OVERWRITE_QUERY: bool = Query(
    default=False,
    alias="allowOverwrite",
    description="If true, overwrite existing files with the same name",
)

# Service dependencies


# =============================================================================
# Service Factory
# =============================================================================


def _buffered_length(file_stream: object) -> int:
    """Number of bytes actually buffered in a download stream.

    Storage providers hand back a fully materialized ``BytesIO``; sizing the
    response from it (instead of the DB row's size, which can be seconds stale
    while agent tool calls persist into the same file) guarantees the declared
    ``Content-Length`` always matches the body served.
    """
    if isinstance(file_stream, BytesIO):
        return int(file_stream.getbuffer().nbytes)
    return -1


# =============================================================================
# File Endpoints
# =============================================================================


@router.get("", response_model=PaginatedFileResponse, operation_id="ListFiles")
async def list_files(
    project_id: PROJECT_ID_QUERY,
    my_files_only: bool = MY_FILES_ONLY_QUERY,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    file_types: list[FileFormatType] | None = FILE_TYPES_QUERY,
    filter_string: str | None = FILTER_STRING_QUERY,
    prefix: str | None = PREFIX_QUERY,
    include_system_prefixes: bool = INCLUDE_SYSTEM_PREFIXES_QUERY,
    auth_context: AuthContext[Any] = FILE_READ_AUTH,
) -> PaginatedFileResponse:
    """
    List files for a project with pagination.

    Returns paginated list of files.
    The project_id query parameter is required for authorization.
    Supports filtering by file types and name.
    """
    service = create_file_service(project_id)

    # Determine owner filter
    # Default: Use effective_owner_id (None for admins, user_id for regular users)
    # If my_files_only is True: Always use user_id
    owner_filter = auth_context.user_id if my_files_only else auth_context.effective_owner_id

    result = await service.list_files(
        project_id=project_id,
        page_index=page_index,
        page_size=page_size,
        filter_string=filter_string,
        prefix=prefix,
        file_types=file_types,
        owner_id=owner_filter,
        include_system_prefixes=include_system_prefixes,
    )

    return PaginatedFileResponse(
        items=result.items,
        total_count=result.total_count,
        page_index=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get("/{fileId}", response_model=FileModel, operation_id="GetFile")
async def get_file(
    file_id: Annotated[UUID, FILE_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = FILE_READ_AUTH,
) -> FileModel:
    """
    Get a specific file by ID.

    The project_id query parameter is required for authorization.
    """
    _ = project_id  # Used for authorization
    # Use the resource already fetched by the auth dependency
    file_record = auth_context.resource
    if not file_record:
        service = create_file_service(project_id)
        file_record = await service.get_file_by_id(file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")

    return file_to_model(file_record)


@router.get("/{fileId}/rows", response_model=InlineData, operation_id="GetDataTableRows")
async def get_data_table_rows(
    file_id: Annotated[UUID, FILE_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    offset: int = Query(default=0, ge=0, description="Zero-based row offset"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum rows to return"),
    auth_context: AuthContext[Any] = FILE_READ_AUTH,
) -> InlineData:
    """
    Return a window of full rows for a data-table file.

    Large results keep only a preview in their ``.dt`` descriptor; this reads
    the full rows from the companion Parquet store. ``table.rowCount`` is the
    total number of rows, so callers can paginate with ``offset``/``limit``.
    """
    _ = project_id, auth_context  # Used for authorization
    service = create_file_service(project_id)
    return await service.get_inline_data_rows(project_id, file_id, offset=offset, limit=limit)


@router.get("/{fileId}/exists", response_model=bool, operation_id="CheckFileExists")
async def check_file_exists(
    file_id: Annotated[UUID, FILE_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = FILE_READ_AUTH,
) -> bool:
    """
    Check if a file exists without fetching its full metadata.

    The project_id query parameter is required for authorization.
    Returns True if the file exists and the user has access.
    """
    _ = project_id  # Used for authorization
    # If the auth dependency already found the resource, it exists
    if auth_context.resource:
        return True

    # If not in auth_context, double check via service
    # This handles cases where user has project permissions
    # but resource wasn't pre-loaded
    service = create_file_service(project_id)
    return await service.exists_by_id(project_id=project_id, file_id=file_id)


@router.post(
    "/{fileId}/notebook/blocks/{blockId}/execute-python",
    response_model=PythonExecutionResult,
    operation_id="ExecuteNotebookPythonBlock",
)
async def execute_notebook_python_block(
    file_id: Annotated[UUID, FILE_ID_PATH],
    block_id: Annotated[UUID, BLOCK_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    payload: ExecuteNotebookPythonRequest | None = None,
    auth_context: AuthContext[Any] = FILE_UPDATE_AUTH,
) -> PythonExecutionResult:
    """
    Execute a Python notebook block through the managed CPython runner.

    The project_id query parameter is required for authorization.
    """
    _ = project_id  # Used for authorization
    try:
        if not auth_context.resource:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")

        service = NotebookPythonExecutionService(file_service=create_file_service(project_id))
        code_override = payload.code_override if payload else None
        if code_override is not None and not code_override.strip():
            # A blank-string override means "execute the stored block" (the
            # client resolver normalizes this before calling), not a draft run.
            code_override = None
        return await service.execute_notebook_code_async(
            project_id=str(project_id),
            notebook_id=str(file_id),
            block_id=str(block_id),
            code_override=code_override,
            persist_notebook_state=payload is None or code_override is None,
            owner_id=auth_context.user_id,
            triggered_by=notebook_actor(str(file_id)),
            run_id=payload.run_id if payload else None,
        )
    except NotebookPythonExecutionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.error,
        ) from exc


@router.post("", response_model=FileModel, status_code=201, operation_id="CreateFile")
async def create_file(
    request: CreateFileRequest,
    auth_context: AuthContext[Any] = FILE_CREATE_AUTH,
) -> FileModel:
    """
    Create a file record.

    This creates the metadata record. File content should be uploaded
    separately using the upload endpoint.
    """
    try:
        project_id = UUID(request.project_id)
        service = create_file_service(project_id)
        owner_id = auth_context.user_id

        file_record = await service.create_file_metadata(
            project_id=project_id,
            name=request.name,
            prefix=request.prefix,
            content_type=request.content_type,
            file_type=request.file_type,
            owner_id=owner_id,
        )

        return file_to_model(file_record)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.put("/{fileId}", response_model=FileModel, operation_id="UpdateFile")
async def update_file(
    file_id: Annotated[UUID, FILE_ID_PATH],
    request: UpdateFileRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = FILE_UPDATE_AUTH,
) -> FileModel:
    """
    Update a file's metadata.

    The project_id query parameter is required for authorization.
    """
    _ = project_id  # Used for authorization
    try:
        service = create_file_service(project_id)

        # Use the resource already fetched by the auth dependency
        file = auth_context.resource
        if not file:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")

        file_record = await service.update_file_metadata(
            file_id=file_id,
            name=request.name,
            prefix=request.prefix,
            content_type=request.content_type,
        )

        return file_to_model(file_record)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{fileId}/schema", response_model=FileModel, operation_id="UpdateFileSchema")
async def update_file_schema(
    file_id: Annotated[UUID, FILE_ID_PATH],
    request: UpdateFileSchemaRequest,
    http_request: Request,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = FILE_UPDATE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> FileModel:
    """
    Update a file's schema and statistics.

    This endpoint is typically called after profiling a file.
    Records a FileSchemaUpdated audit event after lakehouse ingest updates
    file metadata.
    """
    try:
        service = create_file_service(project_id, queue_client)

        # Use the resource already fetched by the auth dependency
        file = auth_context.resource
        if not file:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")

        user_id = auth_context.user_id
        ip_address = get_client_ip(http_request)

        # Convert Pydantic models to JSON strings for storage
        schema_json = (
            request.schema_definition.model_dump_json(
                by_alias=True, exclude_none=True, exclude_unset=True
            )
            if request.schema_definition
            else None
        )
        stats_json = (
            request.statistics_data.model_dump_json(
                by_alias=True, exclude_none=True, exclude_unset=True
            )
            if request.statistics_data
            else None
        )

        file_record = await service.update_file_schema(
            file_id=file_id,
            project_id=project_id,
            schema_json=schema_json,
            stats_json=stats_json,
            column_count=request.column_count,
            row_count=request.row_count,
            size=request.size,
            user_id=user_id,
            ip_address=ip_address,
        )

        return file_to_model(file_record)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{fileId}", status_code=204, operation_id="DeleteFile")
async def delete_file(
    file_id: Annotated[UUID, FILE_ID_PATH],
    http_request: Request,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = FILE_DELETE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> None:
    """
    Soft delete a file.

    The project_id query parameter is required for authorization.
    """
    try:
        service = create_file_service(project_id, queue_client)

        # Use the resource already fetched by the auth dependency
        file = auth_context.resource
        if not file:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")

        user_id = auth_context.user_id
        ip_address = get_client_ip(http_request)

        await service.delete_file(
            file_id=file_id,
            project_id=project_id,
            user_id=user_id,
            ip_address=ip_address,
            triggered_by=auth_context.trigger_actor,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{fileId}/download", operation_id="DownloadFile")
async def download_file(
    file_id: Annotated[UUID, FILE_ID_PATH],
    request: Request,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = FILE_READ_AUTH,
) -> StreamingResponse:
    """
    Download a file file.

    Returns the file content as a streaming response.
    Supports HTTP Range requests for partial downloads.
    """
    _ = project_id  # Used for authorization
    try:
        # Use the resource already fetched by the auth dependency
        file_record = auth_context.resource
        if not file_record:
            service = create_file_service(project_id)
            file_record = await service.get_file_for_download(file_id)

        if not file_record or not file_record.uri:
            raise HTTPException(
                status_code=404, detail=f"File {file_id} not found or has no content"
            )

        service = create_file_service(project_id)
        range_header = request.headers.get("Range")

        # Handle Range requests (important for DuckDB and large files)
        if range_header and range_header.startswith("bytes=") and file_record.size:
            try:
                byte_range = range_header.replace("bytes=", "").split("-")
                start = int(byte_range[0])
                # If end is not specified, go to the end of the file
                end = (
                    int(byte_range[1])
                    if len(byte_range) > 1 and byte_range[1]
                    else file_record.size - 1
                )

                # Ensure range is valid
                if start >= file_record.size:
                    raise HTTPException(
                        status_code=416,
                        detail=f"Range Not Satisfiable: {start} >= {file_record.size}",
                    )

                end = min(end, file_record.size - 1)
                length = end - start + 1

                file_stream = await service.download_file_range(str(file_record.uri), start, length)

                # Size the response from the actual bytes served: the DB row's
                # size can be stale relative to the storage object (agent tool
                # calls persist into these files while downloads run), and a
                # declared length that does not match the body makes browsers
                # abort the response (ERR_CONTENT_LENGTH_MISMATCH).
                served_length = _buffered_length(file_stream)
                if served_length == 0:
                    raise HTTPException(
                        status_code=416,
                        detail=f"Range Not Satisfiable: no content at offset {start}",
                    )

                headers: dict[str, str] = {
                    "Accept-Ranges": "bytes",
                    "Content-Disposition": (
                        f"attachment; filename*=UTF-8''{quote(os.path.basename(file_record.name))}"
                    ),
                }
                status_code = 206
                if served_length < 0:
                    # Unknown length (streaming provider did not buffer): a
                    # 206 must declare a Content-Range, so degrade to a plain
                    # 200 response instead of sending one we cannot back up.
                    status_code = 200
                else:
                    actual_end = start + served_length - 1
                    range_total = max(int(file_record.size or 0), actual_end + 1)
                    headers["Content-Range"] = f"bytes {start}-{actual_end}/{range_total}"
                    headers["Content-Length"] = str(served_length)

                return StreamingResponse(
                    content=file_stream,
                    status_code=status_code,
                    media_type=file_record.content_type or "application/octet-stream",
                    headers=headers,
                )
            except (ValueError, IndexError) as e:
                logger.warning(f"Malformed Range header: {range_header}, error: {e}")
                # Fall back to full download if range is malformed

        # Full download
        # uri is guaranteed to be non-None here
        file_stream = await service.download_file_stream(str(file_record.uri))
        # The provider materializes the object before returning; serve the
        # verified byte count rather than the DB row's size so the declared
        # length always matches the body.
        served_length = _buffered_length(file_stream)

        full_headers = {
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(os.path.basename(file_record.name))}"
            ),
            "Accept-Ranges": "bytes",
        }
        if served_length and served_length > 0:
            full_headers["Content-Length"] = str(served_length)

        return StreamingResponse(
            content=file_stream,
            media_type=file_record.content_type or "application/octet-stream",
            headers=full_headers,
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/bulk", response_model=list[FileModel], operation_id="GetFilesByIds")
async def get_files_by_ids(
    request: BulkFileIdsRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = FILE_READ_AUTH,
) -> list[FileModel]:
    """
    Get multiple files by their IDs.

    Maximum 100 file IDs can be requested at once.
    """
    _ = project_id  # Used for authorization
    service = create_file_service(project_id)
    file_uuids = [UUID(rid) for rid in request.file_ids]
    # Service now returns FileModel list directly (Protocol compliant)
    return await service.get_files_by_ids(project_id, file_uuids)


# =============================================================================
# File Upload Endpoints
# =============================================================================


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=201,
    operation_id="UploadFile",
)
async def upload_file(
    file: FileUpload,
    http_request: Request,
    project_id: PROJECT_ID_QUERY,
    name: str | None = None,
    prefix: str | None = PREFIX_QUERY,
    auth_context: AuthContext[Any] = FILE_CREATE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> FileUploadResponse:
    """
    Upload a file and create a file.

    This endpoint handles file upload and creates the file record.
    If name is not provided, uses the original filename.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    if not auth_context.project:
        raise HTTPException(status_code=400, detail="Project context required")

    try:
        logger.info(
            "UploadFile request received (project_id=%s, filename=%s, has_queue=%s)",
            project_id,
            file.filename,
            queue_client is not None,
        )
        service = create_file_service(project_id, queue_client)

        effective_owner_id = auth_context.user_id
        ip_address = get_client_ip(http_request)

        file_record = await service.upload_single_file(
            project_id=project_id,
            upload_file=file,
            name=name,
            prefix=prefix,
            owner_id=effective_owner_id,
            ip_address=ip_address,
            triggered_by=auth_context.trigger_actor,
            provenance=ArtifactProvenance(
                origin=ArtifactOrigin.UPLOAD,
                created_by=auth_context.trigger_actor,
            ),
        )

        return FileUploadResponse(file=file_to_model(file_record))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/upload-multiple",
    response_model=CreateMultipleFilesResponse,
    status_code=201,
    operation_id="UploadMultipleFiles",
)
async def upload_multiple_files(
    files: MultipleFileUpload,
    http_request: Request,
    project_id: PROJECT_ID_QUERY,
    allow_overwrite: bool = ALLOW_OVERWRITE_QUERY,
    prefix: str | None = PREFIX_QUERY,
    auth_context: AuthContext[Any] = FILE_CREATE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> CreateMultipleFilesResponse:
    """
    Upload multiple files and create files.

    Returns a summary of successful and failed uploads.
    If allow_overwrite is true, existing files with the same name
    will be updated instead of creating duplicates.
    """
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    if not auth_context.project:
        raise HTTPException(status_code=400, detail="Project context required")

    logger.info(
        (
            "UploadMultipleFiles request received (project_id=%s, files=%s, "
            "allow_overwrite=%s, has_queue=%s)"
        ),
        project_id,
        len(files),
        allow_overwrite,
        queue_client is not None,
    )
    service = create_file_service(project_id, queue_client)

    effective_owner_id = auth_context.user_id
    ip_address = get_client_ip(http_request)

    # Upload files - returns (created, updated, errors)
    # Cast files to list for type compatibility
    # (UploadFile implements UploadFileProtocol)
    (created_files, updated_files, errors) = await service.upload_multiple_files(
        project_id=project_id,
        files=list(files),
        prefix=prefix,
        owner_id=effective_owner_id,
        ip_address=ip_address,
        allow_overwrite=allow_overwrite,
        infer_type_func=infer_file_type,
        triggered_by=auth_context.trigger_actor,
        provenance=ArtifactProvenance(
            origin=ArtifactOrigin.UPLOAD,
            created_by=auth_context.trigger_actor,
        ),
    )

    # Combine for response
    successful_files = created_files + updated_files

    logger.info(
        f"Multiple upload completed for project {project_id}: "
        f"{len(created_files)} created, {len(updated_files)} updated, "
        f"{len(errors)} failed"
    )

    # Convert to view models
    file_models = [file_to_model(r) for r in successful_files]

    return CreateMultipleFilesResponse(
        files=file_models,
        success_count=len(successful_files),
        failure_count=len(errors),
        errors=errors if errors else None,
    )


@router.put("/{fileId}/upload", response_model=FileModel, operation_id="UpdateFileContent")
async def update_file_content(
    file_id: Annotated[UUID, FILE_ID_PATH],
    file: FileUpload,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = FILE_UPDATE_AUTH,
) -> FileModel:
    """
    Replace a file's file content.

    The file name is preserved unless a new file with different name
    is uploaded.
    """
    _ = project_id  # Used for authorization
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    try:
        service = create_file_service(project_id)

        # Use the resource already fetched by the auth dependency
        file_entity = auth_context.resource
        if not file_entity:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")

        file_record = await service.update_file_content(
            file_id=file_id,
            upload_file=file,
            owner_id=auth_context.user_id,
            triggered_by=auth_context.trigger_actor,
        )

        return file_to_model(file_record)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
