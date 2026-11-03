"""Storage provider factory."""

import logging
import os

from .config import StorageConfig, StorageProvider
from .providers.base import BaseStorageProvider

logger = logging.getLogger("storage.factory")

_storage_provider: BaseStorageProvider | None = None


def get_storage_config() -> StorageConfig:
    """Build storage configuration from environment variables."""
    provider_str = os.environ.get("STORAGE_PROVIDER", "local").lower()

    try:
        provider = StorageProvider(provider_str)
    except ValueError:
        logger.warning("Unknown storage provider '%s', falling back to local", provider_str)
        provider = StorageProvider.LOCAL

    return StorageConfig(
        provider=provider,
        file_storage_path=os.environ.get("FILE_STORAGE_PATH"),
        local_base_path=os.environ.get("KONTEXT_LOCAL_STORAGE_PATH"),
    )


def get_storage_provider(
    config: StorageConfig | None = None, force_new: bool = False
) -> BaseStorageProvider:
    """Get a storage provider instance."""
    global _storage_provider

    if _storage_provider is not None and not force_new and config is None:
        return _storage_provider

    if config is None:
        config = get_storage_config()

    logger.info("Creating storage provider: %s", config.provider)

    if config.provider == StorageProvider.LOCAL:
        from kontext.storage.providers.local import LocalFilesystemProvider

        provider = LocalFilesystemProvider(config)
    else:
        raise ValueError(f"Unsupported storage provider: {config.provider}")

    if not force_new:
        _storage_provider = provider

    return provider


def clear_storage_provider_cache() -> None:
    """Clear the cached storage provider instance."""
    global _storage_provider
    _storage_provider = None
