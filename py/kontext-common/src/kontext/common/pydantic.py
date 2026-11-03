"""Pydantic base models shared across Kontext Python packages."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel, to_pascal


class KontextBaseModel(BaseModel):
    """Base model for Kontext with flexible alias generation"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KontextBaseModel":
        """Create an instance from a dictionary"""
        return cls(**data)


class CamelCaseModel(KontextBaseModel):
    """Base model using camelCase aliases"""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        alias_generator=to_camel,
    )


class PascalModel(KontextBaseModel):
    """Base model using PascalCase aliases for external payloads."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        alias_generator=to_pascal,
    )
