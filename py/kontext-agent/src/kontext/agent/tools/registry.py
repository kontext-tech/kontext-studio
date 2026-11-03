"""
Central registry for tool metadata and result parsing.

This module is framework-agnostic and can be reused across agent runtimes.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

from kontext.common.constants.tool_names import (
    DELEGATE_TASK_TO_MEMBER_TOOL_NAME,
    DELEGATE_TASK_TO_MEMBERS_TOOL_NAME,
)
from kontext.schema import (
    ArtifactType,
    ChatMessageSegment,
    ChatToolCallSegment,
    ToolCallResult,
    ToolCallStatus,
)

logger = logging.getLogger(__name__)


class ToolAction(StrEnum):
    NONE = "none"
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


def _convert_method_name_to_display_name(method_name: str) -> str:
    """Convert a snake_case method name to a user-facing Title Case label."""
    display_name = method_name.replace("_", " ").title()
    replacements = {
        "Sql": "SQL",
        "Api": "API",
        "Http": "HTTP",
        "Json": "JSON",
        "Xml": "XML",
        "Html": "HTML",
        "Csv": "CSV",
        "Pdf": "PDF",
        "Id": "ID",
    }
    for old, new in replacements.items():
        display_name = re.sub(rf"\b{old}\b", new, display_name)
    return display_name


@dataclass(frozen=True)
class ToolMeta:
    """Metadata declared on a tool callable.

    Covers both the registry side (result parsing, artifact semantics, client
    visibility) and the harness side (LLM-facing description and strict-schema
    flags), so a tool declares its contract exactly once.

    Result contract — receipt plus reference: a tool that produces a durable
    output persists it (or promotes its local handle) and returns a *typed
    receipt* — result object with ids/refs, display actions, and at most a
    bounded preview for the model. Large payloads live in the artifact store
    and in the session's tool-result sidecar (explicit handles), never inline
    in the result string.
    """

    name: str
    display_name: str | None = None
    result_class: type[Any] | None = None
    action: ToolAction = ToolAction.NONE
    artifact_type: ArtifactType | None = None
    emit_tool_call: bool = False
    emit_result: bool = False
    external_execution: bool = False
    # LLM-facing: rendered into the harness's tool schema.
    description: str | None = None
    strict: bool = False

    def get_display_name(self) -> str:
        return self.display_name or _convert_method_name_to_display_name(self.name)


_TOOL_META_ATTR = "__kontext_tool_meta__"


class ToolRegistry:
    """Namespaced tool metadata registry."""

    def __init__(self, namespace: str = "default") -> None:
        self.namespace = namespace
        self._registry: dict[str, ToolMeta] = {}
        self._display_name_index: dict[str, str] = {}

    def register_tool(
        self,
        name: str,
        result_class: type[Any] | None = None,
        action: ToolAction = ToolAction.NONE,
        artifact_type: ArtifactType | None = None,
        display_name: str | None = None,
        emit_tool_call: bool = False,
        emit_result: bool = False,
        external_execution: bool = False,
        description: str | None = None,
        strict: bool = False,
    ) -> None:
        meta = ToolMeta(
            name=name,
            display_name=display_name,
            result_class=result_class,
            action=action,
            artifact_type=artifact_type,
            emit_tool_call=emit_tool_call,
            emit_result=emit_result,
            external_execution=external_execution,
            description=description,
            strict=strict,
        )
        resolved_display_name = meta.get_display_name()
        existing = self._display_name_index.get(resolved_display_name)
        if existing and existing != name:
            logger.warning(
                "Tool registry display-name conflict in namespace '%s': '%s' remapped from '%s' to '%s'",
                self.namespace,
                resolved_display_name,
                existing,
                name,
            )

        self._registry[name] = meta
        self._display_name_index[resolved_display_name] = name

    def get_tool_meta(self, name: str) -> ToolMeta | None:
        meta = self._registry.get(name)
        if meta:
            return meta
        internal_name = self._display_name_index.get(name)
        if internal_name:
            return self._registry.get(internal_name)
        return None

    def get_tool_meta_by_display_name(self, display_name: str) -> ToolMeta | None:
        tool_name = self._display_name_index.get(display_name)
        return self._registry.get(tool_name) if tool_name else None


_DEFAULT_REGISTRY = ToolRegistry()


def create_tool_registry(namespace: str = "default") -> ToolRegistry:
    """Create an isolated tool registry namespace."""
    return ToolRegistry(namespace=namespace)


def register_tool(
    name: str,
    result_class: type[Any] | None = None,
    action: ToolAction = ToolAction.NONE,
    artifact_type: ArtifactType | None = None,
    display_name: str | None = None,
    emit_tool_call: bool = False,
    emit_result: bool = False,
    external_execution: bool = False,
    description: str | None = None,
    strict: bool = False,
) -> None:
    """Register or overwrite tool metadata by internal tool name."""
    _DEFAULT_REGISTRY.register_tool(
        name=name,
        result_class=result_class,
        action=action,
        artifact_type=artifact_type,
        display_name=display_name,
        emit_tool_call=emit_tool_call,
        emit_result=emit_result,
        external_execution=external_execution,
        description=description,
        strict=strict,
    )


def get_tool_meta(name: str) -> ToolMeta | None:
    """Retrieve tool metadata by internal name or display name."""
    return _DEFAULT_REGISTRY.get_tool_meta(name)


def get_tool_meta_by_display_name(display_name: str) -> ToolMeta | None:
    """Retrieve tool metadata by its display name."""
    return _DEFAULT_REGISTRY.get_tool_meta_by_display_name(display_name)


def reset_default_tool_registry_for_tests() -> None:
    """Clear the default tool registry state.

    This is primarily intended for test isolation.
    """
    _DEFAULT_REGISTRY._registry.clear()
    _DEFAULT_REGISTRY._display_name_index.clear()


def _attach_declared_tool_meta(func: Any, meta: ToolMeta) -> None:
    setattr(func, _TOOL_META_ATTR, meta)


def get_declared_tool_meta(tool_callable: Any) -> ToolMeta | None:
    """Return metadata declared directly on a tool callable."""
    metadata_source = getattr(tool_callable, "__func__", tool_callable)
    return getattr(metadata_source, _TOOL_META_ATTR, None)


def register_tool_callable(
    tool_callable: Any, registry: ToolRegistry | None = None
) -> ToolMeta | None:
    """Register metadata declared on a tool callable into a target registry."""
    meta = get_declared_tool_meta(tool_callable)
    if meta is None:
        return None

    active_registry = registry or _DEFAULT_REGISTRY
    active_registry.register_tool(
        name=meta.name,
        result_class=meta.result_class,
        action=meta.action,
        artifact_type=meta.artifact_type,
        display_name=meta.display_name,
        emit_tool_call=meta.emit_tool_call,
        emit_result=meta.emit_result,
        external_execution=meta.external_execution,
        description=meta.description,
        strict=meta.strict,
    )
    return meta


def register_tools_from_callables(
    tool_callables: list[Any] | tuple[Any, ...],
    registry: ToolRegistry | None = None,
) -> ToolRegistry:
    """Build a registry from explicitly provided tool callables."""
    active_registry = registry or create_tool_registry()
    for tool_callable in tool_callables:
        register_tool_callable(tool_callable, registry=active_registry)
    return active_registry


def tool_meta(
    result_class: type[Any] | None = None,
    action: ToolAction = ToolAction.NONE,
    name: str | None = None,
    display_name: str | None = None,
    artifact_type: ArtifactType | None = None,
    emit_tool_call: bool = False,
    emit_result: bool = False,
    external_execution: bool = False,
    description: str | None = None,
    strict: bool = False,
    registry: ToolRegistry | None = None,
):
    """Decorator that declares tool metadata on the callable and registers it."""

    def decorator(func):  # type: ignore[no-untyped-def]
        tool_name = name or getattr(func, "__name__", None)
        if tool_name:
            meta = ToolMeta(
                name=tool_name,
                display_name=display_name,
                result_class=result_class,
                action=action,
                artifact_type=artifact_type,
                emit_tool_call=emit_tool_call,
                emit_result=emit_result,
                external_execution=external_execution,
                description=description,
                strict=strict,
            )
            _attach_declared_tool_meta(func, meta)
            active_registry = registry or _DEFAULT_REGISTRY
            active_registry.register_tool(
                tool_name,
                display_name=meta.display_name,
                result_class=meta.result_class,
                action=meta.action,
                artifact_type=meta.artifact_type,
                emit_tool_call=meta.emit_tool_call,
                emit_result=meta.emit_result,
                external_execution=meta.external_execution,
                description=meta.description,
                strict=meta.strict,
            )
        return func

    return decorator


def creates_artifact(
    result_class: type[Any],
    *,
    artifact_type: ArtifactType,
    display_name: str | None = None,
    emit_tool_call: bool = False,
    emit_result: bool = True,
    registry: ToolRegistry | None = None,
):
    return tool_meta(
        result_class=result_class,
        action=ToolAction.CREATE,
        artifact_type=artifact_type,
        display_name=display_name,
        emit_tool_call=emit_tool_call,
        emit_result=emit_result,
        registry=registry,
    )


def updates_artifact(
    result_class: type[Any],
    *,
    artifact_type: ArtifactType,
    display_name: str | None = None,
    emit_tool_call: bool = False,
    emit_result: bool = True,
    registry: ToolRegistry | None = None,
):
    return tool_meta(
        result_class=result_class,
        action=ToolAction.UPDATE,
        artifact_type=artifact_type,
        display_name=display_name,
        emit_tool_call=emit_tool_call,
        emit_result=emit_result,
        registry=registry,
    )


def deletes_artifact(
    result_class: type[Any],
    *,
    artifact_type: ArtifactType,
    display_name: str | None = None,
    emit_tool_call: bool = False,
    emit_result: bool = True,
    registry: ToolRegistry | None = None,
):
    return tool_meta(
        result_class=result_class,
        action=ToolAction.DELETE,
        artifact_type=artifact_type,
        display_name=display_name,
        emit_tool_call=emit_tool_call,
        emit_result=emit_result,
        registry=registry,
    )


def reads_artifact(
    result_class: type[Any],
    *,
    artifact_type: ArtifactType | None = None,
    display_name: str | None = None,
    emit_tool_call: bool = False,
    emit_result: bool = False,
    registry: ToolRegistry | None = None,
):
    return tool_meta(
        result_class=result_class,
        action=ToolAction.READ,
        artifact_type=artifact_type,
        display_name=display_name,
        emit_tool_call=emit_tool_call,
        emit_result=emit_result,
        registry=registry,
    )


class ToolResultParser:
    """Shared logic for parsing tool results and converting them to tool-call segments."""

    # Parsing is deterministic per (tool, raw result string), so results are
    # cached. The cache is bounded with FIFO eviction so long-running processes
    # cannot grow it without limit.
    _PARSE_CACHE_MAX_SIZE = 256

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self._cache: dict[str, Any] = {}
        self._registry = registry or _DEFAULT_REGISTRY

    def get_display_name(self, tool_name: str | None) -> str:
        if not tool_name:
            return ""
        meta = self._registry.get_tool_meta(tool_name)
        return meta.get_display_name() if meta else tool_name

    def parse_tool_result(
        self,
        tool_name: str | None,
        result_json: str | ToolCallResult | None,
        session_id: str | None = None,
    ) -> ToolCallResult | None:
        if not tool_name or not result_json:
            return None

        if isinstance(result_json, ToolCallResult):
            actual = result_json.root
            if isinstance(actual, str):
                result_json = actual
            else:
                return result_json

        if result_json in self._cache:
            return self._cache[result_json]

        meta = self._registry.get_tool_meta(tool_name)
        result_class = meta.result_class if meta else ToolCallResult

        try:
            # Tool payloads are reconstructed from the returned JSON. Typed
            # payloads referenced across tool calls live in the session's
            # sidecar under explicit ids, not here — parse never consults it.
            result_data = json.loads(result_json)
        except Exception:
            return None

        if not isinstance(result_data, dict):
            return None

        def normalize_enums(obj: Any) -> Any:
            if isinstance(obj, list):
                return [normalize_enums(item) for item in obj]
            if isinstance(obj, dict):
                return {k: normalize_enums(v) for k, v in obj.items()}
            if isinstance(obj, str) and "." in obj:
                dot_match = re.match(r"^([a-zA-Z0-9]+)\.([a-zA-Z0-9_]+)$", obj)
                if dot_match:
                    enum_name, member_name = dot_match.groups()
                    try:
                        import kontext.schema as ks

                        enum_cls = getattr(ks, enum_name, None)
                        if enum_cls and isinstance(enum_cls, type) and issubclass(enum_cls, Enum):
                            if member_name in enum_cls.__members__:
                                return enum_cls[member_name].value
                            target = member_name.replace("_", "").upper()
                            for name, member in enum_cls.__members__.items():
                                if name.replace("_", "").upper() == target:
                                    return member.value
                    except Exception:
                        pass
            return obj

        result_data = normalize_enums(result_data)

        if result_class is ToolCallResult:
            parsed_result = ToolCallResult.model_validate(result_data)
        elif result_class and hasattr(result_class, "model_validate"):
            parsed_result = result_class.model_validate(result_data)
        elif result_class:
            parsed_result = result_class(**result_data)
        else:
            return None

        self._evict_parse_cache()
        self._cache[result_json] = parsed_result
        return parsed_result

    def _evict_parse_cache(self) -> None:
        if len(self._cache) >= ToolResultParser._PARSE_CACHE_MAX_SIZE:
            self._cache.pop(next(iter(self._cache)))

    def convert_tool_to_segments(
        self,
        tool_name: str | None,
        tool_args: Any,
        result: ToolCallResult | str | None,
        tool_call_id: str | None,
        tool_call_error: str | None = None,
        session_id: str | None = None,
    ) -> list[ChatMessageSegment]:
        segments: list[ChatMessageSegment] = []
        display_name = self.get_display_name(tool_name)

        error_message = tool_call_error
        actual_error = bool(error_message)

        if not actual_error and result and tool_name:
            parsed = self.parse_tool_result(tool_name, result, session_id=session_id)
            if parsed and getattr(parsed, "success", True) is False:
                actual_error = True
                raw_error_msg = getattr(parsed, "message", None) or getattr(parsed, "error", None)
                error_message = str(raw_error_msg) if raw_error_msg else None
        elif actual_error and result and not error_message:
            if isinstance(result, ToolCallResult):
                error_message = str(result.root) if result.root else None
            else:
                error_message = result

        segments.append(
            ChatMessageSegment(
                ChatToolCallSegment(
                    segment_type="tool_call",
                    tool_call_id=tool_call_id,
                    tool_name=display_name,
                    tool_args=tool_args,
                    status=ToolCallStatus.ERROR if actual_error else ToolCallStatus.COMPLETED,
                    tool_call_error=error_message,
                    error=error_message,
                    result=result
                    if isinstance(result, ToolCallResult)
                    else (ToolCallResult(root=result) if result else None),
                )
            )
        )
        return segments


register_tool(
    DELEGATE_TASK_TO_MEMBER_TOOL_NAME,
    display_name="Run Sub Agent",
    emit_tool_call=True,
    emit_result=True,
)
register_tool(
    DELEGATE_TASK_TO_MEMBERS_TOOL_NAME,
    display_name="Run Sub Agents",
    emit_tool_call=True,
    emit_result=True,
)
