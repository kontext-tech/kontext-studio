"""Base storage provider interface."""

import logging
import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

from kontext.common.utils.file_storage import normalize_project_file_prefix

from ..config import StorageConfig


@dataclass
class StorageResult:
    """Result of a storage operation."""

    path: str
    uri: str
    size: int = 0


class BaseStorageProvider(ABC):
    """Abstract base class for storage providers."""

    def __init__(self, config: StorageConfig):
        self.config = config
        self.logger = logging.getLogger(f"storage.{self.__class__.__name__}")

    @abstractmethod
    async def upload_file(
        self,
        project_id: str,
        filename: str,
        content: BinaryIO | bytes,
        prefix: str | None = None,
        content_type: str | None = None,
    ) -> StorageResult:
        pass

    @abstractmethod
    async def download_file(self, path: str) -> BytesIO:
        pass

    @abstractmethod
    async def download_range(self, path: str, offset: int, length: int) -> BytesIO:
        pass

    @abstractmethod
    async def delete_file(self, path: str) -> bool:
        pass

    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        pass

    @abstractmethod
    def resolve_path(self, path: str) -> pathlib.Path:
        pass

    @abstractmethod
    async def get_file_size(self, path: str) -> int | None:
        pass

    async def list_files(self, *, project_id: str, prefix: str | None = None) -> list[str]:
        """List stored relative paths under a project's resources/<prefix> dir.

        Optional capability: providers that cannot enumerate (e.g. a cloud
        object store without a list API) return an empty list, and callers that
        depend on enumeration must treat that as "unknown", not "empty".
        """
        return []

    def get_storage_uri(self, project_id: str, filename: str, prefix: str | None = None) -> str:
        uri_prefix = self.config.get_storage_uri_prefix()
        relative_path = self.get_relative_path(
            project_id=project_id,
            filename=filename,
            prefix=prefix,
        )
        return f"{uri_prefix}/{relative_path}"

    def get_relative_path(self, project_id: str, filename: str, prefix: str | None = None) -> str:
        normalized_prefix = normalize_project_file_prefix(prefix)
        resource_path = f"resources/{filename}"
        if normalized_prefix:
            resource_path = f"resources/{normalized_prefix}/{filename}"
        return f"projects/{project_id}/{resource_path}"
