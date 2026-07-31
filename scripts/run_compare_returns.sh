#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/workflow_common.sh"

require_trunk_lineage
PYTHON_BIN="$REPO_DIR/.venvs/core/bin/python"
require_file "$PYTHON_BIN"

args=("$@")
if has_arg "--input" "${args[@]}" || has_arg "-i" "${args[@]}"; then
  if ! has_arg "--output" "${args[@]}" && ! has_arg "-o" "${args[@]}"; then
    timestamp="$(date +%Y%m%d-%H%M%S)"
    args+=("--output" "$REPO_DIR/outputs/returns/report-$timestamp.md")
  fi
fi

cd "$REPO_DIR"
exec "$PYTHON_BIN" "$REPO_DIR/core/backtests/compare_returns.py" "${args[@]}"
