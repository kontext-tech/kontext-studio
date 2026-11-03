"""File post-upload processing: job dispatch plans and workflow orchestration.

Owns the mapping from file processing intent (lakehouse ingest, document
indexing, cleanup) to queued job runs and multi-step workflows, extracted from
``FileService`` so upload persistence and processing orchestration stay
separate concerns.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.common.messaging import IQueueClient
from kontext.common.project_scoped import ProjectScopedService
from kontext.common.utils.enum_utils import safe_enum_conversion
from kontext.common.utils.file_storage import is_system_managed_project_file_prefix
from kontext.execution.scheduling import create_queued_job_run_and_maybe_dispatch
from kontext.execution.workflows import (
    WorkflowJobStepDefinition,
    WorkflowOrchestrationService,
    WorkflowStartRequest,
)
from kontext.jobs.service import JobService
from kontext.schema import FileFormatType, JobTriggerType, TriggerActorModel

from .helpers import should_trigger_profiling_job

logger = logging.getLogger(__name__)

_DOCUMENT_INDEXING_JOB_TYPE = "python.jobs.DocumentIndexingJob"
_DOCUMENT_INDEXING_JOB_NAME = "Document Indexing"
_DOCUMENT_INDEXING_JOB_DESCRIPTION = "Indexes project files into the document search index for RAG"


FileProcessingTarget = Literal["lakehouse", "document", "none"]


@dataclass(frozen=True)
class FileProcessingPlan:
    file_id: UUID | str
    old_target: FileProcessingTarget
    new_target: FileProcessingTarget
    old_file_type: FileFormatType | str | None = None
    old_prefix: str | None = None
    new_prefix: str | None = None


@dataclass(frozen=True)
class JobDispatchPlan:
    step_key: str
    step_name: str
    job_id: UUID
    job_type: str
    job_name: str
    parameters: dict[str, str]
    timeout_seconds: int | None
    job_description: str | None = None
    priority: int = 5


class FileProcessingService(ProjectScopedService):
    """Plans and dispatches post-upload file processing jobs and workflows."""

    def __init__(
        self,
        *,
        project_id: UUID | str,
        queue_client: IQueueClient | None = None,
    ):
        super().__init__(project_id)
        self._queue_client = queue_client

    async def _queue_lakehouse_ingest(
        self,
        *,
        file_ids: Sequence[UUID | str],
        triggered_by: TriggerActorModel | None,
    ) -> None:
        dispatch_plan = await self._build_lakehouse_ingest_dispatch_plan(
            file_ids=file_ids,
            triggered_by=triggered_by,
        )
        if dispatch_plan is None:
            return

        await self._dispatch_job_plan(
            dispatch_plan,
            triggered_by=triggered_by,
        )

    async def queue_document_indexing(
        self,
        *,
        file_id: UUID | str | None = None,
        delete_file_id: UUID | str | None = None,
        triggered_by: TriggerActorModel | None,
    ) -> None:
        dispatch_plan = await self._build_document_indexing_dispatch_plan(
            file_id=file_id,
            delete_file_id=delete_file_id,
            triggered_by=triggered_by,
        )
        if dispatch_plan is None:
            return

        await self._dispatch_job_plan(
            dispatch_plan,
            triggered_by=triggered_by,
        )

    async def _queue_lakehouse_cleanup(
        self,
        *,
        file_id: UUID | str,
        file_type: FileFormatType | str | None,
        triggered_by: TriggerActorModel | None,
    ) -> None:
        dispatch_plan = await self._build_lakehouse_cleanup_dispatch_plan(
            file_id=file_id,
            file_type=file_type,
            triggered_by=triggered_by,
        )
        if dispatch_plan is None:
            return

        await self._dispatch_job_plan(
            dispatch_plan,
            triggered_by=triggered_by,
        )

    async def _dispatch_job_plan(
        self,
        dispatch_plan: JobDispatchPlan,
        *,
        triggered_by: TriggerActorModel | None,
        trigger_type: JobTriggerType = JobTriggerType.MANUAL,
        trigger_configuration: dict[str, str] | None = None,
    ) -> None:
        await create_queued_job_run_and_maybe_dispatch(
            project_id=self.project_id,
            queue_client=self._queue_client,
            job_id=dispatch_plan.job_id,
            parameters=dispatch_plan.parameters,
            job_type=dispatch_plan.job_type,
            job_name=dispatch_plan.job_name,
            timeout_seconds=dispatch_plan.timeout_seconds,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            trigger_configuration=(
                json.dumps(trigger_configuration) if trigger_configuration else None
            ),
            priority=dispatch_plan.priority,
        )

    async def _build_lakehouse_ingest_dispatch_plan(
        self,
        *,
        file_ids: Sequence[UUID | str],
        triggered_by: TriggerActorModel | None,
    ) -> JobDispatchPlan | None:
        normalized_file_ids = [str(file_id) for file_id in file_ids if file_id]
        if not normalized_file_ids:
            return None

        from .jobs import LakehouseIngestJob

        job_metadata = LakehouseIngestJob.get_job_metadata()
        job_service = JobService(project_id=self.project_id)
        job_entity = await job_service.ensure_job_exists_async(
            job_type=job_metadata.type,
            name=job_metadata.name or "Lakehouse Ingest",
            description=job_metadata.description,
            timeout=300,
            created_by=format_trigger_actor(triggered_by),
        )
        if not job_entity or not job_entity.id:
            logger.warning("Could not find or create job definition for lakehouse ingest")
            return None

        return JobDispatchPlan(
            step_key="lakehouse-ingest",
            step_name="Lakehouse ingest",
            job_id=job_entity.id,
            job_type=job_metadata.type,
            job_name=job_entity.name or job_metadata.name or job_metadata.type,
            parameters={"file_ids": ",".join(normalized_file_ids)},
            timeout_seconds=job_entity.timeout,
            job_description=job_metadata.description,
            priority=5,
        )

    async def _build_document_indexing_dispatch_plan(
        self,
        *,
        file_id: UUID | str | None = None,
        delete_file_id: UUID | str | None = None,
        triggered_by: TriggerActorModel | None,
    ) -> JobDispatchPlan | None:
        parameters: dict[str, str] = {}
        if file_id:
            parameters["file_id"] = str(file_id)
        if delete_file_id:
            parameters["delete_file_id"] = str(delete_file_id)
        if not parameters:
            return None

        job_service = JobService(project_id=self.project_id)
        job_entity = await job_service.ensure_job_exists_async(
            job_type=_DOCUMENT_INDEXING_JOB_TYPE,
            name=_DOCUMENT_INDEXING_JOB_NAME,
            description=_DOCUMENT_INDEXING_JOB_DESCRIPTION,
            timeout=300,
            created_by=format_trigger_actor(triggered_by),
        )
        if not job_entity or not job_entity.id:
            logger.warning("Could not find or create job definition for document indexing")
            return None

        target_file_id = file_id or delete_file_id
        action = "delete" if delete_file_id else "index"
        return JobDispatchPlan(
            step_key=f"document-{action}-{target_file_id}",
            step_name=("Document index removal" if delete_file_id else "Document indexing"),
            job_id=job_entity.id,
            job_type=_DOCUMENT_INDEXING_JOB_TYPE,
            job_name=job_entity.name or _DOCUMENT_INDEXING_JOB_NAME,
            parameters=parameters,
            timeout_seconds=job_entity.timeout,
            job_description=_DOCUMENT_INDEXING_JOB_DESCRIPTION,
            priority=5,
        )

    async def _build_lakehouse_cleanup_dispatch_plan(
        self,
        *,
        file_id: UUID | str,
        file_type: FileFormatType | str | None,
        triggered_by: TriggerActorModel | None,
    ) -> JobDispatchPlan | None:
        from .jobs import LakehouseCleanupJob

        job_metadata = LakehouseCleanupJob.get_job_metadata()
        job_service = JobService(project_id=self.project_id)
        job_entity = await job_service.ensure_job_exists_async(
            job_type=job_metadata.type,
            name=job_metadata.name or "Lakehouse Cleanup",
            description=job_metadata.description,
            timeout=300,
            created_by=format_trigger_actor(triggered_by),
        )
        if not job_entity or not job_entity.id:
            logger.warning("Could not find or create job definition for lakehouse cleanup")
            return None

        parameters = {
            "project_id": str(self.project_id),
            "file_id": str(file_id),
        }
        file_type_value = str(getattr(file_type, "value", file_type)) if file_type else None
        if file_type_value:
            parameters["file_type"] = file_type_value

        return JobDispatchPlan(
            step_key=f"lakehouse-cleanup-{file_id}",
            step_name="Lakehouse cleanup",
            job_id=job_entity.id,
            job_type=job_metadata.type,
            job_name=job_entity.name or job_metadata.name or job_metadata.type,
            parameters=parameters,
            timeout_seconds=job_entity.timeout,
            job_description=job_metadata.description,
            priority=5,
        )

    @staticmethod
    def _is_document_indexable_upload(
        *,
        filename: str | None,
        content_type: str | None,
        file_type: FileFormatType | str | None,
    ) -> bool:
        from kontext.catalog import is_indexable_document_upload

        return is_indexable_document_upload(
            filename=filename,
            content_type=content_type,
            file_type=file_type,
        )

    def get_file_processing_target(
        self,
        *,
        filename: str | None,
        prefix: str | None = None,
        content_type: str | None,
        file_type: FileFormatType | str | None,
    ) -> FileProcessingTarget:
        if is_system_managed_project_file_prefix(prefix):
            return "none"
        normalized_file_type = safe_enum_conversion(
            FileFormatType, file_type, FileFormatType.DEFAULT
        )
        if should_trigger_profiling_job(normalized_file_type):
            return "lakehouse"
        if self._is_document_indexable_upload(
            filename=filename,
            content_type=content_type,
            file_type=normalized_file_type,
        ):
            return "document"
        return "none"

    def build_file_processing_plan(
        self,
        *,
        file_id: UUID | str,
        new_filename: str | None,
        new_prefix: str | None = None,
        new_content_type: str | None,
        new_file_type: FileFormatType | str | None,
        old_filename: str | None = None,
        old_prefix: str | None = None,
        old_content_type: str | None = None,
        old_file_type: FileFormatType | str | None = None,
    ) -> FileProcessingPlan:
        old_target: FileProcessingTarget = "none"
        if old_filename is not None or old_content_type is not None or old_file_type is not None:
            old_target = self.get_file_processing_target(
                filename=old_filename,
                prefix=old_prefix,
                content_type=old_content_type,
                file_type=old_file_type,
            )

        new_target = self.get_file_processing_target(
            filename=new_filename,
            prefix=new_prefix,
            content_type=new_content_type,
            file_type=new_file_type,
        )
        return FileProcessingPlan(
            file_id=file_id,
            old_target=old_target,
            new_target=new_target,
            old_file_type=old_file_type,
            old_prefix=old_prefix,
            new_prefix=new_prefix,
        )

    async def apply_file_processing_plan(
        self,
        plan: FileProcessingPlan,
        *,
        triggered_by: TriggerActorModel | None,
    ) -> UUID | None:
        return await self.apply_file_processing_plans([plan], triggered_by=triggered_by)

    async def apply_file_processing_plans(
        self,
        plans: Sequence[FileProcessingPlan],
        *,
        triggered_by: TriggerActorModel | None,
        force_workflow: bool = False,
        workflow_key: str = "file_processing",
        workflow_name: str = "File Processing Workflow",
        workflow_description: str | None = None,
        workflow_parameters: dict[str, object] | None = None,
    ) -> UUID | None:
        dispatch_plans: list[JobDispatchPlan] = []
        lakehouse_ingest_ids: list[UUID | str] = []

        for plan in plans:
            if plan.old_target != plan.new_target:
                if plan.old_target == "lakehouse":
                    cleanup_plan = await self._build_lakehouse_cleanup_dispatch_plan(
                        file_id=plan.file_id,
                        file_type=plan.old_file_type,
                        triggered_by=triggered_by,
                    )
                    if cleanup_plan is not None:
                        dispatch_plans.append(cleanup_plan)
                elif plan.old_target == "document":
                    delete_plan = await self._build_document_indexing_dispatch_plan(
                        delete_file_id=plan.file_id,
                        triggered_by=triggered_by,
                    )
                    if delete_plan is not None:
                        dispatch_plans.append(delete_plan)

            if plan.new_target == "document":
                index_plan = await self._build_document_indexing_dispatch_plan(
                    file_id=plan.file_id,
                    triggered_by=triggered_by,
                )
                if index_plan is not None:
                    dispatch_plans.append(index_plan)
            elif plan.new_target == "lakehouse":
                lakehouse_ingest_ids.append(plan.file_id)

        ingest_plan = await self._build_lakehouse_ingest_dispatch_plan(
            file_ids=lakehouse_ingest_ids,
            triggered_by=triggered_by,
        )
        if ingest_plan is not None:
            dispatch_plans.append(ingest_plan)

        if not dispatch_plans and not force_workflow:
            return None

        if len(dispatch_plans) == 1 and not force_workflow:
            await self._dispatch_job_plan(
                dispatch_plans[0],
                triggered_by=triggered_by,
            )
            return None

        return await self._start_file_processing_workflow(
            dispatch_plans,
            triggered_by=triggered_by,
            workflow_key=workflow_key,
            workflow_name=workflow_name,
            workflow_description=workflow_description,
            workflow_parameters=workflow_parameters,
        )

    async def _start_file_processing_workflow(
        self,
        dispatch_plans: Sequence[JobDispatchPlan],
        *,
        triggered_by: TriggerActorModel | None,
        workflow_key: str = "file_processing",
        workflow_name: str = "File Processing Workflow",
        workflow_description: str | None = None,
        workflow_parameters: dict[str, object] | None = None,
    ) -> UUID:
        parameters = dict(workflow_parameters or {})
        parameters.setdefault("workflowKey", workflow_key)
        parameters.setdefault(
            "fileIds",
            sorted(
                {
                    file_id
                    for dispatch_plan in dispatch_plans
                    for file_id in self._extract_file_ids_from_dispatch_plan(dispatch_plan)
                }
            ),
        )
        parameters.setdefault(
            "stepKeys", [dispatch_plan.step_key for dispatch_plan in dispatch_plans]
        )
        workflow_request = WorkflowStartRequest(
            workflow_key=workflow_key,
            workflow_name=workflow_name,
            description=workflow_description
            or ("Coordinates file follow-up jobs such as cleanup, indexing, and lakehouse ingest."),
            triggered_by=triggered_by,
            trigger_type=JobTriggerType.EVENT,
            parameters=parameters,
            steps=[
                WorkflowJobStepDefinition(
                    key=dispatch_plan.step_key,
                    name=dispatch_plan.step_name,
                    job_id=str(dispatch_plan.job_id),
                    job_type=dispatch_plan.job_type,
                    job_name=dispatch_plan.job_name,
                    job_description=dispatch_plan.job_description,
                    timeout_seconds=dispatch_plan.timeout_seconds,
                    priority=dispatch_plan.priority,
                    parameters=dict(dispatch_plan.parameters),
                )
                for dispatch_plan in dispatch_plans
            ],
        )
        return await WorkflowOrchestrationService().start_workflow_async(
            project_id=self.project_uuid,
            workflow=workflow_request,
            queue_client=self._queue_client,
        )

    @staticmethod
    def _extract_file_ids_from_dispatch_plan(
        dispatch_plan: JobDispatchPlan,
    ) -> list[str]:
        file_ids: list[str] = []
        for key in ("file_id", "delete_file_id"):
            value = dispatch_plan.parameters.get(key)
            if value:
                file_ids.append(value)

        batched_file_ids = dispatch_plan.parameters.get("file_ids")
        if batched_file_ids:
            file_ids.extend(
                file_id.strip() for file_id in batched_file_ids.split(",") if file_id.strip()
            )

        return file_ids
