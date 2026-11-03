"""
Job business service for Kontext

This service encapsulates job-related business logic including:
- Ensuring jobs exist by type (creating on-demand)
- Job orchestration and workflow management

The service uses data services for database access and provides a clean
interface for both API endpoints and internal components.
"""

import logging
from uuid import UUID

from kontext.common.project_scoped import ProjectScopedService
from kontext.data import Job, JobDataService
from kontext.schema import CreateJobRequest, JobRetryStrategy

logger = logging.getLogger(__name__)


class JobService(ProjectScopedService):
    """
    Business service for job operations.

    This service provides high-level job business logic that orchestrates
    data services and implements business rules.
    """

    def __init__(self, *, project_id: UUID | str) -> None:
        """
        Initialize the job service.

        Args:
            project_id: Project ID for job operations.
        """
        super().__init__(project_id)
        self._data_service = JobDataService(project_id=project_id)

    async def ensure_job_exists_async(
        self,
        job_type: str,
        name: str,
        description: str | None = None,
        timeout: int = 300,
        retry_strategy: str = "None",
        retry_limit: int = 3,
        owner_id: UUID | None = None,
        created_by: str | None = None,
    ) -> Job | None:
        """
        Ensure a job of the given type exists, creating if needed.

        This is useful for event-driven jobs that need to be created on-demand.

        Args:
            job_type: Fully qualified job type.
            name: Job display name.
            description: Optional job description.
            timeout: Execution timeout in seconds.
            retry_strategy: Retry strategy enum value.
            retry_limit: Maximum retry attempts.
            owner_id: Optional owner user ID.
            created_by: Optional creator identifier.

        Returns:
            Existing or newly created Job entity, or None if creation fails.
        """
        # Check if job already exists (returns view model)
        existing_vm = await self._data_service.get_job_by_type_async(job_type)
        if existing_vm and existing_vm.id:
            # Get the actual entity
            return await self._data_service._get_job_entity_async(UUID(existing_vm.id))

        # Parse retry strategy
        parsed_retry_strategy: JobRetryStrategy = JobRetryStrategy.NONE
        if retry_strategy:
            try:
                parsed_retry_strategy = JobRetryStrategy(retry_strategy)
            except ValueError:
                parsed_retry_strategy = JobRetryStrategy.NONE

        # Create new job using CreateJobRequest
        request = CreateJobRequest(
            name=name,
            type=job_type,
            description=description,
            timeout=timeout,
            retry_strategy=parsed_retry_strategy,
            retry_limit=retry_limit,
        )

        job_vm = await self._data_service.create_job_async(
            request, owner_id=owner_id, created_by=created_by
        )

        # Return the entity if needed
        if job_vm and job_vm.id:
            return await self._data_service._get_job_entity_async(UUID(job_vm.id))

        return None
