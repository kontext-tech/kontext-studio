"""Resolved model runtime: the binding plus the credentials for one run.

Composition resolves this once (selection -> binding -> credentials) and passes
it through the harness context. Adapters therefore never reach into the
process-global model-connection store to build a model client.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .resolved_model_config import ResolvedModelConfig


@dataclass(frozen=True)
class ModelRuntime:
    """A resolved binding and its secret values for the current run.

    Credentials stay in memory and are never persisted or logged. ``repr`` is
    redacted so a stray log line cannot leak provider secrets.
    """

    binding: ResolvedModelConfig
    credentials: Mapping[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"ModelRuntime(binding={self.binding!r}, credentials=<redacted>)"


__all__ = ["ModelRuntime"]
