#!/bin/bash
# Regenerate the committed TypeScript API types from the OpenAPI spec at
# ts/schema/src/schemas/kontext.api.openapi.json.
#
# The generated `paths` / `components` types are committed to the repository
# (no artifact tarball) and consumed by @kontext-tech/common through
# openapi-fetch. The spec is exported from the Zod contracts in ts/schema, so
# run `pnpm run generate:models` first when the contracts changed.
#
# Requirements: node/pnpm (workspace deps).

set -euo pipefail

# shellcheck source=./lib/generator-common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/generator-common.sh"

LABS_DIR="$(generator_repo_root)"

cd "$LABS_DIR"

require_command node "Install Node.js (see .nvmrc)."
require_command pnpm "Install pnpm >= 10 (corepack enable pnpm)."

SPEC="$LABS_DIR/ts/schema/src/schemas/kontext.api.openapi.json"
OUT="$LABS_DIR/ts/schema/src/generated/api.ts"

if [ ! -f "$SPEC" ]; then
    echo "❌ API OpenAPI spec not found at $SPEC" >&2
    exit 1
fi

echo "🔄 Generating TypeScript API types..."

pnpm --filter @kontext-tech/schema exec openapi-typescript "$SPEC" --output "$OUT"

echo "✅ Generated API types: ts/schema/src/generated/api.ts"
