#!/bin/bash
# Build shared packages for local development
# Usage: ./scripts/build-shared-packages.sh

set -e

echo "🔄 Building shared packages for local development..."

# Determine project directory
SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
LABS_DIR=$(dirname "$SCRIPT_DIR")

cd "$LABS_DIR"

if [ ! -d "$LABS_DIR/node_modules" ]; then
    echo "❌ Dependencies are not installed. Run 'pnpm install' from the repo root first."
    exit 1
fi

echo "🔄 Validating workspace package graph..."
pnpm run validate:workspace-graph

# Build schemas (depends on nothing)
echo "🔄 Building schemas..."
if [ -d "ts/schema" ]; then
    pnpm --filter @kontext-tech/schema build
fi

echo "🔄 Building shared build configuration..."
if [ -d "ts/build-config" ]; then
    pnpm --filter @kontext-tech/build-config build
fi

# Build shared packages in dependency order
echo "🔄 Building shared packages..."

# Build common shared foundations
echo "🔄 Building common..."
if [ -d "ts/common" ]; then
    pnpm --filter @kontext-tech/common build
fi

# Sync common public assets (logos, icons, manifests) to the app only.
echo "🔄 Syncing app assets..."
node ./scripts/sync-app-assets.mjs

echo "🔄 Building remaining shared packages with topological workspace ordering..."
pnpm -r \
    --workspace-concurrency=1 \
    --filter "./ts/**" \
    --filter "!@kontext-tech/build-config" \
    --filter "!@kontext-tech/schema" \
    --filter "!@kontext-tech/common" \
    build

echo "✅ All shared packages built successfully!"
echo ""
echo "Next steps:"
echo "1. Run: pnpm run dev:app to start the app"
echo "2. Run: pnpm run dev:notebook to start the notebook demo"
echo "3. Or run: pnpm run build to build the workspace"
