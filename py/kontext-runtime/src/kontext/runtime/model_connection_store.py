"""Model-resolution composition for the local profile.

Wires the ``kontext-llm`` model-resolution seam
(:mod:`kontext.llm.model_connection_store`) to the SQLite-backed model-connection
store in ``kontext-account``. Keeping this in ``kontext-runtime`` means
``kontext-llm`` itself imports neither ``kontext-account`` nor
``kontext-runtime``.

Kontext is local-first; a hosted platform would register a different
``ModelConnectionStore`` implementation here at bootstrap.
"""

from __future__ import annotations

import logging

from kontext.schema import ModelConnection

logger = logging.getLogger(__name__)


class LocalModelConnectionStore:
    """Read-only model-connection store backed by ``kontext-account`` (SQLite)."""

    def get_model_connection(self, connection_id: str) -> ModelConnection | None:
        from kontext.account import get_model_connection

        return get_model_connection(connection_id)

    def resolve_model_connection_credentials(self, connection_id: str) -> dict[str, str]:
        from kontext.account import resolve_model_connection_credentials

        return resolve_model_connection_credentials(connection_id)


def configure_model_resolution() -> None:
    """Register the local model-connection store."""
    from kontext.llm import register_local_model_store

    register_local_model_store(LocalModelConnectionStore())
    logger.debug("Registered local model-connection store.")
