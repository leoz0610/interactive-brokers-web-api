#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TRUNK_BRANCH="customized-changes"

require_trunk_lineage() {
  local branch
  branch="$(git -C "$REPO_DIR" branch --show-current)"
  if [[ "$branch" == "main" ]]; then
    echo "Refusing to run from 'main'; use '$TRUNK_BRANCH' or a feature branch based on it." >&2
    exit 2
  fi
  if ! git -C "$REPO_DIR" merge-base --is-ancestor "$TRUNK_BRANCH" HEAD; then
    echo "Refusing to run: '$branch' is not based on '$TRUNK_BRANCH'." >&2
    exit 2
  fi
}

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "Required file not found: $1" >&2
    exit 2
  fi
}

has_arg() {
  local wanted="$1"
  shift
  local arg
  for arg in "$@"; do
    if [[ "$arg" == "$wanted" ]]; then
      return 0
    fi
  done
  return 1
}
