"""
Tests for DuckDB Storage Manager.

Tests the DuckDBStorageManager class which handles local storage path resolution.
"""

from kontext.engine.storage.duckdb_storage import DuckDBStorageManager
from kontext.storage import StorageConfig, StorageProvider


class TestDuckDBStorageManagerExtensions:
    """Tests for DuckDB extension mapping."""

    def test_get_extension_name_local(self):
        """LOCAL provider should return None (no extension needed)."""
        config = StorageConfig(provider=StorageProvider.LOCAL)
        manager = DuckDBStorageManager(config)
        assert manager.get_extension_name() is None

    def test_setup_extension_is_a_no_op_for_local_provider(self):
        """LOCAL provider should not raise when extension setup is requested."""
        config = StorageConfig(provider=StorageProvider.LOCAL)
        manager = DuckDBStorageManager(config)

        manager.setup_extension(None)  # type: ignore[arg-type]


class TestDuckDBStorageManagerStorageUri:
    """Tests for storage URI generation."""

    def test_get_storage_uri_absolute_path_passthrough(self):
        """Absolute local paths should be returned as-is."""
        config = StorageConfig(provider=StorageProvider.LOCAL)
        manager = DuckDBStorageManager(config)
        uri = manager.get_storage_uri("project-123", "/data/file.parquet")
        assert uri == "/data/file.parquet"

    def test_get_storage_uri_relative_path_with_base(self):
        """Relative paths should be resolved against local_base_path."""
        config = StorageConfig(provider=StorageProvider.LOCAL, local_base_path="/tmp/storage")
        manager = DuckDBStorageManager(config)
        uri = manager.get_storage_uri("project-123", "data/file.parquet")
        assert uri == "/tmp/storage/data/file.parquet"


class TestDuckDBStorageManagerDropSecret:
    """Tests for secret management with local provider."""

    def test_create_secret_returns_empty_string(self):
        """LOCAL provider should not create DuckDB secrets."""
        config = StorageConfig(provider=StorageProvider.LOCAL)
        manager = DuckDBStorageManager(config)
        assert manager.create_secret(None, "project-123") == ""  # type: ignore[arg-type]

    def test_drop_secret_returns_false(self):
        """LOCAL provider drop_secret should return False (no secrets exist)."""
        config = StorageConfig(provider=StorageProvider.LOCAL)
        manager = DuckDBStorageManager(config)
        assert manager.drop_secret(None, "any_secret") is False  # type: ignore[arg-type]
