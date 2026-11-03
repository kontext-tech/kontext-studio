from kontext.llm import LanguageModelService, infer_model_connection_validation_state
from kontext.llm.provider_definitions import (
    DEFAULT_MODEL_IDS,
    PROVIDER_MODEL_ENV_VARS,
    SUPPORTED_PROVIDERS,
    get_default_endpoint_base_url,
    list_model_provider_definitions,
    model_supports_connection_kind,
    strip_known_provider_prefix,
    strip_own_provider_prefix,
)
from kontext.llm.provider_resolution import resolve_provider_from_model_definition
from kontext.schema import (
    ModelAdapterType,
    ModelConnectionCredentialRefs,
    ModelConnectionKind,
    ModelConnectionProviderConfig,
    ModelProviderConfigField,
)


def test_provider_tables_match_provider_definitions() -> None:
    """The derived Python tables must stay in sync with the JSON definitions."""
    definitions = list_model_provider_definitions()
    definition_kinds = {d.connection_kind for d in definitions}

    assert set(SUPPORTED_PROVIDERS) == definition_kinds
    assert set(DEFAULT_MODEL_IDS) == definition_kinds
    assert set(PROVIDER_MODEL_ENV_VARS) == definition_kinds


def test_provider_definitions_are_internally_consistent() -> None:
    """Every definition uses valid enum values and unique connection kinds."""
    definitions = list_model_provider_definitions()
    kinds = [d.connection_kind for d in definitions]

    assert len(kinds) == len(set(kinds)), "connection kinds must be unique"

    valid_config_fields = {field.value for field in ModelProviderConfigField}
    valid_adapters = {adapter.value for adapter in ModelAdapterType}
    valid_kinds = {kind.value for kind in ModelConnectionKind if kind.value != "platform"}

    for definition in definitions:
        assert definition.adapter_type.value in valid_adapters
        assert definition.connection_kind.value in valid_kinds
        for field in (
            *definition.required_config_fields,
            *definition.optional_config_fields,
        ):
            assert field.value in valid_config_fields


def test_every_adapter_has_at_least_one_provider() -> None:
    adapters = {d.adapter_type.value for d in list_model_provider_definitions()}
    assert adapters == {adapter.value for adapter in ModelAdapterType}


def test_default_endpoint_base_url_comes_from_definition() -> None:
    assert get_default_endpoint_base_url("deepseek") == "https://api.deepseek.com/v1"
    assert get_default_endpoint_base_url("mistral") == "https://api.mistral.ai/v1"
    assert get_default_endpoint_base_url("openai") == "https://api.openai.com/v1"
    assert get_default_endpoint_base_url("anthropic") is None
    assert get_default_endpoint_base_url("ollama_cloud") == "https://ollama.com"


def test_language_model_service_resolves_curated_canonical_model_ids_only() -> None:
    service = LanguageModelService()

    gemini_model = service.get_model_definition("gemini/gemini-2.5-flash")
    bedrock_model = service.get_model_definition("bedrock/amazon.nova-2-lite-v1:0")
    gemma_model = service.get_model_definition("google/gemma-4-12b")

    assert gemini_model is not None
    assert gemini_model.canonical_model_id == "gemini/gemini-2.5-flash"
    assert bedrock_model is not None
    assert bedrock_model.canonical_model_id == "bedrock/amazon.nova-2-lite-v1:0"
    assert gemma_model is not None
    assert gemma_model.canonical_model_id == "google/gemma-4-12b"
    assert gemma_model.max_tokens == 256000
    assert service.get_model_definition("google/gemini-2.5-flash") is None
    assert service.get_model_definition("bedrock/amazon.nova-lite-v1:0") is not None
    assert service.normalize_model_id("google/gemini-2.5-flash") == ("google/gemini-2.5-flash")
    assert service.normalize_model_id("bedrock/amazon.nova-lite-v1:0") == (
        "bedrock/amazon.nova-lite-v1:0"
    )


def test_new_provider_defaults_resolve() -> None:
    service = LanguageModelService()

    ollama_cloud = service.get_model_definition("ollama_cloud/gpt-oss:120b")
    vertex = service.get_model_definition("gemini/gemini-2.5-flash", "google_vertex")
    azure = service.get_model_definition("azure_openai/gpt-5.4-mini")

    assert ollama_cloud is not None
    assert "ollama_cloud" in {k.value for k in ollama_cloud.supported_connection_kinds}
    assert vertex is not None
    assert azure is not None


def test_strip_known_provider_prefix_only_strips_real_providers() -> None:
    assert strip_known_provider_prefix("deepseek/deepseek-chat") == "deepseek-chat"
    assert strip_known_provider_prefix("ollama_cloud/deepseek-v4.1-flash") == (
        "deepseek-v4.1-flash"
    )
    # Vendor namespaces are not providers and must survive.
    assert strip_known_provider_prefix("meta-llama/llama-3-70b") == "meta-llama/llama-3-70b"
    assert strip_known_provider_prefix("google/gemini-2.5-flash") == "google/gemini-2.5-flash"
    assert strip_known_provider_prefix(None) is None


def test_strip_own_provider_prefix_only_strips_matching_kind() -> None:
    assert strip_own_provider_prefix("openrouter/openai/gpt-4o", "openrouter") == ("openai/gpt-4o")
    assert strip_own_provider_prefix("openai/gpt-4o", "openrouter") == "openai/gpt-4o"


def test_provider_inference_prefers_primary_connection_kind() -> None:
    """The catalog orders the primary provider first; inference must honour it."""
    service = LanguageModelService()

    deepseek = service.get_model_definition("deepseek/deepseek-v4-pro")
    openai = service.get_model_definition("openai/gpt-4o")
    gemma = service.get_model_definition("google/gemma-4-26b-a4b")
    assert deepseek is not None and openai is not None and gemma is not None

    assert resolve_provider_from_model_definition(deepseek) == "deepseek"
    assert resolve_provider_from_model_definition(openai) == "openai"
    assert resolve_provider_from_model_definition(gemma) == "lm_studio"


def test_generic_openai_compatible_kind_still_serves_shared_adapter_models() -> None:
    """Regression: first-class kinds must not invalidate legacy generic connections.

    ``deepseek/deepseek-chat`` used to list ``["openai_compatible"]``; the refactor
    narrowed it to ``["deepseek"]``. A pre-existing connection configured through
    the generic ``openai_compatible`` provider must stay valid (matching adapter),
    otherwise it drops out of ``/models/catalog`` and the dashboard chart falls
    back to raw model-selection UUIDs.
    """
    service = LanguageModelService()

    deepseek = service.get_model_definition("deepseek/deepseek-chat")
    mistral = service.get_model_definition("mistral/mistral-small-latest")
    assert deepseek is not None and mistral is not None

    # Same adapter (openai_compatible) -> accepted through the generic kind.
    assert model_supports_connection_kind(deepseek, "openai_compatible")
    assert model_supports_connection_kind(mistral, "openai_compatible")
    # Native mismatch -> still rejected.
    assert not model_supports_connection_kind(deepseek, "openai")
    assert not model_supports_connection_kind(deepseek, "anthropic")


def test_native_adapter_model_rejects_unrelated_generic_kind() -> None:
    """An openai_native model is not servable through the generic kind."""
    service = LanguageModelService()

    gpt = service.get_model_definition("openai/gpt-4o-mini")
    bedrock = service.get_model_definition("bedrock/amazon.nova-2-lite-v1:0")
    assert gpt is not None and bedrock is not None

    assert not model_supports_connection_kind(gpt, "openai_compatible")
    assert not model_supports_connection_kind(bedrock, "openai_compatible")


def test_infer_validation_state_requires_configured_credentials() -> None:
    validation_state = infer_model_connection_validation_state(
        connection_kind="deepseek",
        provider_config=ModelConnectionProviderConfig(
            endpoint_base_url="https://api.deepseek.com/v1",
        ),
        credential_refs=None,
    )

    assert validation_state == "pending"


def test_infer_validation_state_valid_when_required_fields_present() -> None:
    validation_state = infer_model_connection_validation_state(
        connection_kind="deepseek",
        provider_config=ModelConnectionProviderConfig(
            endpoint_base_url="https://api.deepseek.com/v1",
        ),
        credential_refs=ModelConnectionCredentialRefs(api_key_ref="secret://example"),
    )

    assert validation_state == "valid"


def test_vertex_validation_requires_project_id() -> None:
    from kontext.llm.provider_definitions import infer_model_connection_validation_state as infer

    assert (
        infer(
            connection_kind="google_vertex",
            provider_config=None,
            credential_refs=None,
        )
        == "pending"
    )
    assert (
        infer(
            connection_kind="google_vertex",
            provider_config=ModelConnectionProviderConfig(project_id="my-project"),
            credential_refs=None,
        )
        == "valid"
    )


def test_external_model_override_takes_precedence(tmp_path, monkeypatch) -> None:
    """A file-storage registry overrides packaged models with the same id."""
    from kontext.llm import service as service_module

    models_dir = tmp_path / "models"
    models_dir.mkdir()
    override_path = models_dir / "foundation-models.json"
    override_path.write_text(
        '[{"canonicalModelId": "deepseek/deepseek-chat", "name": "Overridden DeepSeek", '
        '"vendor": "DeepSeek", "adapterType": "openai_compatible", "maxTokens": 1234, '
        '"supportedConnectionKinds": ["deepseek"]}]'
    )
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path))
    service_module._load_foundation_models.cache_clear()
    try:
        service = LanguageModelService()
        overridden = service.get_model_definition("deepseek/deepseek-chat")
        assert overridden is not None
        assert overridden.name == "Overridden DeepSeek"
        assert overridden.max_tokens == 1234
    finally:
        service_module._load_foundation_models.cache_clear()
