#!/usr/bin/env bash
# Test runner for the Kontext Python workspace.
#
# Delegates to pytest with the workspace configuration in the root
# pyproject.toml (`testpaths = ["py/*/tests"]`), which collects every
# package suite. Extra arguments are forwarded to pytest, e.g.
#   bash scripts/run-python-tests.sh -m "not slow"
#   bash scripts/run-python-tests.sh py/kontext-agentic/tests

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "🧪 Running Python workspace tests..."
exec uv run pytest "$@"
