#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../scripts/lib/generator-common.sh
source "$SCRIPT_DIR/../../../scripts/lib/generator-common.sh"

PROJECT_ROOT="$(generator_repo_root)"
GUARD_MANIFEST="$SCRIPT_DIR/generated-code-guards.json"

echo "🔎 Checking schema package contracts..."
pnpm --filter @kontext-tech/schema build
pnpm --filter @kontext-tech/schema run check:contracts

echo "🔎 Checking generated Python schema models..."
uv run python -m compileall -q "$PROJECT_ROOT/py/kontext-schema/src/kontext/schema"

# Guarded checks are data-driven from generated-code-guards.json so that adding
# a required schema or a forbidden legacy file does not require editing this
# script.
PROJECT_ROOT="$PROJECT_ROOT" GUARD_MANIFEST="$GUARD_MANIFEST" uv run python - <<'PY'
import json
import os
import sys
from pathlib import Path

manifest = json.loads(Path(os.environ["GUARD_MANIFEST"]).read_text())
project_root = Path(os.environ["PROJECT_ROOT"])

failures: list[str] = []

for rel_path in manifest.get("forbiddenGeneratedFiles", []):
    if (project_root / rel_path).exists():
        failures.append(f"forbidden generated file present: {rel_path}")

exports = manifest.get("requiredPythonSchemaExports", [])
if exports:
    try:
        import kontext.schema as schema

        for name in exports:
            value = getattr(schema, name, None)
            if value is None:
                failures.append(f"missing kontext.schema export: {name}")
            elif getattr(value, "__name__", name) != name:
                failures.append(
                    f"kontext.schema.{name} has unexpected __name__ {getattr(value, '__name__', None)!r}"
                )
    except Exception as error:  # noqa: BLE001
        failures.append(f"failed to import kontext.schema: {error}")

if failures:
    for failure in failures:
        print(f"❌ {failure}", file=sys.stderr)
    sys.exit(1)

print(
    f"ok {len(exports)} required exports and "
    f"{len(manifest.get('forbiddenGeneratedFiles', []))} forbidden-file checks passed"
)
PY

if [ ! -f "$PROJECT_ROOT/ts/schema/src/generated/api.ts" ]; then
  echo "❌ Generated TypeScript API types are missing. Run: pnpm run generate:api-types" >&2
  exit 1
fi
echo "✅ Generated TypeScript API types are present"

echo "✅ Generator smoke checks passed"
