from __future__ import annotations

import pytest
from agno.exceptions import ModelProviderError
from agno.models.google import Gemini

from kontext.harness.agno.gemini_model import KontextGemini, extract_gemini_error_message
from kontext.harness.agno.models import create_model
from kontext.llm import ResolvedModelConfig
from kontext.llm.provider_resolution import normalize_reasoning_kwargs
from kontext.schema import ModelReasoningEffort


class _FakeAioHttpResponse:
    status = 400
    reason = "Bad Request"

    def text(self) -> str:
        return "this should not be used"


class _FakeGeminiClientError(Exception):
    def __init__(self) -> None:
        super().__init__("400 INVALID_ARGUMENT")
        self.message = "Gemini rejected the request payload."
        self.details = {
            "error": {
                "code": 400,
                "message": self.message,
                "status": "INVALID_ARGUMENT",
            }
        }
        self.response = _FakeAioHttpResponse()


def _raise_broken_model_provider_error() -> None:
    cause = _FakeGeminiClientError()
    raise ModelProviderError(
        message=str(cause.response.text),
        status_code=400,
        model_name="Gemini",
        model_id="gemini-2.5-flash",
    ) from cause


def test_extract_gemini_error_message_uses_underlying_sdk_message() -> None:
    with pytest.raises(ModelProviderError) as excinfo:
        _raise_broken_model_provider_error()

    assert "<bound method" in str(excinfo.value)
    assert extract_gemini_error_message(excinfo.value) == "Gemini rejected the request payload."


@pytest.mark.asyncio
async def test_kontext_gemini_repairs_bound_method_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _broken_ainvoke_stream(self, *args, **kwargs):
        _ = (self, args, kwargs)
        _raise_broken_model_provider_error()
        yield None

    monkeypatch.setattr(Gemini, "ainvoke_stream", _broken_ainvoke_stream)

    model = KontextGemini(id="gemini-2.5-flash")

    with pytest.raises(ModelProviderError) as excinfo:
        async for _ in model.ainvoke_stream([], None):
            pass

    assert str(excinfo.value) == "Gemini rejected the request payload."
    assert isinstance(excinfo.value.__cause__, _FakeGeminiClientError)


def test_create_model_returns_kontext_gemini_for_gemini_provider() -> None:
    resolved_config = ResolvedModelConfig(
        selection_id="550e8400-e29b-41d4-a716-446655440000",
        canonical_model_id="gemini/gemini-2.5-flash",
        source_type="user_managed",
        adapter_type="gemini_native",
        connection_kind="gemini",
        display_name="Gemini",
        provider_model_name="gemini-2.5-flash",
    )

    model = create_model(resolved_config=resolved_config)

    assert isinstance(model, KontextGemini)
    assert isinstance(model, Gemini)


def test_normalize_reasoning_kwargs_omits_gemini_thinking_level() -> None:
    assert normalize_reasoning_kwargs("gemini", ModelReasoningEffort.LOW) == {}


def test_create_model_does_not_set_gemini_thinking_level_by_default() -> None:
    resolved_config = ResolvedModelConfig(
        selection_id="550e8400-e29b-41d4-a716-446655440000",
        canonical_model_id="gemini/gemini-2.5-flash",
        source_type="user_managed",
        adapter_type="gemini_native",
        connection_kind="gemini",
        display_name="Gemini",
        provider_model_name="gemini-2.5-flash",
    )

    model = create_model(
        resolved_config=resolved_config,
        reasoning_effort=ModelReasoningEffort.LOW,
    )

    assert getattr(model, "thinking_level", None) is None
