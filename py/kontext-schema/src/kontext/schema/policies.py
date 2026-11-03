"""Hand-written cross-model policies for the generated schema package.

Generated modules live in :mod:`kontext.schema._generated` and inherit
:class:`~kontext.schema.base.SchemaModel` unless a contract policy needs more.
Two policies cannot be expressed in OpenAPI, so ``generate-models.sh`` maps the
affected models to the bases below with ``--base-class-map``:

* OKF timestamps must keep a UTC offset when a bundle carries a date-only value
  (``okf_attestation``, ``okf_concept``, ``okf_provenance_actor``,
  ``okf_source``).
* Update requests must reject explicit JSON nulls for fields that are
  omit-only, i.e. optional on the wire but not clearable
  (``update_chat_session_request``).

Keeping the policy here instead of rewriting generated source means a
regeneration is a plain ``rm -rf _generated`` with no string patching.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import model_validator

from .base import SchemaModel


class UtcModel(SchemaModel):
    """SchemaModel that stamps naive datetimes as UTC after validation.

    A bundle written by an older tool (or an OKF v0.1 author) may carry a
    date-only value such as ``2026-12-31``, which Pydantic parses into a naive
    ``datetime``. Serialized back out it would lose its offset, and the shared
    Zod schema (``z.string().datetime({ offset: true })``) rejects that in the
    browser, so normalize on the way in.
    """

    @model_validator(mode="after")
    def _stamp_naive_datetimes_as_utc(self) -> UtcModel:
        for field_name in type(self).model_fields:
            value = self.__dict__.get(field_name)
            if isinstance(value, datetime) and value.tzinfo is None:
                # Bypass ``validate_assignment``: the value is already
                # validated, and assigning through the field would re-enter
                # this validator.
                object.__setattr__(self, field_name, value.replace(tzinfo=UTC))
        return self


class OmitOnlyUpdateModel(SchemaModel):
    """Reject explicit JSON nulls for omit-only optional fields.

    The generator types these fields as optional, so Pydantic would accept
    ``null`` as a way to clear them. On the wire ``null`` is ambiguous with
    "not provided", so only omission is allowed.
    """

    omit_only_fields: ClassVar[tuple[str, ...]] = (
        "sessionName",
        "modelSelectionId",
        "querySessionId",
        "defaultCatalogConnectionId",
        "defaultNamespace",
        "defaultEntityId",
        "engineType",
        "pythonExecutionApprovalMode",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        for field_name in cls.omit_only_fields:
            if field_name in value and value[field_name] is None:
                raise ValueError(field_name)
        return value


__all__ = ["OmitOnlyUpdateModel", "UtcModel"]
