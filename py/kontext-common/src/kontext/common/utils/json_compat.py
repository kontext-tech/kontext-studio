"""Tolerant validation of JSON persisted by older schema versions.

Generated contract models use ``extra="forbid"`` so inbound API requests are
validated strictly. That strictness is wrong for data we ourselves wrote to the
database in an earlier release: when a field is later removed from the schema,
the stored JSON still carries the old key and re-validating it would raise
``extra_forbidden`` (this is exactly what broke ``GET /catalog/connections``
after ``supportsRelationshipDiscovery`` was removed).

:func:`model_validate_stored` reads such payloads by pruning keys the target
model does not know about, recursively for nested models, collections, and
mappings. Unknown keys are dropped rather than rejected; known keys (matched by
field name or alias) are validated normally.
"""

from __future__ import annotations

import types
from collections.abc import Mapping, Sequence
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

_UNION_ORIGINS = (Union, types.UnionType)


def model_validate_stored[ModelT: BaseModel](model_cls: type[ModelT], data: Any) -> ModelT:
    """Validate stored JSON into ``model_cls``, tolerating unknown legacy keys.

    Unlike ``model_cls.model_validate`` this never fails because a removed
    field is still present in persisted data. Missing/invalid *known* fields
    are still subject to normal validation.
    """
    if isinstance(data, model_cls):
        return data
    if isinstance(data, BaseModel):
        data = data.model_dump(by_alias=True)
    return model_cls.model_validate(_prune_for_model(model_cls, data))


def _prune_for_model(model_cls: type[BaseModel], data: Any) -> Any:
    if not isinstance(data, Mapping):
        return data

    fields_by_key: dict[str, Any] = {}
    for name, field_info in model_cls.model_fields.items():
        fields_by_key[name] = field_info
        if field_info.alias:
            fields_by_key[field_info.alias] = field_info

    pruned: dict[str, Any] = {}
    for key, value in data.items():
        field_info = fields_by_key.get(key)
        if field_info is None:
            # Unknown key from an older schema: drop it.
            continue
        pruned[key] = _prune_value(field_info.annotation, value)
    return pruned


def _prune_value(annotation: Any, value: Any) -> Any:
    annotation = _unwrap_optional(annotation)
    origin = get_origin(annotation)

    if origin in (list, set, tuple, frozenset):
        item_type = _first_arg(annotation)
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            return [_prune_value(item_type, item) for item in value]
        return value

    if origin in (dict, Mapping):
        args = get_args(annotation)
        value_type = args[1] if len(args) == 2 else Any
        if isinstance(value, Mapping):
            return {key: _prune_value(value_type, item) for key, item in value.items()}
        return value

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _prune_for_model(annotation, value)

    return value


def _unwrap_optional(annotation: Any) -> Any:
    """Strip ``Optional``/``None`` from a union so its payload type is visible."""
    if get_origin(annotation) in _UNION_ORIGINS:
        non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def _first_arg(annotation: Any) -> Any:
    args = get_args(annotation)
    return _unwrap_optional(args[0]) if args else Any


__all__ = ["model_validate_stored"]
