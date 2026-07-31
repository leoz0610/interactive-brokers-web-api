#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/workflow_common.sh"

find_modern_python() {
  local candidate version_ok
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      version_ok="$($candidate -c 'import sys; print(int(sys.version_info >= (3, 10)))')"
      if [[ "$version_ok" == "1" ]]; then
        command -v "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(find_modern_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3.10+ is required. Install it, then rerun this setup." >&2
  exit 2
fi

require_trunk_lineage
mkdir -p "$REPO_DIR/.venvs"

if [[ ! -x "$REPO_DIR/.venvs/core/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$REPO_DIR/.venvs/core"
fi
"$REPO_DIR/.venvs/core/bin/python" -m pip install --upgrade pip
"$REPO_DIR/.venvs/core/bin/python" -m pip install -r "$REPO_DIR/core/requirements.txt"

if [[ ! -x "$REPO_DIR/.venvs/cnbc/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$REPO_DIR/.venvs/cnbc"
fi
"$REPO_DIR/.venvs/cnbc/bin/python" -m pip install --upgrade pip
"$REPO_DIR/.venvs/cnbc/bin/python" -m pip install -r "$REPO_DIR/cnbc_extractor/requirements.txt"

echo "Setup complete using $PYTHON_BIN."
