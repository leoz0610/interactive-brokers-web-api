#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/workflow_common.sh"

require_trunk_lineage
PYTHON_BIN="$REPO_DIR/.venvs/cnbc/bin/python"
require_file "$PYTHON_BIN"

cd "$REPO_DIR/cnbc_extractor"
exec "$PYTHON_BIN" "$REPO_DIR/cnbc_extractor/main.py" "$@"
