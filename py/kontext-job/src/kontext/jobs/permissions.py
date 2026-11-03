"""
Job-specific permission constants and common permission sets.

These are used in job definitions to specify required permissions.
All values are lists of permission claim strings.
"""

from kontext.auth import (
    FilePermissions,
    JobPermissions,
    ProjectPermissions,
    QuerySessionPermissions,
)


class JobRequiredPermissions:
    """Pre-defined permission sets for common job patterns.

    Each permission set is a list of permission claim strings that a user
    must have to execute the corresponding job type.

    System jobs (is_system_job=True) typically use SYSTEM_INTERNAL which
    is an empty list, as they bypass normal permission checks.
    """

    # Basic job execution - for simple jobs that don't access resources
    EXECUTE_ONLY: list[str] = [JobPermissions.EXECUTE]

    # File read operations
    FILE_READ: list[str] = [JobPermissions.EXECUTE, FilePermissions.READ]

    # File write operations (includes read)
    FILE_WRITE: list[str] = [
        JobPermissions.EXECUTE,
        FilePermissions.READ,
        FilePermissions.UPDATE,
    ]

    # Query execution in sessions
    QUERY_EXECUTE: list[str] = [
        JobPermissions.EXECUTE,
        QuerySessionPermissions.EXECUTE,
    ]

    # Session management (create, update, delete)
    SESSION_MANAGE: list[str] = [
        JobPermissions.EXECUTE,
        QuerySessionPermissions.CREATE,
        QuerySessionPermissions.UPDATE,
        QuerySessionPermissions.DELETE,
    ]

    # Catalog management
    CATALOG_MANAGE: list[str] = [
        JobPermissions.EXECUTE,
        ProjectPermissions.UPDATE,
    ]

    # System/internal jobs - bypass permission checks
    # System jobs are triggered by platform events, not user actions
    SYSTEM_INTERNAL: list[str] = []
