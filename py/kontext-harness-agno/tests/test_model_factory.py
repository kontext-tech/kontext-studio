from __future__ import annotations

import pytest
from agno.models.anthropic import Claude
from agno.models.aws.bedrock import AwsBedrock
from agno.models.azure import AzureOpenAI
from agno.models.deepseek import DeepSeek
from agno.models.google import Gemini
from agno.models.lmstudio import LMStudio
from agno.models.mistral import MistralChat
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from agno.models.openai.like import OpenAILike

from kontext.harness.agno.models import create_model
from kontext.llm import ResolvedModelConfig
from kontext.llm.provider_resolution import resolve_provider_from_resolved_config


def _resolved_model_config(
    *,
    connection_kind: str,
    adapter_type: str,
    canonical_model_id: str,
    provider_model_name: str,
    endpoint_base_url: str | None = None,
    region: str | None = None,
) -> ResolvedModelConfig:
    return ResolvedModelConfig(
        selection_id="550e8400-e29b-41d4-a716-446655440000",
        canonical_model_id=canonical_model_id,
        source_type="user_managed",
        adapter_type=adapter_type,
        connection_kind=connection_kind,
        display_name="Test Connection",
        provider_model_name=provider_model_name,
        endpoint_base_url=endpoint_base_url,
        region=region,
    )


@pytest.mark.parametrize(
    ("resolved_config", "expected_type"),
    [
        (
            _resolved_model_config(
                connection_kind="lm_studio",
                adapter_type="openai_compatible",
                canonical_model_id="google/gemma-4-26b-a4b",
                provider_model_name="google/gemma-4-26b-a4b",
                endpoint_base_url="http://127.0.0.1:1234/v1",
            ),
            LMStudio,
        ),
        (
            _resolved_model_config(
                connection_kind="ollama",
                adapter_type="openai_compatible",
                canonical_model_id="google/gemma-4-26b-a4b",
                provider_model_name="google/gemma-4-26b-a4b",
                endpoint_base_url="http://127.0.0.1:11434/v1",
            ),
            Ollama,
        ),
        (
            _resolved_model_config(
                connection_kind="ollama_cloud",
                adapter_type="ollama_native",
                canonical_model_id="ollama_cloud/gpt-oss:120b",
                provider_model_name="gpt-oss:120b",
                endpoint_base_url="https://ollama.com",
            ),
            Ollama,
        ),
        (
            _resolved_model_config(
                connection_kind="deepseek",
                adapter_type="openai_compatible",
                canonical_model_id="deepseek/deepseek-chat",
                provider_model_name="deepseek-chat",
                endpoint_base_url="https://api.deepseek.com/v1",
            ),
            DeepSeek,
        ),
        (
            _resolved_model_config(
                connection_kind="mistral",
                adapter_type="openai_compatible",
                canonical_model_id="mistral/mistral-small-latest",
                provider_model_name="mistral-small-latest",
                endpoint_base_url="https://api.mistral.ai/v1",
            ),
            MistralChat,
        ),
        (
            _resolved_model_config(
                connection_kind="openai_compatible",
                adapter_type="openai_compatible",
                canonical_model_id="deepseek/deepseek-chat",
                provider_model_name="deepseek-chat",
                endpoint_base_url="https://api.deepseek.com/v1",
            ),
            OpenAILike,
        ),
        (
            _resolved_model_config(
                connection_kind="openrouter",
                adapter_type="openai_compatible",
                canonical_model_id="openai/gpt-4o-mini",
                provider_model_name="openai/gpt-4o-mini",
                endpoint_base_url="https://openrouter.ai/api/v1",
            ),
            OpenAILike,
        ),
        (
            _resolved_model_config(
                connection_kind="openai",
                adapter_type="openai_native",
                canonical_model_id="openai/gpt-4o-mini",
                provider_model_name="gpt-4o-mini",
                endpoint_base_url="https://api.openai.com/v1",
            ),
            OpenAIChat,
        ),
        (
            _resolved_model_config(
                connection_kind="anthropic",
                adapter_type="anthropic_native",
                canonical_model_id="anthropic/claude-3-5-sonnet-latest",
                provider_model_name="claude-3-5-sonnet-latest",
            ),
            Claude,
        ),
        (
            _resolved_model_config(
                connection_kind="gemini",
                adapter_type="gemini_native",
                canonical_model_id="gemini/gemini-2.5-flash",
                provider_model_name="gemini-2.5-flash",
            ),
            Gemini,
        ),
        (
            _resolved_model_config(
                connection_kind="google_vertex",
                adapter_type="google_vertex_native",
                canonical_model_id="gemini/gemini-2.5-flash",
                provider_model_name="gemini-2.5-flash",
            ),
            Gemini,
        ),
        (
            _resolved_model_config(
                connection_kind="azure_openai",
                adapter_type="azure_native",
                canonical_model_id="azure_openai/gpt-4o-mini",
                provider_model_name="gpt-4o-mini",
                endpoint_base_url="https://example.openai.azure.com",
            ),
            AzureOpenAI,
        ),
        (
            _resolved_model_config(
                connection_kind="bedrock",
                adapter_type="bedrock_native",
                canonical_model_id="bedrock/amazon.nova-2-lite-v1:0",
                provider_model_name="amazon.nova-2-lite-v1:0",
                region="ap-southeast-2",
            ),
            AwsBedrock,
        ),
    ],
)
def test_create_model_dispatches_by_connection_kind(
    monkeypatch: pytest.MonkeyPatch,
    resolved_config: ResolvedModelConfig,
    expected_type: type[object],
) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")

    model = create_model(resolved_config=resolved_config)

    assert isinstance(model, expected_type)


def test_create_model_sets_bedrock_region_from_resolved_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")
    resolved_config = _resolved_model_config(
        connection_kind="bedrock",
        adapter_type="bedrock_native",
        canonical_model_id="bedrock/amazon.nova-2-lite-v1:0",
        provider_model_name="amazon.nova-2-lite-v1:0",
        region="ap-southeast-2",
    )

    model = create_model(resolved_config=resolved_config)

    assert isinstance(model, AwsBedrock)
    assert getattr(model, "aws_region", None) == "ap-southeast-2"


def test_provider_from_resolved_config_prefers_connection_kind() -> None:
    assert (
        resolve_provider_from_resolved_config(
            _resolved_model_config(
                connection_kind="anthropic",
                adapter_type="openai_compatible",
                canonical_model_id="anthropic/claude-3-5-sonnet-latest",
                provider_model_name="claude-3-5-sonnet-latest",
            )
        )
        == "anthropic"
    )


def test_create_model_uses_the_binding_identity() -> None:
    """The binding is the only model identity input the factory accepts."""
    model = create_model(
        resolved_config=_resolved_model_config(
            connection_kind="anthropic",
            adapter_type="anthropic_native",
            canonical_model_id="anthropic/claude-3-5-sonnet-latest",
            provider_model_name="claude-3-5-sonnet-latest",
        )
    )

    assert isinstance(model, Claude)
    assert getattr(model, "id", None) == "claude-3-5-sonnet-latest"


def test_create_model_uses_supplied_credentials() -> None:
    """Credentials are injected by composition, never read from the store here."""
    model = create_model(
        resolved_config=_resolved_model_config(
            connection_kind="openai",
            adapter_type="openai_native",
            canonical_model_id="openai/gpt-4o-mini",
            provider_model_name="gpt-4o-mini",
        ),
        credentials={"apiKey": "test-key"},
    )

    assert getattr(model, "api_key", None) == "test-key"


def test_create_model_fails_loud_without_a_provider() -> None:
    with pytest.raises(ValueError, match="has no provider"):
        create_model(
            resolved_config=_resolved_model_config(
                connection_kind="platform",
                adapter_type="unknown_adapter",
                canonical_model_id="unknown/model",
                provider_model_name="model",
            )
        )


def test_create_model_fails_loud_without_a_model_id() -> None:
    with pytest.raises(ValueError, match="has no model id"):
        create_model(
            resolved_config=_resolved_model_config(
                connection_kind="openai",
                adapter_type="openai_native",
                canonical_model_id="",
                provider_model_name="",
            )
        )


def test_provider_factory_registry_covers_supported_providers() -> None:
    """Every supported provider must have an Agno factory registered."""
    from kontext.harness.agno.providers import PROVIDER_FACTORIES
    from kontext.llm.provider_definitions import SUPPORTED_PROVIDERS

    assert set(PROVIDER_FACTORIES) == set(SUPPORTED_PROVIDERS)


def test_resolved_config_resolves_token_limit_from_canonical_id() -> None:
    """Curated token limits resolve even though the runtime name is an alias."""
    model = create_model(
        resolved_config=_resolved_model_config(
            connection_kind="openai",
            adapter_type="openai_native",
            canonical_model_id="openai/gpt-4o-mini",
            provider_model_name="gpt-4o-mini",
            endpoint_base_url="https://api.openai.com/v1",
        )
    )

    assert getattr(model, "max_tokens", None) == 16384


def test_resolved_config_resolves_vertex_token_limit() -> None:
    model = create_model(
        resolved_config=_resolved_model_config(
            connection_kind="google_vertex",
            adapter_type="google_vertex_native",
            canonical_model_id="gemini/gemini-2.5-flash",
            provider_model_name="gemini-2.5-flash",
        )
    )

    assert getattr(model, "max_output_tokens", None) == 65536


def test_openrouter_keeps_namespaced_model_ids() -> None:
    """OpenRouter requires vendor-namespaced ids; the prefix must not be stripped."""
    model = create_model(
        resolved_config=_resolved_model_config(
            connection_kind="openrouter",
            adapter_type="openai_compatible",
            canonical_model_id="anthropic/claude-sonnet-4-6",
            provider_model_name="anthropic/claude-sonnet-4.6",
            endpoint_base_url="https://openrouter.ai/api/v1",
        )
    )

    assert getattr(model, "id", None) == "anthropic/claude-sonnet-4.6"


def test_ollama_resolves_catalog_alias_to_native_tag() -> None:
    """Ollama renames models, so the curated alias (a native tag) is used."""
    model = create_model(
        resolved_config=_resolved_model_config(
            connection_kind="ollama",
            adapter_type="ollama_native",
            canonical_model_id="google/gemma-4-26b-a4b",
            provider_model_name="google/gemma-4-26b-a4b",
        )
    )

    assert getattr(model, "id", None) == "gemma4:26b-a4b"
    assert getattr(model, "options", None) == {"num_predict": 8192}


def test_lm_studio_keeps_hugging_face_model_id() -> None:
    model = create_model(
        resolved_config=_resolved_model_config(
            connection_kind="lm_studio",
            adapter_type="openai_compatible",
            canonical_model_id="qwen/qwen3-coder-30b",
            provider_model_name="qwen/qwen3-coder-30b",
        )
    )

    assert getattr(model, "id", None) == "qwen/qwen3-coder-30b"
