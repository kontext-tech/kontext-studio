"""Hand-written base model for the generated Kontext schema package.

This module is **retained** across regeneration: the generator owns only
``_generated/``, while this file and ``__init__.py`` are hand-written. It
carries the cross-model policy that a schema generator cannot express once per
contract:

* camelCase wire aliases are emitted explicitly per field, so the base only
  enables population by Python field name;
* ``validate_assignment`` used to be repeated in every generated
  ``ConfigDict``;
* ``schema`` is a legitimate contract field name, so Pydantic's protected
  namespace must be disabled;
* ``additional_properties`` keeps the read API of the pre-migration generated
  models for open objects (``additionalProperties: true``), which now use
  Pydantic's ``model_extra`` instead of a hand-generated field;
* ``to_dict`` / ``from_dict`` / ``to_json`` / ``from_json`` are thin
  compatibility shims for call sites that predate ``model_dump`` /
  ``model_validate``.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    """Shared configuration and compatibility helpers for contract models."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        protected_namespaces=(),
    )

    @property
    def additional_properties(self) -> dict[str, Any]:
        """Unknown keys accepted by an open model (``additionalProperties``)."""
        return dict(self.model_extra or {})

    def to_dict(self) -> dict[str, Any]:
        """Return the camelCase wire representation of the model.

        Mirrors the previous generated helper: ``None`` is omitted unless it was
        set explicitly, and unknown keys of open models are flattened to the top
        level.
        """
        data = self.model_dump(by_alias=True, exclude_none=True)
        fields = type(self).model_fields
        for name in self.model_fields_set:
            value = getattr(self, name)
            if value is not None:
                continue
            field = fields.get(name)
            # Declared fields use their wire alias; extra keys keep their name.
            data[(field.alias or name) if field is not None else name] = None
        return data

    def to_json(self) -> str:
        """Return the wire JSON representation, omitting unset fields."""
        return self.model_dump_json(by_alias=True, exclude_unset=True)

    @classmethod
    def from_dict(cls, obj: Any) -> Self:
        """Create an instance from a camelCase or Python-named mapping."""
        return cls.model_validate(obj)

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Create an instance from a wire JSON document."""
        return cls.model_validate_json(json_str)


__all__ = ["SchemaModel"]
