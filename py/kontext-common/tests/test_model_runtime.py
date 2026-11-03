from __future__ import annotations

from kontext.common.contracts import ModelRuntime, ResolvedModelConfig


def _binding() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        canonical_model_id="openai/gpt-4.1-mini",
        source_type="user_managed",
        adapter_type="openai_native",
        connection_kind="openai",
        display_name="Test",
        provider_model_name="gpt-4.1-mini",
    )


def test_model_runtime_repr_redacts_credentials() -> None:
    runtime = ModelRuntime(binding=_binding(), credentials={"apiKey": "super-secret"})

    text = repr(runtime)

    assert "super-secret" not in text
    assert "credentials=<redacted>" in text
    assert "gpt-4.1-mini" in text
