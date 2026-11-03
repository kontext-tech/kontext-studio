from __future__ import annotations

import pytest

from kontext.catalog.indexing.embedding import (
    FastEmbedEmbedding,
    LocalHashEmbedding,
    _build_default_embedding_provider,
)


def test_default_embedding_provider_uses_fastembed_by_default() -> None:
    _build_default_embedding_provider.cache_clear()
    provider = _build_default_embedding_provider(
        "fastembed",
        "BAAI/bge-small-en-v1.5",
        None,
    )

    assert isinstance(provider, FastEmbedEmbedding)


def test_default_embedding_provider_supports_explicit_hash_fallback() -> None:
    _build_default_embedding_provider.cache_clear()
    provider = _build_default_embedding_provider(
        "hash",
        "BAAI/bge-small-en-v1.5",
        None,
    )

    assert isinstance(provider, LocalHashEmbedding)


def test_fastembed_to_vector_rejects_non_iterables() -> None:
    provider = FastEmbedEmbedding()

    with pytest.raises(TypeError, match="non-iterable embedding vector"):
        provider._to_vector(object())
