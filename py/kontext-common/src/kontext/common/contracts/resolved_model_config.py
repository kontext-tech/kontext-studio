"""Resolved model bindings shared across the agent stack.

A resolved binding is the secret-free snapshot of a model *selection*: which
connection, adapter, canonical model, runtime model name, endpoint, and
reasoning default. It is resolved once by composition and passed down; it is
never a wire payload and never contains secret values.

It lives in the shared contract layer because chat, llm, agent, and harness
distributions all carry the same persisted snapshot. Keeping it in
``kontext-llm`` would force the framework-neutral contract layer to depend on
the model-resolution service just to name a type.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from kontext.schema import ModelReasoningEffort


class ResolvedModelConfig(BaseModel):
    """Secret-safe runtime configuration resolved from a model selection.

    Provider config and credential references are flattened into scalar fields:
    the nested ``provider_config`` / ``credential_refs`` objects add nothing once
    resolved and are not read by any consumer.
    """

    # ``None`` for the app-default binding, which is not a persisted selection.
    selection_id: str | None = Field(default=None)
    canonical_model_id: str = Field(...)
    source_type: str = Field(...)
    adapter_type: str = Field(...)
    connection_kind: str = Field(...)
    display_name: str = Field(...)
    provider_model_name: str | None = Field(default=None)
    endpoint_base_url: str | None = Field(default=None)
    secret_ref: str | None = Field(default=None)
    region: str | None = Field(default=None)
    project_id: str | None = Field(default=None)
    location: str | None = Field(default=None)
    api_version: str | None = Field(default=None)
    reasoning_effort: ModelReasoningEffort | None = Field(default=None)

    # `ignore` so persisted snapshots written before fields were flattened still
    # validate when read back from storage.
    model_config = ConfigDict(extra="ignore")


__all__ = ["ResolvedModelConfig"]
