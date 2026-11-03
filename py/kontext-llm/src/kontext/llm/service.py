"""Language model service backed by environment configuration."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from importlib import resources
from pathlib import Path

from kontext.common.constants import AgentTaskProfile, ModelEnvVars
from kontext.common.contracts import AgentConfig
from kontext.common.protocols import ILanguageModelProtocol
from kontext.common.utils.file_storage import get_file_storage_path
from kontext.schema import (
    FoundationModel,
    ModelProviderDefinition,
    ModelReasoningEffort,
)

from .provider_definitions import (
    list_model_provider_definitions,
    model_supports_connection_kind,
    normalize_foundation_model_id,
    parse_json_array,
    strip_known_provider_prefix,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_foundation_models() -> list[FoundationModel]:
    """Load the packaged curated catalog, then overlay external overrides.

    The packaged file is part of the release artifact, so parse/validation
    failures raise instead of silently yielding an empty catalog. External
    overrides (from file storage) are best-effort and replace packaged entries
    with the same ``canonicalModelId``.
    """
    models: dict[str, FoundationModel] = {}
    resource_path = resources.files("kontext.llm.resources.models") / "foundation-models.json"
    with resource_path.open("r") as handle:
        data = handle.read()
    for item in parse_json_array(data):
        model = FoundationModel.model_validate(item)
        models[model.canonical_model_id] = model

    external_models = _load_external_models()
    for model in external_models:
        models[model.canonical_model_id] = model

    return list(models.values())


def _load_external_models() -> list[FoundationModel]:
    """Load external model-registry overrides from file storage.

    Precedence: the first existing candidate wins, and its entries override
    packaged models with the same ``canonicalModelId``. Candidate order is
    ``models/foundation-models.json`` then ``models/model-registry.json`` under
    the configured file-storage root (``FILE_STORAGE_PATH``). Malformed
    overrides are skipped with a warning so a bad local file cannot break the
    curated catalog.
    """
    storage_root = Path(get_file_storage_path())
    candidates = [
        storage_root / "models" / "foundation-models.json",
        storage_root / "models" / "model-registry.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            data = candidate.read_text()
            return [FoundationModel.model_validate(item) for item in parse_json_array(data)]
        except Exception as exc:
            logger.warning("Failed to load external models from %s: %s", candidate, exc)
    return []


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in ("true", "1", "yes")


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


class LanguageModelService(ILanguageModelProtocol):
    """Resolves models and agent configuration from environment defaults."""

    def __init__(self, models: list[FoundationModel] | None = None) -> None:
        self._models = models or _load_foundation_models()

    def list_model_definitions(self, provider: str | None = None) -> list[FoundationModel]:
        if provider is None:
            return list(self._models)
        return [model for model in self._models if model_supports_connection_kind(model, provider)]

    def get_model_definition(
        self, model_id: str, provider: str | None = None
    ) -> FoundationModel | None:
        candidate_ids: list[str] = []
        for candidate in (
            model_id,
            normalize_foundation_model_id(model_id),
            strip_known_provider_prefix(model_id),
            strip_known_provider_prefix(normalize_foundation_model_id(model_id)),
        ):
            if candidate and candidate not in candidate_ids:
                candidate_ids.append(candidate)
        for model in self._models:
            if model.canonical_model_id in candidate_ids and (
                provider is None or model_supports_connection_kind(model, provider)
            ):
                return model
        return None

    def normalize_model_id(self, model_id: str | None) -> str | None:
        if model_id is None:
            return None
        model_definition = self.get_model_definition(model_id)
        if model_definition is not None:
            return model_definition.canonical_model_id
        return normalize_foundation_model_id(model_id)

    def list_provider_definitions(self) -> list[ModelProviderDefinition]:
        return list_model_provider_definitions()

    def get_agent_config(self) -> AgentConfig:
        """Return the environment-driven behaviour defaults for an agent run.

        Model identity is resolved separately by composition, and reasoning is
        resolved by ``AgentConfigBuilder`` for the relevant task profile.
        """
        markdown = _parse_bool(os.getenv(ModelEnvVars.PROJECT_AGENT_MARKDOWN))
        add_history = _parse_bool(os.getenv(ModelEnvVars.PROJECT_AGENT_ADD_HISTORY))
        telemetry = _parse_bool(os.getenv(ModelEnvVars.PROJECT_AGENT_TELEMETRY))
        summary = _parse_bool(os.getenv(ModelEnvVars.PROJECT_AGENT_SUMMARY))
        debug_mode = _parse_bool(os.getenv(ModelEnvVars.PROJECT_AGENT_DEBUG))
        tool_call_limit = _parse_int(os.getenv(ModelEnvVars.PROJECT_AGENT_TOOL_CALL_LIMIT))
        sql_dialect = os.getenv(ModelEnvVars.SQL_DIALECT, "DuckDB")
        num_history_runs = _parse_int(os.getenv(ModelEnvVars.PROJECT_AGENT_NUM_HISTORY_RUNS))

        return AgentConfig(
            markdown=markdown if markdown is not None else True,
            tool_call_limit=tool_call_limit or 50,
            sql_dialect=sql_dialect,
            add_history_to_context=add_history if add_history is not None else True,
            num_history_runs=num_history_runs or 3,
            telemetry=telemetry if telemetry is not None else False,
            summary=summary if summary is not None else True,
            debug_mode=debug_mode if debug_mode is not None else False,
        )

    def get_reasoning_effort(self, task_profile: str | None = None) -> ModelReasoningEffort:
        default_effort = (
            ModelReasoningEffort.MEDIUM
            if task_profile == AgentTaskProfile.PYTHON_PLANNING
            else ModelReasoningEffort.LOW
        )
        env_effort = os.getenv(ModelEnvVars.PROJECT_AGENT_REASONING_EFFORT)
        try:
            return ModelReasoningEffort((env_effort or default_effort).lower())
        except ValueError:
            return default_effort
