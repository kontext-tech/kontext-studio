#!/usr/bin/env bash
# Create a plain, drag-to-Applications DMG without Finder/AppleScript.
# Tauri's built-in DMG bundler styles the window through Finder, which times
# out in headless CI sessions.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="$(node -p "require('$ROOT/desktop/src-tauri/tauri.conf.json').version")"
HOST_ARCH="$(uname -m)"
ARCH="${1:-$HOST_ARCH}"

case "$ARCH" in
   arm64 | aarch64) SUFFIX="arm64" ;;
   x86_64 | x64) SUFFIX="x64" ;;
   *) SUFFIX="$ARCH" ;;
esac

APP="$ROOT/desktop/src-tauri/target/release/bundle/macos/Kontext Studio.app"
OUT_DIR="$ROOT/dist"
DMG="$OUT_DIR/Kontext-Studio-${VERSION}-macOS-${SUFFIX}.dmg"

if [ ! -d "$APP" ]; then
   echo "Missing app bundle: $APP" >&2
   exit 1
fi

mkdir -p "$OUT_DIR"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG"
hdiutil create \
   -volname "Kontext Studio" \
   -srcfolder "$STAGE" \
   -ov \
   -format UDZO \
   "$DMG"

echo "Created $DMG"
