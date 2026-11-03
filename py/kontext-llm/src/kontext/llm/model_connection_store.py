"""Model-connection store seam.

``kontext-llm`` resolves a model *selection* to a secret-safe runtime snapshot,
but it must not depend on the layer that stores that selection. The local
model-connection store lives in ``kontext-account`` / SQLite; composition
(``kontext-runtime``) registers it at bootstrap.

This module defines the port and a small process-wide registry so ``kontext-llm``
depends only on the protocol — keeping it free of ``kontext-account``,
``kontext-runtime`` (and any platform/client) imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from kontext.schema import ModelConnection


@runtime_checkable
class ModelConnectionStore(Protocol):
    """Read-only access to locally stored model connections."""

    def get_model_connection(self, connection_id: str) -> ModelConnection | None: ...

    def resolve_model_connection_credentials(self, connection_id: str) -> dict[str, str]: ...


_local_store: ModelConnectionStore | None = None


def register_local_model_store(store: ModelConnectionStore) -> None:
    """Register the local model-connection store (called by composition)."""
    global _local_store
    _local_store = store


def get_local_model_store() -> ModelConnectionStore | None:
    """Return the registered local model-connection store, if any."""
    return _local_store


def reset_model_resolution_hooks() -> None:
    """Clear the registered store (mainly useful in tests)."""
    global _local_store
    _local_store = None
