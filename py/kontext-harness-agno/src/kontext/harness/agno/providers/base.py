"""Shared types and helpers for harness-native provider factories.

Each provider factory is a small function that turns a neutral
:class:`ModelRequest` into a concrete Agno model. Factories never read the
selection store themselves; resolution is done once in
``kontext.llm.provider_resolution`` (which stays harness-neutral) and passed in.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kontext.common.contracts import ResolvedModelConfig
from kontext.llm.provider_resolution import (
    normalize_reasoning_kwargs,
    resolve_api_key,
    resolve_base_url,
)
from kontext.schema import ModelReasoningEffort


@dataclass(frozen=True)
class ModelRequest:
    """Neutral inputs a provider factory needs to build a native model."""

    provider: str
    model_id: str
    resolved_config: ResolvedModelConfig
    max_tokens: int | None = None
    reasoning_effort: ModelReasoningEffort | None = None
    credentials: dict[str, str] = field(default_factory=dict)

    def base_url(self) -> str | None:
        return resolve_base_url(self.provider, self.resolved_config)

    def api_key(self) -> str | None:
        return resolve_api_key(self.provider, self.credentials)

    def reasoning_kwargs(self) -> dict[str, Any]:
        return normalize_reasoning_kwargs(self.provider, self.reasoning_effort)

    def token_kwarg(self, name: str = "max_tokens") -> dict[str, Any]:
        return {name: self.max_tokens} if self.max_tokens is not None else {}


ModelFactory = Callable[[ModelRequest], Any]
