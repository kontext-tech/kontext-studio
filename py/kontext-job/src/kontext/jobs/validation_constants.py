"""
Shared validation constants for job types and parameters
These constants match the C# JobValidationConstants to ensure consistency
"""

import re


class JobValidationConstants:
    """Shared validation constants for job types and parameters"""

    # Regular expression patterns (as compiled regex objects for better performance)
    JOB_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_\.]+$")
    JOB_TYPE_PATTERN = re.compile(r"^[a-zA-Z0-9\.\-_]+$")
    PARAMETER_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    # Maximum lengths
    MAX_JOB_NAME_LENGTH = 255
    MAX_JOB_TYPE_LENGTH = 500
    MAX_JOB_DESCRIPTION_LENGTH = 4000
    MAX_JOB_CATEGORY_LENGTH = 100
    MAX_PARAMETER_NAME_LENGTH = 100
    MAX_PARAMETER_DESCRIPTION_LENGTH = 1000
    # Upper bound for any string job parameter. This must be >= the largest
    # legitimate string parameter (the Python `code` parameter, whose schema
    # allows 10000 characters — see kontext-common MAX_PYTHON_CODE_CHARS),
    # otherwise the job fails registry validation instead of executing.
    MAX_STRING_PARAMETER_LENGTH = 10_000

    # Job timeout limits (in seconds)
    MIN_JOB_TIMEOUT_SECONDS = 60  # 1 minute
    MAX_JOB_TIMEOUT_SECONDS = 86400  # 24 hours

    # Retry limits
    MIN_RETRY_LIMIT = 0
    MAX_RETRY_LIMIT = 10


# Legacy pattern strings for compatibility
JOB_NAME_PATTERN = r"^[a-zA-Z0-9\s\-_\.]+$"
JOB_TYPE_PATTERN = r"^[a-zA-Z0-9\.\-_]+$"
PARAMETER_NAME_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
