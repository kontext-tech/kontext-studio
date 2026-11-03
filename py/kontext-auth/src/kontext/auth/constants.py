"""Auth-related constants shared across Kontext Python services."""


class SystemRoles:
    """System-wide roles for the Kontext."""

    ADMINISTRATOR = "Administrator"
    DATA_LAKE_OPERATOR = "Data Lake Operator"
    PYTHON_JOB_EXECUTOR = "Python Job Executor"
    READONLY_ADMIN = "Readonly Admin"
    RESOURCE_PROFILER = "Resource Profiler"
    SUB___CAMPAIGN_ADMINISTRATOR = "Sub & Campaign Administrator"
    USER = "User"


class JwtConstants:
    """JWT claim names and versioning.

    Keep these consistent with the .NET backend.
    """

    VERSION_CLAIM_TYPE = "jwt_ver"
    CURRENT_VERSION = 2
