"""Embedding helpers for the catalog and knowledge index."""

from __future__ import annotations

import hashlib
import itertools
import logging
import math
import os
import re
from collections import Counter
from collections.abc import Iterable
from functools import lru_cache
from typing import Protocol, runtime_checkable

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_DEFAULT_EMBEDDING_PROVIDER = "fastembed"
_DEFAULT_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"

logger = logging.getLogger(__name__)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for text → embedding vector providers."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        ...


class FastEmbedEmbedding:
    """Local ONNX-backed semantic embeddings via ``fastembed``."""

    def __init__(
        self,
        *,
        model_name: str = _DEFAULT_FASTEMBED_MODEL,
        cache_dir: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir or os.getenv("KONTEXT_FASTEMBED_CACHE_DIR")
        self._model = None
        self._fallback: LocalHashEmbedding | None = None

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=self.cache_dir,
                lazy_load=True,
            )
        return self._model

    def _to_vector(self, raw_vector: object) -> list[float]:
        values = getattr(raw_vector, "tolist", None)
        normalized = values() if callable(values) else raw_vector
        if isinstance(normalized, str | bytes) or not isinstance(normalized, Iterable):
            raise TypeError(
                "fastembed returned a non-iterable embedding vector "
                f"of type {type(normalized).__name__}"
            )
        return [float(value) for value in normalized]

    def _fallback_provider(self, exc: Exception) -> LocalHashEmbedding:
        if self._fallback is None:
            logger.warning(
                "Falling back to LocalHashEmbedding because fastembed semantic "
                "embeddings are unavailable: %s",
                exc,
            )
            self._fallback = LocalHashEmbedding()
        return self._fallback

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return [self._to_vector(vector) for vector in self._get_model().passage_embed(texts)]
        except Exception as exc:  # pragma: no cover - optional dependency/runtime path
            return self._fallback_provider(exc).embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        try:
            vectors = [
                self._to_vector(vector) for vector in self._get_model().query_embed(text or "")
            ]
            return vectors[0] if vectors else []
        except Exception as exc:  # pragma: no cover - optional dependency/runtime path
            return self._fallback_provider(exc).embed_query(text)


class LocalHashEmbedding:
    """Small dependency-free embedding model for local hybrid search.

    This is intentionally simple and deterministic. It gives us a stable
    dense-search primitive without requiring remote APIs or heavyweight model
    downloads, while keeping the embedding provider swappable behind the same
    interface.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def _tokenize(self, text: str) -> list[str]:
        normalized = text.lower().replace("_", " ").replace("-", " ")
        words = _TOKEN_PATTERN.findall(normalized)
        tokens: list[str] = []
        for word in words:
            tokens.append(word)
            if len(word) > 3 and word.endswith("s"):
                tokens.append(word[:-1])
            if len(word) > 4:
                tokens.extend(word[index : index + 3] for index in range(len(word) - 2))
        tokens.extend(f"{left}_{right}" for left, right in itertools.pairwise(words))
        return tokens or ["__empty__"]

    def _bucket(self, token: str, salt: str) -> int:
        digest = hashlib.blake2b(
            f"{salt}:{token}".encode(),
            digest_size=8,
        ).digest()
        return int.from_bytes(digest, "big") % self.dimensions

    def _sign(self, token: str) -> float:
        return 1.0 if self._bucket(token, "sign") % 2 == 0 else -1.0

    def _embed_text(self, text: str) -> list[float]:
        counts = Counter(self._tokenize(text))
        vector = [0.0] * self.dimensions
        for token, count in counts.items():
            bucket = self._bucket(token, "bucket")
            vector[bucket] += self._sign(token) * (1.0 + math.log1p(count))
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0:
            return vector
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache(maxsize=8)
def _build_default_embedding_provider(
    provider_name: str,
    model_name: str,
    cache_dir: str | None,
) -> EmbeddingProvider:
    normalized_provider = provider_name.strip().lower()
    if normalized_provider in {"hash", "local_hash"}:
        logger.warning(
            "Using LocalHashEmbedding because KONTEXT_EMBEDDING_PROVIDER=%s. "
            "Semantic retrieval quality will be degraded.",
            provider_name,
        )
        return LocalHashEmbedding()

    if normalized_provider not in {"fastembed", _DEFAULT_EMBEDDING_PROVIDER}:
        logger.warning(
            "Unknown embedding provider %s; falling back to LocalHashEmbedding. "
            "Semantic retrieval quality will be degraded.",
            provider_name,
        )
        return LocalHashEmbedding()

    try:
        return FastEmbedEmbedding(model_name=model_name, cache_dir=cache_dir)
    except Exception as exc:  # pragma: no cover - optional dependency/runtime path
        logger.warning(
            "Falling back to LocalHashEmbedding because the semantic embedding "
            "provider could not be initialized: %s",
            exc,
        )
        return LocalHashEmbedding()


def get_default_embedding_provider() -> EmbeddingProvider:
    """Resolve the default embedding provider for runtime use."""

    provider_name = os.getenv(
        "KONTEXT_EMBEDDING_PROVIDER",
        _DEFAULT_EMBEDDING_PROVIDER,
    )
    model_name = os.getenv(
        "KONTEXT_EMBEDDING_MODEL",
        _DEFAULT_FASTEMBED_MODEL,
    )
    cache_dir = os.getenv("KONTEXT_FASTEMBED_CACHE_DIR")
    return _build_default_embedding_provider(provider_name, model_name, cache_dir)
