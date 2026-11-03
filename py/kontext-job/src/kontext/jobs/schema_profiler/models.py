"""
Data models for schema profiling - using generated API client models
"""

from uuid import UUID

from pydantic import BaseModel

from kontext.schema import FileFormatType, FileSchemaModel, FileStatsModel


class SchemaProfilingResult(BaseModel):
    """Result of schema profiling operation"""

    success: bool
    file_schema: FileSchemaModel | None = None
    file_stats: FileStatsModel | None = None
    error_message: str | None = None
    warnings: list[str] = []

    @classmethod
    def success_result(
        cls, file_schema: FileSchemaModel, file_stats: FileStatsModel
    ) -> "SchemaProfilingResult":
        return cls(success=True, file_schema=file_schema, file_stats=file_stats)

    @classmethod
    def failure_result(
        cls, error_message: str, warnings: list[str] | None = None
    ) -> "SchemaProfilingResult":
        return cls(
            success=False,
            file_schema=None,
            file_stats=None,
            error_message=error_message,
            warnings=warnings or [],
        )


class SchemaProfilingError(Exception):
    """Exception raised during schema profiling"""

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        original_error: Exception | None = None,
    ):
        self.message = message
        self.file_path = file_path
        self.original_error = original_error
        super().__init__(message)

    def __str__(self) -> str:
        if self.file_path:
            return f"Schema detection error for {self.file_path}: {self.message}"
        return f"Schema detection error: {self.message}"


class ProfilerParameters(BaseModel):
    """Parameters for initializing a schema profiler"""

    uri: str  # was file_path
    file_type: FileFormatType
    file_name: str | None = None
    file_size_bytes: int | None = None
    project_id: UUID  # Now mandatory
