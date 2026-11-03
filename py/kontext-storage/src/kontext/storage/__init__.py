"""
Unified storage module for Kontext.

This package provides storage configuration, provider factories, and local
lake-storage primitives shared across API, console, embedded runtime, and jobs.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import FileSize, StorageConfig, StorageProvider
    from .factory import (
        clear_storage_provider_cache,
        get_storage_config,
        get_storage_provider,
    )
    from .providers.base import BaseStorageProvider, StorageResult

_EXPORTS = {
    "FileSize": "kontext.storage.config",
    "StorageConfig": "kontext.storage.config",
    "StorageProvider": "kontext.storage.config",
    "get_storage_provider": "kontext.storage.factory",
    "get_storage_config": "kontext.storage.factory",
    "clear_storage_provider_cache": "kontext.storage.factory",
    "BaseStorageProvider": "kontext.storage.providers.base",
    "StorageResult": "kontext.storage.providers.base",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'kontext.storage' has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)


__all__ = [
    "BaseStorageProvider",
    "FileSize",
    "StorageConfig",
    "StorageProvider",
    "StorageResult",
    "clear_storage_provider_cache",
    "get_storage_config",
    "get_storage_provider",
]
