#!/bin/bash

set -e

SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
LABS_DIR=$(dirname "$SCRIPT_DIR")

SHARED_PUBLIC="$LABS_DIR/ts/common/public"
SHARED_ASSETS="$LABS_DIR/ts/common/src/assets"
TARGET="$LABS_DIR/app/public"

echo "🔄 Syncing app assets..."

if [ -d "$SHARED_PUBLIC" ]; then
    mkdir -p "$TARGET"

    if [ -d "$SHARED_PUBLIC/icons" ]; then
        cp -R "$SHARED_PUBLIC/icons" "$TARGET/"
    fi

    mkdir -p "$TARGET/resources"
    cp "$SHARED_ASSETS"/logo* "$TARGET/resources/"
    rm -f "$TARGET"/logo*

    echo "✅ Synced to $TARGET"
else
    echo "⚠️  Warning: Shared public directory not found at $SHARED_PUBLIC"
fi

APP_DIST="$LABS_DIR/app/dist"
LABS_DIST_TARGET="$LABS_DIR/py/kontext-labs/src/kontext/labs/_app_dist"

if [ -d "$APP_DIST" ]; then
    echo "📦 Syncing built app/dist into kontext-studio package..."
    rm -rf "$LABS_DIST_TARGET"
    mkdir -p "$LABS_DIST_TARGET"
    cp -R "$APP_DIST"/* "$LABS_DIST_TARGET/"
    cp "$LABS_DIR/LICENSE" "$LABS_DIST_TARGET/LICENSE"
    cp "$LABS_DIR/THIRD_PARTY_NOTICES.md" "$LABS_DIST_TARGET/THIRD_PARTY_NOTICES.md"
    cp "$LABS_DIR/TERMS.md" "$LABS_DIST_TARGET/TERMS.md"
    cp "$LABS_DIR/PRIVACY.md" "$LABS_DIST_TARGET/PRIVACY.md"
    echo "✅ Synced app/dist to $LABS_DIST_TARGET"
else
    echo "ℹ️  Note: app/dist not built yet. Run 'pnpm --filter @kontext-labs/app build' to bundle frontend UI."
fi

echo "✨ Asset sync complete."
