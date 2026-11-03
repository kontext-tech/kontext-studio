"""Kontext-specific Gemini model adapter fixes (Agno harness)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

from agno.exceptions import ModelProviderError
from agno.models.google import Gemini


def _stringify_gemini_error_details(details: object) -> str | None:
    if isinstance(details, str):
        normalized = details.strip()
        return normalized or None

    if isinstance(details, dict):
        nested_error = details.get("error")
        if isinstance(nested_error, dict):
            nested_message = nested_error.get("message")
            if isinstance(nested_message, str) and nested_message.strip():
                return nested_message.strip()

        message = details.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        return json.dumps(details, ensure_ascii=True)

    if isinstance(details, list):
        return json.dumps(details, ensure_ascii=True)

    return None


def extract_gemini_error_message(exc: ModelProviderError) -> str:
    """Recover the underlying Gemini API message from Agno's wrapped error."""

    original_message = str(exc.message)
    cause = exc.__cause__ or exc.__context__
    if cause is None:
        return original_message

    cause_message = getattr(cause, "message", None)
    if isinstance(cause_message, str) and cause_message.strip():
        return cause_message.strip()

    details_message = _stringify_gemini_error_details(getattr(cause, "details", None))
    if details_message:
        return details_message

    response = getattr(cause, "response", None)
    if response is not None:
        response_text = getattr(response, "text", None)
        if isinstance(response_text, str) and response_text.strip():
            return response_text.strip()

        response_reason = getattr(response, "reason", None) or getattr(
            response, "reason_phrase", None
        )
        response_status = getattr(response, "status", None) or getattr(
            response, "status_code", None
        )
        if response_reason and response_status:
            return f"{response_status} {response_reason}"

    return original_message


def _raise_repaired_gemini_error(exc: ModelProviderError) -> None:
    repaired_message = extract_gemini_error_message(exc)
    original_message = str(exc.message)
    if repaired_message == original_message:
        raise exc

    repaired_error = type(exc)(
        message=repaired_message,
        status_code=exc.status_code,
        model_name=getattr(exc, "model_name", None),
        model_id=getattr(exc, "model_id", None),
    )
    raise repaired_error from (exc.__cause__ or exc.__context__)


class KontextGemini(Gemini):
    """Gemini adapter that preserves readable provider errors."""

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return super().invoke(*args, **kwargs)
        except ModelProviderError as exc:
            _raise_repaired_gemini_error(exc)

    def invoke_stream(self, *args: Any, **kwargs: Any) -> Iterator[Any]:
        try:
            yield from super().invoke_stream(*args, **kwargs)
        except ModelProviderError as exc:
            _raise_repaired_gemini_error(exc)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return await super().ainvoke(*args, **kwargs)
        except ModelProviderError as exc:
            _raise_repaired_gemini_error(exc)

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        try:
            async for item in super().ainvoke_stream(*args, **kwargs):
                yield item
        except ModelProviderError as exc:
            _raise_repaired_gemini_error(exc)
