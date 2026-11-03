"""Configuration utilities for Kontext Agentic."""

from kontext.common.contracts import AgentConfig
from kontext.common.protocols import (
    ILanguageModelProtocol,
    LanguageModelServiceProviderProtocol,
)
from kontext.schema import ModelReasoningEffort


class AgentConfigBuilder:
    """Builds and adjusts ``AgentConfig`` from runtime-provider defaults."""

    @staticmethod
    def _language_model_service(
        runtime_provider: LanguageModelServiceProviderProtocol,
    ) -> ILanguageModelProtocol:
        language_model_service = runtime_provider.get_language_model_service()
        if language_model_service is None:
            raise RuntimeError("Language model service is not available")
        return language_model_service

    @staticmethod
    def _resolve_reasoning_effort(
        language_model_service: ILanguageModelProtocol,
        task_profile: str | None,
        reasoning_effort: ModelReasoningEffort | str | None = None,
    ) -> ModelReasoningEffort:
        """Resolve the effective reasoning effort once.

        Precedence: explicit selection (the persisted model binding) wins over
        the environment override, which wins over the task-profile default.
        """
        if reasoning_effort is not None:
            return ModelReasoningEffort(reasoning_effort)
        return language_model_service.get_reasoning_effort(task_profile)

    @staticmethod
    def from_runtime_provider(
        runtime_provider: LanguageModelServiceProviderProtocol,
        task_profile: str | None = None,
        reasoning_effort: ModelReasoningEffort | str | None = None,
    ) -> AgentConfig:
        """Build AgentConfig from runtime-provider defaults and explicit overrides.

        Model identity is not part of this config; it comes from the resolved
        model runtime assembled separately by composition.
        """
        language_model_service = AgentConfigBuilder._language_model_service(runtime_provider)
        config = language_model_service.get_agent_config().model_copy(deep=True)
        config.reasoning_effort = AgentConfigBuilder._resolve_reasoning_effort(
            language_model_service, task_profile, reasoning_effort
        )
        return config

    @staticmethod
    def with_task_profile(
        config: AgentConfig,
        *,
        runtime_provider: LanguageModelServiceProviderProtocol,
        task_profile: str | None,
        reasoning_effort: ModelReasoningEffort | str | None = None,
    ) -> AgentConfig:
        """Clone an AgentConfig and resolve reasoning for another task profile.

        ``reasoning_effort`` is the persisted binding's explicit selection; when
        absent, the environment override or the task-profile default applies.
        """
        language_model_service = AgentConfigBuilder._language_model_service(runtime_provider)
        resolved = config.model_copy(deep=True)
        resolved.reasoning_effort = AgentConfigBuilder._resolve_reasoning_effort(
            language_model_service, task_profile, reasoning_effort
        )
        return resolved
