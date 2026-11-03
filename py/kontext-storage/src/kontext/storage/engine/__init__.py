"""
Lake storage engine interfaces for JSON-backed collections.
"""

from __future__ import annotations

import abc
from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .local import LocalStorageEngine


class StorageEngine(abc.ABC):
    """Abstract base class for lake storage engines."""

    @abc.abstractmethod
    def get(self, collection: str, record_id: str, *, project_id: str) -> dict[str, Any] | None: ...

    @abc.abstractmethod
    def list(
        self,
        collection: str,
        *,
        project_id: str,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]: ...

    @abc.abstractmethod
    def count(
        self, collection: str, *, project_id: str, filters: dict[str, Any] | None = None
    ) -> int: ...

    @abc.abstractmethod
    def create(
        self, collection: str, data: dict[str, Any], *, project_id: str
    ) -> dict[str, Any]: ...

    @abc.abstractmethod
    def update(
        self, collection: str, record_id: str, data: dict[str, Any], *, project_id: str
    ) -> dict[str, Any]: ...

    @abc.abstractmethod
    def delete(self, collection: str, record_id: str, *, project_id: str) -> bool: ...

    @abc.abstractmethod
    def query(
        self, collection: str, *, project_id: str, predicate: Any | None = None
    ) -> list[dict[str, Any]]: ...

    @abc.abstractmethod
    def get_global(self, name: str) -> dict[str, Any] | list[Any] | None: ...

    @abc.abstractmethod
    def put_global(self, name: str, data: dict[str, Any] | list[Any]) -> None: ...

    @abc.abstractmethod
    def ensure_project_structure(self, project_id: str) -> None: ...

    @abc.abstractmethod
    def project_exists(self, project_id: str) -> bool: ...

    @abc.abstractmethod
    def get_project_data_path(self, project_id: str, subdir: str = "") -> str: ...


def __getattr__(name: str):
    if name != "LocalStorageEngine":
        raise AttributeError(f"module 'kontext.storage.engine' has no attribute {name!r}")
    module = import_module("kontext.storage.engine.local")
    return getattr(module, name)


__all__ = ["LocalStorageEngine", "StorageEngine"]
