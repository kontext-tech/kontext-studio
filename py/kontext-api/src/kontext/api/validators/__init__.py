"""
Validation utilities and constants for FastAPI routers.

This module provides shared validation patterns, constants, and utilities
for validating request data across the API.
"""

# Models without business logic validation - imported directly from kontext.schema
from kontext.schema import (
    BulkFileIdsRequest,
    CreateFileRequest,
    FileUploadMetadata,
    UpdateFileRequest,
    UpdateFileSchemaRequest,
)

from .constants import PART_NAME_PATTERN, SQL_IDENTIFIER_PATTERN

__all__ = [
    "PART_NAME_PATTERN",
    # Constants
    "SQL_IDENTIFIER_PATTERN",
    "BulkFileIdsRequest",
    # File validators
    "CreateFileRequest",
    "FileUploadMetadata",
    "UpdateFileRequest",
    "UpdateFileSchemaRequest",
]
