from __future__ import annotations

from kontext.chat.sessions import _enrich_usages_with_model_names
from kontext.llm import register_local_model_store, reset_model_resolution_hooks
from kontext.schema import (
    ModelAdapterType,
    ModelConnection,
    ModelConnectionKind,
    ModelConnectionSourceType,
    ModelValidationState,
    TokenUsageStatsModel,
)


class _FakeStore:
    def __init__(self, connections: dict[str, ModelConnection]) -> None:
        self._connections = connections

    def get_model_connection(self, connection_id: str) -> ModelConnection | None:
        return self._connections.get(connection_id)

    def resolve_model_connection_credentials(self, connection_id: str) -> dict[str, str]:
        return {}


def _connection(connection_id: str, canonical_model_id: str, display_name: str) -> ModelConnection:
    return ModelConnection(
        id=connection_id,
        source_type=ModelConnectionSourceType.USERMANAGED,
        adapter_type=ModelAdapterType.OLLAMANATIVE,
        connection_kind=ModelConnectionKind.OLLAMACLOUD,
        canonical_model_id=canonical_model_id,
        display_name=display_name,
        enabled=True,
        validation_state=ModelValidationState.VALID,
    )


def _usage(selection_id: str | None) -> TokenUsageStatsModel:
    return TokenUsageStatsModel(
        month="2026-10",
        model_selection_id=selection_id,
        canonical_model_id=None,
        inbound_tokens=1,
        outbound_tokens=2,
        total_tokens=3,
    )


def test_enrich_fills_canonical_id_and_display_name() -> None:
    selection_id = "a13f64f1-fbdc-42ad-a597-777693cb0323"
    register_local_model_store(
        _FakeStore(
            {
                selection_id: _connection(
                    selection_id, "ollama_cloud/deepseek-v4.1-flash", "DeepSeek V4.1 Flash"
                )
            }
        )
    )
    try:
        usages = [_usage(selection_id)]
        _enrich_usages_with_model_names(usages)
        assert usages[0].canonical_model_id == "ollama_cloud/deepseek-v4.1-flash"
        assert usages[0].model_display_name == "DeepSeek V4.1 Flash"
    finally:
        reset_model_resolution_hooks()


def test_enrich_leaves_deleted_connection_untouched() -> None:
    register_local_model_store(_FakeStore({}))
    try:
        usages = [_usage("missing-connection-id")]
        _enrich_usages_with_model_names(usages)
        assert usages[0].canonical_model_id is None
        assert usages[0].model_display_name is None
    finally:
        reset_model_resolution_hooks()


def test_enrich_is_noop_without_registered_store() -> None:
    reset_model_resolution_hooks()
    usages = [_usage("any")]
    _enrich_usages_with_model_names(usages)
    assert usages[0].canonical_model_id is None
    assert usages[0].model_display_name is None
