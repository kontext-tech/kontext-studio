"""Agno adapters for framework-neutral Kontext toolkits."""

from __future__ import annotations

import inspect
import json
from functools import wraps
from typing import TYPE_CHECKING, Any

from agno.tools import Toolkit
from agno.tools.decorator import tool as agno_tool
from agno.tools.function import Function
from kontext.agent import FrameworkToolkit, ToolCallable, ToolRuntimeSpec
from kontext.agent.tools import get_declared_tool_meta

if TYPE_CHECKING:
    from collections.abc import Sequence

type AgnoDecoratedTool = ToolCallable | Function
type AgnoAdaptableTool = ToolCallable | FrameworkToolkit | Toolkit
type AgnoTool = Toolkit | ToolCallable | Function | dict[str, Any]


def _required_argument_message(
    *,
    tool_name: str,
    tool_callable: ToolCallable,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str | None:
    signature = inspect.signature(tool_callable)
    try:
        signature.bind(*args, **kwargs)
        return None
    except TypeError:
        try:
            bound = signature.bind_partial(*args, **kwargs)
        except TypeError:
            return f"Invalid arguments for {tool_name}"
        missing = [
            name
            for name, parameter in signature.parameters.items()
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
            and parameter.default is inspect.Signature.empty
            and name not in bound.arguments
        ]
        if missing:
            return f"Missing required arguments for {tool_name}: {', '.join(missing)}"
        return f"Invalid arguments for {tool_name}"


def _serialize_tool_error(tool_callable: ToolCallable, message: str) -> str:
    meta = get_declared_tool_meta(tool_callable)
    result_class = meta.result_class if meta else None

    payload: dict[str, Any] = {
        "success": False,
        "message": message,
    }
    model_fields = getattr(result_class, "model_fields", None)
    if isinstance(model_fields, dict) and "error" in model_fields:
        payload["error"] = message

    if result_class and hasattr(result_class, "model_validate"):
        try:
            result = result_class.model_validate(payload)
            return result.model_dump_json(by_alias=True, exclude_none=True)
        except Exception:
            pass

    payload.setdefault("error", message)
    return json.dumps(payload)


def _wrap_callable_for_agno(spec: ToolRuntimeSpec) -> AgnoDecoratedTool:
    tool_callable = spec.callable

    @wraps(tool_callable)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        message = _required_argument_message(
            tool_name=spec.name,
            tool_callable=tool_callable,
            args=args,
            kwargs=kwargs,
        )
        if message:
            return _serialize_tool_error(tool_callable, message)
        return await tool_callable(*args, **kwargs)

    @wraps(tool_callable)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        message = _required_argument_message(
            tool_name=spec.name,
            tool_callable=tool_callable,
            args=args,
            kwargs=kwargs,
        )
        if message:
            return _serialize_tool_error(tool_callable, message)
        return tool_callable(*args, **kwargs)

    wrapper = async_wrapper if inspect.iscoroutinefunction(tool_callable) else sync_wrapper
    if not spec.description and not spec.strict:
        return wrapper
    decorated = agno_tool(strict=spec.strict, description=spec.description)(wrapper)
    if isinstance(decorated, Function):
        # Keep Agno's parsed metadata while routing runtime invocation back through
        # our wrapper so missing-arg failures stay structured JSON instead of a raw
        # validate_call exception.
        decorated.entrypoint = wrapper
    return decorated


class AgnoToolkitAdapter(Toolkit):
    """Adapter that exposes a neutral `FrameworkToolkit` as an Agno toolkit."""

    def __init__(self, toolkit: FrameworkToolkit) -> None:
        self.toolkit = toolkit
        agno_tools = [_wrap_callable_for_agno(spec) for spec in toolkit.get_tool_specs()]
        super().__init__(
            name=toolkit.name,
            tools=agno_tools,
            external_execution_required_tools=toolkit.external_execution_required_tools,
        )


def adapt_tools_for_agno(tools: Sequence[AgnoAdaptableTool]) -> list[AgnoTool]:
    """Adapt a mixed sequence of neutral toolkits/callables to Agno tools."""
    adapted: list[AgnoTool] = []
    for tool in tools:
        if isinstance(tool, FrameworkToolkit):
            adapted.append(AgnoToolkitAdapter(tool))
        elif isinstance(tool, Toolkit):
            adapted.append(tool)
        else:
            adapted.append(tool)
    return adapted
