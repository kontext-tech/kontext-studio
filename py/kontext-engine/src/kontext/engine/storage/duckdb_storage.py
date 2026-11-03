"""
DuckDB Storage Manager for local storage access.

This module provides utilities for DuckDB storage configuration.
With only local storage supported, no cloud extensions or secrets are needed.
"""

import logging
import pathlib
from typing import TYPE_CHECKING

from kontext.storage.config import StorageConfig

if TYPE_CHECKING:
    import duckdb


class DuckDBStorageManager:
    """
    Manager for DuckDB storage configuration.

    With only local storage supported, this manager handles local path
    resolution for DuckDB external tables. No cloud extensions or secrets
    are configured.
    """

    def __init__(self, config: StorageConfig):
        """
        Initialize the DuckDB storage manager.

        Args:
            config: Storage configuration
        """
        self.config = config
        self.logger = logging.getLogger("storage.duckdb")

    def get_extension_name(self) -> str | None:
        """
        Get the DuckDB extension name for the configured provider.

        Returns:
            None (local storage requires no extension)
        """
        return None

    def setup_extension(
        self,
        connection: "duckdb.DuckDBPyConnection",
        extensions_path: str | None = None,
    ) -> None:
        """
        Install and load the appropriate DuckDB extension for the storage provider.
        """
        self.logger.debug(
            "No DuckDB extension required for provider: %s",
            self.config.provider,
        )

    def create_secret(
        self,
        connection: "duckdb.DuckDBPyConnection",
        project_id: str,
        secret_name: str | None = None,
    ) -> str:
        """
        Create a DuckDB secret for accessing storage.
        """
        self.logger.debug(
            "No DuckDB secret required for provider: %s",
            self.config.provider,
        )
        return ""

    def create_container_secret(
        self,
        connection: "duckdb.DuckDBPyConnection",
        container_or_bucket: str | None = None,
        project_id: str | None = None,
        secret_name: str | None = None,
    ) -> str:
        """
        Create a DuckDB secret for accessing storage with container/bucket scope.
        """
        self.logger.debug(
            "No DuckDB container secret required for provider: %s",
            self.config.provider,
        )
        return ""

    def drop_secret(self, connection: "duckdb.DuckDBPyConnection", secret_name: str) -> bool:
        """
        Drop a DuckDB secret.

        Returns:
            False (no secrets exist for local storage)
        """
        return False

    def get_storage_uri(self, project_id: str, resource_uri: str) -> str:
        """
        Build full storage URI for DuckDB external tables.

        Args:
            project_id: Project ID
            resource_uri: Resource URI - can be a relative path or a full URI

        Returns:
            Full URI suitable for DuckDB (absolute path for local storage)
        """
        # If it's already an absolute path, return as-is
        if resource_uri.startswith("/") or (len(resource_uri) > 1 and resource_uri[1] == ":"):
            return resource_uri

        # Build local path from config
        import os

        base = (
            self.config.local_base_path
            or os.environ.get("KONTEXT_LOCAL_STORAGE_PATH")
            or os.path.expanduser("~/.kontext/storage")
        )
        return str(pathlib.Path(base) / resource_uri)


# Backwards compatibility alias
DuckDBSecretManager = DuckDBStorageManager
