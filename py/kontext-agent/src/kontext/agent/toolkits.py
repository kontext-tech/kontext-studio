"""Framework-neutral toolkit primitives and tool metadata."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .tools import get_declared_tool_meta

ToolCallable = Callable[..., Any]


@dataclass(frozen=True)
class ToolRuntimeSpec:
    """Framework-neutral runtime description for a tool callable."""

    callable: ToolCallable
    name: str
    description: str | None = None
    strict: bool = False


class FrameworkToolkit:
    """Framework-neutral toolkit container.

    Concrete runtime adapters can transform these tool callables into their
    framework-specific representations.
    """

    def __init__(
        self,
        *,
        name: str,
        tools: Sequence[ToolCallable] | None = None,
    ) -> None:
        self.name = name
        self._tools = list(tools or [])

    @property
    def external_execution_required_tools(self) -> list[str]:
        """Tool method names declared `external_execution` in their `ToolMeta`.

        Derived from the callables' declared metadata so the external-execution
        contract lives in exactly one place (the `tool_meta` decoration).
        """
        return [
            getattr(tool, "__name__", "tool")
            for tool in self._tools
            if (meta := get_declared_tool_meta(tool)) and meta.external_execution
        ]

    def get_tool_callables(self) -> list[ToolCallable]:
        """Return the tool callables exposed by this toolkit."""
        return list(self._tools)

    def get_tool_specs(self) -> list[ToolRuntimeSpec]:
        """Return tool runtime specs for framework adapters.

        Specs are derived from the ``ToolMeta`` declared on each callable, so a
        tool declares its runtime contract (description, strict schema) once.
        """
        return [get_tool_runtime_spec(tool_callable) for tool_callable in self._tools]


def get_tool_runtime_spec(tool_callable: ToolCallable) -> ToolRuntimeSpec:
    """Build a runtime spec from a tool callable's declared ``ToolMeta``."""
    meta = get_declared_tool_meta(tool_callable)
    return ToolRuntimeSpec(
        callable=tool_callable,
        name=getattr(tool_callable, "__name__", "tool"),
        description=meta.description if meta else None,
        strict=meta.strict if meta else False,
    )
