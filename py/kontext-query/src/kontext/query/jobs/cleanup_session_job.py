"""
Cleanup Session Job

Cleans up a DuckDB query session by deleting the session database file from disk.
"""

import logging

from pydantic import Field

from kontext.common.query.session_storage import delete_session_database_file
from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.jobs.permissions import JobRequiredPermissions
from kontext.schema import JobCategory

logger = logging.getLogger(__name__)


class CleanupSessionParams(BaseJobParams):
    """Parameters for cleaning up DuckDB query session resources."""

    session_id: str = Field(..., description="Session ID to clean up")
    project_id: str = Field(..., description="Project ID for the session")


@job(
    job_type="python.jobs.CleanupSessionJob",
    name="Cleanup Session",
    description="Cleans up a DuckDB query session by deleting database file",
    category=JobCategory.DATAPROCESSING,
    params_model=CleanupSessionParams,
    required_permissions=JobRequiredPermissions.SYSTEM_INTERNAL,
    display_parameter="session_id",
    is_system_job=True,
    icon="database-remove",
)
class CleanupSessionJob(BasePythonJob[CleanupSessionParams]):
    """Job for cleaning up DuckDB query session resources."""

    async def execute_job(self, context: JobContext, parameters: CleanupSessionParams) -> JobResult:
        """Execute session cleanup."""
        session_id = parameters.session_id
        project_id = parameters.project_id

        await context.log_info(
            f"Starting session cleanup for session {session_id}, project {project_id}",
            {
                "session_id": session_id,
                "project_id": project_id,
            },
        )

        try:
            deleted = delete_session_database_file(project_id, session_id)

            if deleted:
                await context.log_info(
                    f"Successfully deleted session database file for {session_id}"
                )
                await context.update_progress(100, f"Session {session_id} database file deleted")
                return JobResult.success_result(
                    message=f"Session {session_id} cleaned up successfully",
                    data={
                        "session_id": session_id,
                        "project_id": project_id,
                        "file_deleted": True,
                    },
                )

            await context.log_info(
                f"No database file to delete for session {session_id} "
                "(already deleted or in-memory session)"
            )
            await context.update_progress(
                100, f"Session {session_id} cleanup completed (no file to delete)"
            )
            return JobResult.success_result(
                message=f"Session {session_id} cleanup completed (no file found)",
                data={
                    "session_id": session_id,
                    "project_id": project_id,
                    "file_deleted": False,
                },
            )
        except Exception as e:
            error_msg = f"Failed to cleanup session {session_id}: {e!s}"
            await context.log_error(error_msg)
            logger.exception(error_msg)
            return JobResult.error_result(error_msg)
