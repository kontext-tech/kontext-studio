#!/bin/bash

# Kontext Pydantic model generation
#
# 1. Export the Zod-first contract to the committed models OpenAPI document.
# 2. Generate Pydantic v2 models with datamodel-codegen, mapping the models
#    that need contract policies to hand-written bases.
# 3. Format with the repository-pinned Ruff.
#
# Pre-requisites: `pnpm install` and `uv sync --group codegen`.
#
# Usage: ./ts/schema/scripts/generate-models.sh

set -e # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../scripts/lib/generator-common.sh
source "$SCRIPT_DIR/../../../scripts/lib/generator-common.sh"

PROJECT_ROOT="$(generator_repo_root)"
SCHEMAS_DIR="$PROJECT_ROOT/ts/schema"
SCHEMA_FILE="$SCHEMAS_DIR/src/schemas/kontext.models.openapi.json"
OUTPUT_DIR="$PROJECT_ROOT/py/kontext-schema"
SCHEMA_PY_DIR="$OUTPUT_DIR/src/kontext/schema"
GEN_DIR="$SCHEMA_PY_DIR/_generated"

echo "🚀 Starting Kontext schema refresh and Pydantic model generation..."
echo "📁 Project Root: $PROJECT_ROOT"

verify_generator_prerequisites "$PROJECT_ROOT"

# Step 1: refresh the committed models spec from the Zod source of truth.
echo ""
echo "📋 Step 1: Refreshing models schema from @kontext-tech/schema..."
cd "$SCHEMAS_DIR"
pnpm run refresh-schemas

if [ ! -f "$SCHEMA_FILE" ]; then
    echo "❌ Error: Models OpenAPI schema not found at $SCHEMA_FILE"
    exit 1
fi

# Step 2: generate into the dedicated subpackage.
#
# Hand-written files live beside it (`base.py`, `policies.py`, `__init__.py`,
# `py.typed`) and are never touched: regenerating is a plain `rm -rf
# _generated`, with no keep-list exceptions and no post-generation patching.
echo ""
echo "🐍 Step 2: Generating Pydantic models (datamodel-codegen)..."
mkdir -p "$SCHEMA_PY_DIR"

echo "🧹 Cleaning previous generated Python files at $GEN_DIR"
rm -rf "$GEN_DIR"

# Flag rationale:
# - `--snake-case-field` + explicit per-field aliases: unlike the previous
#   `alias_generator=to_camel`, this keeps already-snake_case contract fields
#   (OKF `stale_after`, `last_modified`, ...) on the wire correctly.
# - `--use-default`: Zod `.default()` means optional input; without this flag
#   every defaulted field becomes required.
# - `--type-mappings` replaces the bytearray/UUID/EmailStr post-process passes.
# - `--type-overrides` keeps `ChartBlockData` as its `ChartSpec` target instead
#   of introducing a RootModel wrapper (matches the previous contract).
# - `--base-class-map` routes the four OKF models and the update-chat-session
#   request through the hand-written policy bases in `kontext.schema.policies`
#   (UTC normalization and omit-only null rejection) instead of patching the
#   generated source afterwards.
# - `--disable-timestamp`: keeps committed output reproducible for the CI
#   freshness check.
cd "$PROJECT_ROOT"
uv run --group codegen datamodel-codegen \
  --input "$SCHEMA_FILE" \
  --input-file-type openapi \
  --output "$GEN_DIR" \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.12 \
  --target-pydantic-version 2.14 \
  --snake-case-field \
  --use-annotated \
  --use-schema-description \
  --capitalise-enum-members \
  --use-single-value-enum-as-const \
  --use-default \
  --use-default-kwarg \
  --output-datetime-class datetime \
  --base-class kontext.schema.base.SchemaModel \
  --base-class-map '{"OkfAttestation":"kontext.schema.policies.UtcModel","OkfConcept":"kontext.schema.policies.UtcModel","OkfProvenanceActor":"kontext.schema.policies.UtcModel","OkfSource":"kontext.schema.policies.UtcModel","UpdateChatSessionRequest":"kontext.schema.policies.OmitOnlyUpdateModel"}' \
  --model-name-map '{"BaseModel":"KontextBaseModel"}' \
  --naming-strategy primary-first \
  --type-mappings string+uuid=string string+binary=string string+email=string \
  --type-overrides '{"ChartBlockData":"kontext.schema._generated.chart_spec.ChartSpec","ReadyFileId":"pydantic.StrictStr","FileId":"pydantic.StrictStr","JobRunId":"pydantic.StrictStr","IFormFile":"pydantic.StrictStr"}' \
  --module-split-mode single \
  --use-exact-imports \
  --all-exports-scope recursive \
  --all-exports-collision-strategy minimal-prefix \
  --disable-timestamp \
  --formatters builtin

# Step 3: format with the pinned Ruff. Explicit file arguments bypass Ruff's
# `extend-exclude` for generated code (a directory argument would be pruned).
echo ""
echo "🧹 Step 3: Formatting generated Python models..."
shopt -s nullglob
GENERATED_PY_FILES=("$GEN_DIR"/*.py)
shopt -u nullglob
if [ ${#GENERATED_PY_FILES[@]} -eq 0 ]; then
  echo "❌ Error: No generated Python files found in $GEN_DIR"
  exit 1
fi
uv run ruff check --fix --select I --no-cache "${GENERATED_PY_FILES[@]}" || true
uv run ruff format --no-cache "${GENERATED_PY_FILES[@]}"
echo "✅ Formatted ${#GENERATED_PY_FILES[@]} generated files"

echo ""
echo "🎉 ---"
echo "✅ All steps completed successfully!"
echo "🐍 The kontext-schema package is up-to-date."
echo "   Run 'uv sync' in the project root to install/update it in your environment."
echo "---"
