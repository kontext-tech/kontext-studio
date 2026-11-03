"""Structural checks between the committed contract and the generated models.

The repository only verifies that regenerating produces no diff. These tests
check the *shape* of what was generated: every module imports, every contract
component maps to a class, field aliases match the wire names, required-ness
matches the spec, and enum values are complete. They are cheap enough to run in
the normal Python test job and catch generator-version drift beyond formatting.
"""

from __future__ import annotations

import importlib
import json
from enum import Enum
from pathlib import Path

import pytest
from pydantic import RootModel

import kontext.schema as schema

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = REPO_ROOT / "ts/schema/src/schemas/kontext.models.openapi.json"
GENERATED_DIR = Path(schema.__file__).parent / "_generated"

# Components deliberately suppressed by the generator's `--type-overrides`: they
# are represented by an existing type (`ChartSpec`, `StrictStr`) rather than a
# generated class.
SUPPRESSED_COMPONENTS = {"ChartBlockData", "IFormFile"}

# Contract component name -> generated class name, where they differ.
RENAMED_CLASSES = {"BaseModel": "KontextBaseModel"}


@pytest.fixture(scope="module")
def spec_components() -> dict[str, dict]:
    document = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    return document["components"]["schemas"]


def _class_for(component: str) -> type | None:
    return getattr(schema, RENAMED_CLASSES.get(component, component), None)


def test_generated_modules_live_in_the_subpackage_only() -> None:
    package_dir = Path(schema.__file__).parent
    flat_python = {path.name for path in package_dir.glob("*.py") if path.name != "__init__.py"}

    assert GENERATED_DIR.is_dir()
    assert flat_python == {"base.py", "policies.py"}
    assert (GENERATED_DIR / "__init__.py").is_file()


def test_every_generated_module_imports() -> None:
    modules = sorted(path.stem for path in GENERATED_DIR.glob("*.py") if path.stem != "__init__")
    assert modules

    for module in modules:
        importlib.import_module(f"kontext.schema._generated.{module}")


def test_all_exports_resolve() -> None:
    assert "SchemaModel" in schema.__all__
    assert len(schema.__all__) == len(set(schema.__all__))

    missing = [name for name in schema.__all__ if not hasattr(schema, name)]
    assert missing == []


def test_every_component_maps_to_a_class(spec_components: dict[str, dict]) -> None:
    missing = {name for name in spec_components if _class_for(name) is None}

    assert missing == SUPPRESSED_COMPONENTS


def test_object_models_match_spec_fields(spec_components: dict[str, dict]) -> None:
    mismatches: list[str] = []

    for name, component in spec_components.items():
        if component.get("type") != "object" or "enum" in component:
            continue

        model = _class_for(name)
        assert model is not None, name

        properties = component.get("properties") or {}
        required = set(component.get("required") or [])
        fields = {
            field.alias or field_name: field for field_name, field in model.model_fields.items()
        }

        if set(fields) != set(properties):
            mismatches.append(
                f"{name}: properties={sorted(set(properties) - set(fields))} "
                f"fields={sorted(set(fields) - set(properties))}"
            )
            continue

        for prop_name, field in fields.items():
            # A schema default makes the field optional on input for this
            # contract (Zod `.default()`), regardless of `required`.
            expected_required = prop_name in required and "default" not in properties[prop_name]
            if field.is_required() != expected_required:
                mismatches.append(
                    f"{name}.{prop_name}: "
                    f"required={field.is_required()} expected={expected_required}"
                )

    assert mismatches == []


def test_object_models_match_spec_additional_properties(
    spec_components: dict[str, dict],
) -> None:
    mismatches: list[str] = []

    for name, component in spec_components.items():
        if component.get("type") != "object" or "enum" in component:
            continue

        model = _class_for(name)
        assert model is not None, name

        expected = "allow" if component.get("additionalProperties") is True else "forbid"
        actual = model.model_config.get("extra")
        if actual != expected:
            mismatches.append(f"{name}: extra={actual} expected={expected}")

    assert mismatches == []


def test_enums_match_spec_values(spec_components: dict[str, dict]) -> None:
    mismatches: list[str] = []

    for name, component in spec_components.items():
        if "enum" not in component:
            continue

        model = _class_for(name)
        assert model is not None, name
        assert isinstance(model, type) and issubclass(model, Enum), name

        generated = {member.value for member in model}
        expected = set(component["enum"])
        if generated != expected:
            mismatches.append(
                f"{name}: missing={sorted(expected - generated)} "
                f"extra={sorted(generated - expected)}"
            )

    assert mismatches == []


def test_unions_are_root_models(spec_components: dict[str, dict]) -> None:
    for name, component in spec_components.items():
        if "oneOf" not in component and "anyOf" not in component:
            continue

        model = _class_for(name)
        assert model is not None, name
        assert issubclass(model, RootModel), name
