"""Project-file driven document indexing job for the unified LanceDB corpus."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field

from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.schema import JobCategory

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100

if TYPE_CHECKING:
    from kontext.catalog import DocumentIndexingOutcome, DocumentIndexService
    from kontext.data import FileDataService
    from kontext.data.models import ProjectFile
    from kontext.storage.providers.base import BaseStorageProvider


class DocumentIndexingParams(BaseJobParams):
    """Parameters for document indexing."""

    file_id: str | None = Field(
        default=None,
        description="Project file ID to index or reindex into the document corpus.",
    )
    delete_file_id: str | None = Field(
        default=None,
        description="Project file ID to remove from the document corpus.",
    )
    recreate_index: bool = Field(
        default=False,
        description="Delete all existing indexed documents before a full rebuild.",
    )


@job(
    job_type="python.jobs.DocumentIndexingJob",
    name="Document Indexing",
    description="Indexes project files into the document search index for RAG",
    category=JobCategory.DATAPROCESSING,
    params_model=DocumentIndexingParams,
    display_parameter="file_id",
    is_system_job=True,
    icon="file-search",
    required_permissions=[],
)
class DocumentIndexingJob(BasePythonJob[DocumentIndexingParams]):
    """Indexes knowledge documents from `ProjectFile` rows and storage URIs."""

    async def execute_job(
        self, context: JobContext, parameters: DocumentIndexingParams
    ) -> JobResult:
        project_id = context.project_id
        if not project_id:
            return JobResult.error_result("Project ID not available")

        if parameters.file_id and parameters.delete_file_id:
            return JobResult.error_result("Provide only one of file_id or delete_file_id.")

        from kontext.catalog import DocumentIndexService
        from kontext.data import FileDataService
        from kontext.storage.factory import get_storage_provider

        project_uuid = UUID(str(project_id))
        data_service = FileDataService(project_uuid)
        storage_provider: BaseStorageProvider = get_storage_provider()
        index_service = DocumentIndexService(
            project_id=project_id,
            runtime_provider=context.get_runtime_provider(),
        )

        if parameters.delete_file_id:
            await index_service.delete_project_file(parameters.delete_file_id)
            message = f"Removed indexed document rows for file {parameters.delete_file_id}"
            await context.log_info(message)
            return JobResult.success_result(
                message=message,
                data={"files_deleted": 1, "file_id": parameters.delete_file_id},
            )

        if parameters.file_id:
            return await self._index_single_file(
                context=context,
                data_service=data_service,
                storage_provider=storage_provider,
                index_service=index_service,
                file_id=parameters.file_id,
            )

        if parameters.recreate_index:
            await context.log_info("Recreating document index before rebuild")
            await index_service.clear_index()

        await context.log_info("Rebuilding document index from active project files")

        files_indexed = 0
        files_skipped = 0
        chunks_indexed = 0
        errors: list[str] = []

        cursor: UUID | None = None
        while True:
            batch = await data_service.get_non_deleted_files_batch_by_cursor_async(
                project_uuid,
                cursor=cursor,
                batch_size=_BATCH_SIZE,
            )
            if not batch:
                break

            for project_file in batch:
                cursor = project_file.id
                result = await self._index_project_file_record(
                    context=context,
                    storage_provider=storage_provider,
                    index_service=index_service,
                    project_file=project_file,
                )
                if result.error_message:
                    errors.append(result.error_message)
                elif result.skip_reason:
                    files_skipped += 1
                else:
                    files_indexed += 1
                    chunks_indexed += result.chunks_indexed

            if len(batch) < _BATCH_SIZE:
                break

        summary = (
            f"Indexed {files_indexed} files ({chunks_indexed} chunks); "
            f"skipped {files_skipped} files"
        )
        if errors:
            summary += f"; {len(errors)} errors"
        await context.log_info(summary)
        return JobResult.success_result(
            message=summary,
            data={
                "files_indexed": files_indexed,
                "files_skipped": files_skipped,
                "chunks_indexed": chunks_indexed,
                "errors": errors,
            },
        )

    async def _index_single_file(
        self,
        *,
        context: JobContext,
        data_service: FileDataService,
        storage_provider: BaseStorageProvider,
        index_service: DocumentIndexService,
        file_id: str,
    ) -> JobResult:
        try:
            file_uuid = UUID(str(file_id))
        except ValueError as exc:
            return JobResult.error_result(f"Invalid file_id: {exc}")

        project_file = await data_service.get_file_by_id_async(file_uuid)
        if project_file is None or project_file.is_deleted:
            await index_service.delete_project_file(file_id)
            message = f"Removed stale document index rows for missing file {file_id}"
            await context.log_info(message)
            return JobResult.success_result(
                message=message,
                data={"files_deleted": 1, "file_id": file_id},
            )

        result = await self._index_project_file_record(
            context=context,
            storage_provider=storage_provider,
            index_service=index_service,
            project_file=project_file,
        )
        if result.error_message:
            return JobResult.error_result(
                message=result.error_message,
                data={"file_id": file_id},
            )
        if result.skip_reason:
            message = f"Skipped file {project_file.name}: {result.skip_reason}"
            return JobResult.success_result(
                message=message,
                data={"file_id": file_id, "skip_reason": result.skip_reason},
            )

        message = f"Indexed file {project_file.name} into {result.chunks_indexed} document chunks"
        return JobResult.success_result(
            message=message,
            data={
                "file_id": file_id,
                "chunks_indexed": result.chunks_indexed,
                "parser_name": result.parser_name,
            },
        )

    async def _index_project_file_record(
        self,
        *,
        context: JobContext,
        storage_provider: BaseStorageProvider,
        index_service: DocumentIndexService,
        project_file: ProjectFile,
    ) -> DocumentIndexingOutcome:
        from kontext.catalog import DocumentIndexingOutcome

        file_id = str(project_file.id)
        file_name = project_file.name
        if not index_service.is_project_file_indexable(
            file_name=file_name,
            content_type=project_file.content_type,
            file_type=project_file.file_type,
        ):
            await index_service.delete_project_file(file_id)
            skip_reason = "file type is not supported for document indexing"
            await context.log_info(f"Skipping {file_name}: {skip_reason}")
            return DocumentIndexingOutcome(
                source_id=f"file:{file_id}",
                skip_reason=skip_reason,
            )

        if not project_file.uri:
            await index_service.delete_project_file(file_id)
            skip_reason = f"Skipping {file_name}: file has no storage URI"
            await context.log_info(skip_reason)
            return DocumentIndexingOutcome(
                source_id=f"file:{file_id}",
                skip_reason="file has no storage URI",
            )

        try:
            stream = await storage_provider.download_file(project_file.uri)
            content_bytes = stream.getvalue()
        except Exception as exc:
            error_message = f"Failed to download {file_name}: {exc}"
            await context.log_warning(error_message)
            return DocumentIndexingOutcome(
                source_id=f"file:{file_id}",
                error_message=error_message,
            )

        updated_at = project_file.date_modified or project_file.date_created
        outcome = await index_service.index_project_file(
            file_id=file_id,
            file_name=file_name,
            content_type=project_file.content_type,
            file_type=project_file.file_type,
            content_bytes=content_bytes,
            updated_at=updated_at.isoformat() if updated_at else None,
        )
        if outcome.error_message:
            await context.log_warning(f"Failed to index {file_name}: {outcome.error_message}")
        elif outcome.skip_reason:
            await context.log_info(f"Skipping {file_name}: {outcome.skip_reason}")
        else:
            await context.log_info(f"Indexed {file_name} into {outcome.chunks_indexed} chunks")
        return outcome
