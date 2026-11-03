#!/bin/bash
# Bootstrap-safe pre-push Commitizen check.
#
# Runs Commitizen through `uv run` so the check does not depend on a globally
# installed `cz` binary. Commitizen is declared in the root pyproject.toml
# dependency group `dev`.

set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed; skipping Commitizen branch check."
    echo "Install it from https://docs.astral.sh/uv/ to enable this hook."
    exit 0
fi

BASE_REF=""

if git rev-parse --verify --quiet origin/HEAD >/dev/null; then
    BASE_REF="origin/HEAD"
elif UPSTREAM_REF=$(git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>/dev/null); then
    BASE_REF="$UPSTREAM_REF"
elif git rev-parse --verify --quiet origin/main >/dev/null; then
    BASE_REF="origin/main"
elif git rev-parse --verify --quiet origin/master >/dev/null; then
    BASE_REF="origin/master"
else
    echo "No remote default branch found yet; skipping Commitizen branch check for initial push."
    exit 0
fi

COMMITS_AHEAD=$(git rev-list --count "${BASE_REF}..HEAD")
if [ "$COMMITS_AHEAD" = "0" ]; then
    echo "No local commits ahead of ${BASE_REF}; skipping Commitizen branch check."
    exit 0
fi

uv run cz check --rev-range "${BASE_REF}..HEAD"
