"""
Storage configuration models and enums.

This module defines the configuration models for storage providers,
including support for local filesystem storage.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class StorageProvider(StrEnum):
    """Supported storage providers."""

    LOCAL = "local"


class StorageConfig(BaseModel):
    """
    Configuration for storage providers.

    This model holds all configuration needed for local filesystem storage.
    """

    provider: StorageProvider = Field(
        default=StorageProvider.LOCAL, description="Storage provider type"
    )

    file_storage_path: str | None = Field(
        default=None,
        description=("Path for local file storage (e.g., SQLite/DuckDB files, local secrets)"),
    )

    local_base_path: str | None = Field(
        default=None,
        description=(
            "Root directory for LOCAL storage provider. "
            "Defaults to KONTEXT_LOCAL_STORAGE_PATH env-var or ~/.kontext/storage."
        ),
    )

    def get_storage_uri_prefix(self) -> str:
        """Get the URI prefix for the local storage provider."""
        import os

        base = self.local_base_path or os.path.expanduser("~/.kontext/storage")
        return f"file://{base}"


FileSize = Annotated[int, Field(ge=0, description="File size in bytes")]
