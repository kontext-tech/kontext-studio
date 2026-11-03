"""Tests for the composition-side model runtime resolution."""

from __future__ import annotations

import pytest

from kontext.agentic import model_runtime
from kontext.common.contracts import ResolvedModelConfig


def test_default_binding_uses_the_configured_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "openai")

    binding = model_runtime.default_model_binding()

    assert binding.selection_id is None
    assert binding.connection_kind == "openai"
    assert binding.source_type == "app_default"
    assert binding.provider_model_name


def test_build_model_runtime_resolves_credentials_for_a_persisted_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = ResolvedModelConfig(
        selection_id="selection-1",
        canonical_model_id="openai/gpt-4.1-mini",
        source_type="user_managed",
        adapter_type="openai_native",
        connection_kind="openai",
        display_name="Test",
        provider_model_name="gpt-4.1-mini",
    )
    monkeypatch.setattr(
        model_runtime,
        "resolve_runtime_credentials",
        lambda resolved: {"apiKey": f"key-for-{resolved.selection_id}"},
    )

    runtime = model_runtime.build_model_runtime(binding)

    assert runtime.binding is binding
    assert runtime.credentials == {"apiKey": "key-for-selection-1"}


def test_build_model_runtime_skips_credentials_for_the_app_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(_resolved: ResolvedModelConfig) -> dict[str, str]:
        raise AssertionError("app-default binding must not read the credential store")

    monkeypatch.setattr(model_runtime, "resolve_runtime_credentials", _fail)

    runtime = model_runtime.build_model_runtime()

    assert runtime.binding.selection_id is None
    assert runtime.credentials == {}
