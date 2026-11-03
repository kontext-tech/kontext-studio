"""Framework-neutral tool JSON-schema rendering.

`render_tool_schema` defines Kontext's model-facing tool surface as a pure
function of a tool callable: name, description, and a JSON-schema ``parameters``
object derived from type hints and the callable's docstring. This is the
reference any harness adapter must reproduce, so budget tests, conformance
scenarios, and schema-size reasoning never need a harness SDK.

Derivation contract (mirrors the reference harness, byte-for-byte on current
tools):

- Container params (``self``), the return annotation, and ``RuntimeToolContext``
  injections are excluded from the schema; the runtime injects them.
- Parameter descriptions come from the docstring (``:param x:`` sections). A
  docstring with a type name is rendered as ``(type) description``.
- ``Optional[T]`` unwraps to ``T``; PEP 604 unions (``T | None``) are rendered
  as ``anyOf`` (the reference harness does not unwrap modern union syntax).
- ``required`` lists parameters without defaults, in signature order, filtered
  to properties that could be serialized.
- ``strict=True`` forbids additional properties and marks every property
  required.
"""

from __future__ import annotations

import types
from dataclasses import fields as dataclass_fields
from enum import Enum
from inspect import Parameter, getdoc, signature
from typing import (
    Annotated,
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from docstring_parser import parse as parse_docstring

from .context import RuntimeToolContext
from .toolkits import ToolCallable, ToolRuntimeSpec

type ToolSchemaDocument = dict[str, Any]

_CONTAINER_PARAMS = frozenset(
    {"self", "return", "agent", "team", "run_context", "images", "videos", "audios", "files"}
)

_UNION_ORIGINS: tuple[Any, ...] = (Union, types.UnionType)


def _json_type_for_py_type(type_name: str) -> str:
    if type_name == "int":
        return "integer"
    if type_name in ("float", "complex", "Decimal"):
        return "number"
    if type_name in ("str", "string"):
        return "string"
    if type_name in ("bool", "boolean"):
        return "boolean"
    if type_name in ("NoneType", "None"):
        return "null"
    if type_name in ("list", "tuple", "set", "frozenset"):
        return "array"
    if type_name in ("dict", "mapping"):
        return "object"
    return "object"


def _inline_pydantic_schema(
    schema: dict[str, Any], _active_refs: frozenset[str] = frozenset()
) -> Any:
    """Inline a Pydantic model schema by replacing ``$ref`` with definitions."""
    definitions = schema.pop("$defs", {})

    def process(node: Any, active_refs: frozenset[str]) -> Any:
        if isinstance(node, list):
            return [process(item, active_refs) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            ref = node["$ref"]
            if not ref.startswith("#/$defs/"):
                return {"type": "object"}
            def_name = ref.split("/")[-1]
            if def_name in active_refs:
                return {
                    "type": "object",
                    "description": f"A nested {def_name} object of this same shape.",
                }
            definition = definitions.get(def_name)
            if definition is None:
                return {"type": "object"}
            return process(definition, active_refs | {def_name})

        result = dict(node)
        for key in ("items", "additionalProperties", "propertyNames"):
            if key in result:
                result[key] = process(result[key], active_refs)
        if "properties" in result:
            result["properties"] = {
                name: process(prop, active_refs) for name, prop in result["properties"].items()
            }
        for key in ("anyOf", "allOf", "oneOf"):
            if key in result:
                result[key] = [process(sub, active_refs) for sub in result[key]]
        result.pop("$defs", None)
        return result

    return process(schema, _active_refs)


def _is_union_origin(origin: Any) -> bool:
    return origin in _UNION_ORIGINS


def _schema_for_arg(type_hint: Any) -> ToolSchemaDocument | None:
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    if origin is not None:
        if origin is Annotated and args:
            return _schema_for_arg(args[0])
        if origin is Literal and args:
            if all(isinstance(arg, str) for arg in args):
                return {"type": "string", "enum": list(args)}
            if all(isinstance(arg, bool) for arg in args):
                return {"type": "boolean", "enum": list(args)}
            if all(isinstance(arg, int) and not isinstance(arg, bool) for arg in args):
                return {"type": "integer", "enum": list(args)}
            if all(isinstance(arg, (int, float)) and not isinstance(arg, bool) for arg in args):
                return {"type": "number", "enum": list(args)}
            return {"enum": list(args)}
        if origin in (list, tuple, set, frozenset):
            item_schema = _schema_for_arg(args[0]) if args else {"type": "string"}
            return {"type": "array", "items": item_schema}
        if origin is dict:
            key_schema = _schema_for_arg(args[0]) if args else {"type": "string"}
            value_schema = _schema_for_arg(args[1]) if len(args) > 1 else {"type": "string"}
            return {
                "type": "object",
                "propertyNames": key_schema,
                "additionalProperties": value_schema,
            }
        if _is_union_origin(origin):
            schemas = [schema for arg in args if (schema := _schema_for_arg(arg))]
            return {"anyOf": schemas} if schemas else None

    if isinstance(type_hint, type) and issubclass(type_hint, Enum):
        return {"type": "string", "enum": [member.value for member in type_hint]}

    if isinstance(type_hint, type) and _is_pydantic_model(type_hint):
        return _inline_pydantic_schema(type_hint.model_json_schema())  # type: ignore[arg-type]

    if hasattr(type_hint, "__dataclass_fields__"):
        properties: dict[str, Any] = {}
        required: list[str] = []
        for field in dataclass_fields(type_hint):  # type: ignore[arg-type]
            field_schema = _schema_for_arg(field.type)
            if (
                field_schema
                and "anyOf" in field_schema
                and any(sub.get("type") == "null" for sub in field_schema["anyOf"])
            ):
                non_null = next(
                    (
                        sub["type"]
                        for sub in field_schema["anyOf"]
                        if sub.get("type") not in (None, "null")
                    ),
                    None,
                )
                if non_null is not None:
                    field_schema = dict(field_schema)
                    field_schema["type"] = non_null
                    field_schema.pop("anyOf")
            else:
                required.append(field.name)
            if field_schema:
                properties[field.name] = field_schema
        result: ToolSchemaDocument = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if required:
            result["required"] = required
        return result

    if type_hint is dict:
        return {"type": "object", "additionalProperties": True}

    try:
        name = type_hint.__name__
    except AttributeError:
        return None
    result = {"type": _json_type_for_py_type(name)}
    if result["type"] == "object":
        result["properties"] = {}
        result["additionalProperties"] = False
    return result


def _is_pydantic_model(type_hint: type) -> bool:
    try:
        from pydantic import BaseModel

        return issubclass(type_hint, BaseModel)
    except ImportError:
        return False


def _is_runtime_context(type_hint: Any) -> bool:
    """Whether an annotation is (or contains) a ``RuntimeToolContext`` injection."""
    if type_hint is RuntimeToolContext:
        return True
    origin = get_origin(type_hint)
    if _is_union_origin(origin):
        return any(_is_runtime_context(arg) for arg in get_args(type_hint))
    return False


def _docstring_description(tool_callable: ToolCallable) -> str:
    docstring = getdoc(tool_callable)
    if not docstring:
        return ""
    parsed = parse_docstring(docstring)
    lines: list[str] = []
    if parsed.short_description:
        lines.append(parsed.short_description)
    if parsed.long_description:
        lines.extend(parsed.long_description.split("\n"))
    return "\n".join(lines)


def _docstring_param_descriptions(tool_callable: ToolCallable) -> dict[str, str]:
    docstring = getdoc(tool_callable)
    if not docstring:
        return {}
    descriptions: dict[str, str] = {}
    try:
        for param in parse_docstring(docstring).params:
            if param.type_name:
                descriptions[param.arg_name] = f"({param.type_name}) {param.description or ''}"
            else:
                descriptions[param.arg_name] = param.description or ""
    except Exception:
        return {}
    return descriptions


def render_tool_schema(
    tool: ToolRuntimeSpec | ToolCallable,
    *,
    strict: bool = False,
    description: str | None = None,
) -> ToolSchemaDocument:
    """Render the model-facing tool schema document for a tool callable.

    Accepts a `ToolRuntimeSpec` (its callable and name are used; metadata is
    honored only through the `strict`/`description` arguments) or a plain
    callable. Passing `description` replaces the docstring-derived description
    entirely, mirroring how a harness advertises a declared description.
    """
    tool_callable: ToolCallable = tool.callable if isinstance(tool, ToolRuntimeSpec) else tool
    tool_name: str = getattr(tool_callable, "__name__", "tool")

    signature_params = list(signature(tool_callable).parameters)
    type_hints = get_type_hints(tool_callable, include_extras=True)
    schema_hints = {
        name: type_hints.get(name)
        for name in signature_params
        if name not in _CONTAINER_PARAMS and not _is_runtime_context(type_hints.get(name))
    }

    docstring_params = _docstring_param_descriptions(tool_callable)

    parameters: ToolSchemaDocument = {"type": "object", "properties": {}}
    if strict:
        parameters["additionalProperties"] = False

    for param_name, type_hint in schema_hints.items():
        if param_name == "return":
            continue
        try:
            origin = get_origin(type_hint)
            args = get_args(type_hint)
            if origin is Union and len(args) == 2 and any(arg is type(None) for arg in args):
                type_hint = next(arg for arg in args if arg is not type(None))
            arg_schema: ToolSchemaDocument | dict[str, Any] | None = (
                _schema_for_arg(type_hint) if type_hint else None
            )
        except Exception:
            continue
        if arg_schema is None:
            continue
        if docstring_params.get(param_name):
            arg_schema = dict(arg_schema)
            arg_schema["description"] = docstring_params[param_name]
        parameters["properties"][param_name] = arg_schema

    properties = parameters["properties"]
    if strict:
        parameters["required"] = [name for name in properties if name not in _CONTAINER_PARAMS]
    else:
        fn_signature = signature(tool_callable)
        context_injected = {
            name for name in fn_signature.parameters if _is_runtime_context(type_hints.get(name))
        }
        candidates = [
            name
            for name, param in fn_signature.parameters.items()
            if name not in _CONTAINER_PARAMS
            and name not in context_injected
            and param.default is Parameter.empty
        ]
        parameters["required"] = [name for name in candidates if name in properties]

    resolved_description = (
        description if description is not None else _docstring_description(tool_callable)
    )
    return {
        "name": tool_name,
        "description": resolved_description,
        "parameters": parameters,
    }


def render_spec_schema(spec: ToolRuntimeSpec) -> ToolSchemaDocument:
    """Render the runtime-facing schema a harness should advertise for a spec.

    Honors the spec's declared metadata: `spec.strict` (strict parameters) and
    `spec.description` (declared description, falling back to the docstring).
    """
    return render_tool_schema(spec.callable, strict=spec.strict, description=spec.description)
