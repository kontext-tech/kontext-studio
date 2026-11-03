from __future__ import annotations

from kontext.agentic.utils import AgentConfigBuilder
from kontext.common.constants import AgentTaskProfile
from kontext.common.contracts import AgentConfig
from kontext.schema import ModelReasoningEffort


class _StubLanguageModelService:
    def get_agent_config(self) -> AgentConfig:
        return AgentConfig()

    def get_reasoning_effort(self, task_profile: str | None = None) -> ModelReasoningEffort:
        return ModelReasoningEffort.LOW


class _StubRuntimeProvider:
    def get_language_model_service(self):
        return _StubLanguageModelService()


def _build(**kwargs) -> AgentConfig:
    return AgentConfigBuilder.from_runtime_provider(
        runtime_provider=_StubRuntimeProvider(),  # type: ignore[arg-type]
        **kwargs,
    )


def test_from_runtime_provider_applies_explicit_reasoning_effort() -> None:
    """A per-connection reasoning effort must override the default."""
    config = _build(reasoning_effort="high")

    assert config.reasoning_effort is ModelReasoningEffort.HIGH


def test_from_runtime_provider_falls_back_to_reasoning_default() -> None:
    class _Service(_StubLanguageModelService):
        def get_reasoning_effort(self, task_profile: str | None = None) -> ModelReasoningEffort:
            return ModelReasoningEffort.MEDIUM

    class _Provider:
        def get_language_model_service(self):
            return _Service()

    config = AgentConfigBuilder.from_runtime_provider(runtime_provider=_Provider())  # type: ignore[arg-type]

    assert config.reasoning_effort is ModelReasoningEffort.MEDIUM


class _ProfileService(_StubLanguageModelService):
    def get_reasoning_effort(self, task_profile: str | None = None) -> ModelReasoningEffort:
        return (
            ModelReasoningEffort.MEDIUM
            if task_profile == AgentTaskProfile.PYTHON_PLANNING
            else ModelReasoningEffort.LOW
        )


class _ProfileProvider:
    def get_language_model_service(self):
        return _ProfileService()


def test_with_task_profile_replaces_the_previous_profile_default() -> None:
    """A task profile must be able to raise/lower the default it owns.

    Regression: the base config was always pre-filled with the chat profile's
    default, so an "only if unset" merge made the ``python_planning`` default
    unreachable.
    """
    base = AgentConfig(reasoning_effort=ModelReasoningEffort.LOW)

    resolved = AgentConfigBuilder.with_task_profile(
        base,
        runtime_provider=_ProfileProvider(),  # type: ignore[arg-type]
        task_profile=AgentTaskProfile.PYTHON_PLANNING,
    )

    assert resolved.reasoning_effort is ModelReasoningEffort.MEDIUM


def test_with_task_profile_keeps_an_explicit_binding_selection() -> None:
    base = AgentConfig(reasoning_effort=ModelReasoningEffort.LOW)

    resolved = AgentConfigBuilder.with_task_profile(
        base,
        runtime_provider=_ProfileProvider(),  # type: ignore[arg-type]
        task_profile=AgentTaskProfile.PYTHON_PLANNING,
        reasoning_effort="high",
    )

    assert resolved.reasoning_effort is ModelReasoningEffort.HIGH
