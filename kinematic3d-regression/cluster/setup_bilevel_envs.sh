#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGRESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASELINES_DIR="$(cd "$REGRESSION_DIR/.." && pwd)"
source "$REGRESSION_DIR/revisions.sh"

if [[ -z "${KINDER_REGRESSION_ROOT:-}" ]]; then
  echo "Set KINDER_REGRESSION_ROOT to an explicit cluster storage path." >&2
  exit 2
fi

PYTHON_BIN="${KINDER_REGRESSION_PYTHON:-python3}"
SOURCE_DIR="$KINDER_REGRESSION_ROOT/source"
WORKTREE_DIR="$KINDER_REGRESSION_ROOT/worktrees"
VENV_DIR="$KINDER_REGRESSION_ROOT/venvs"
MANIFEST_DIR="$KINDER_REGRESSION_ROOT/manifests"
KINDER_REPO="$SOURCE_DIR/kindergarden"

mkdir -p "$SOURCE_DIR" "$WORKTREE_DIR" "$VENV_DIR" "$MANIFEST_DIR"

if [[ ! -d "$KINDER_REPO/.git" ]]; then
  git clone https://github.com/Princeton-Robot-Planning-and-Learning/kindergarden.git \
    "$KINDER_REPO"
fi

git -C "$KINDER_REPO" fetch origin

for label in A0 A1 A2 A3 A4; do
  revision="$(get_kindergarden_revision "$label")"
  worktree="$WORKTREE_DIR/kindergarden-$label"
  venv="$VENV_DIR/bilevel-$label"

  if [[ ! -d "$worktree/.git" && ! -f "$worktree/.git" ]]; then
    git -C "$KINDER_REPO" worktree add --detach "$worktree" "$revision"
  fi

  expected_revision="$(git -C "$KINDER_REPO" rev-parse "$revision")"
  actual_revision="$(git -C "$worktree" rev-parse HEAD)"
  if [[ "$actual_revision" != "$expected_revision" ]]; then
    echo "$worktree is at $actual_revision, expected $expected_revision" >&2
    exit 2
  fi

  if [[ ! -x "$venv/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$venv"
  fi

  "$venv/bin/python" -m pip install --upgrade pip
  "$venv/bin/python" -m pip install -e "$worktree"
  "$venv/bin/python" -m pip install \
    -e "$BASELINES_DIR/kinder-imitation-learning" \
    -e "$BASELINES_DIR/kinder-models" \
    -e "$BASELINES_DIR/kinder-bilevel-planning"
  "$venv/bin/python" -m pip freeze > "$MANIFEST_DIR/bilevel-$label-pip-freeze.txt"
  "$venv/bin/python" - <<PY
import kinder
print("$label", kinder.__file__)
PY
done

git -C "$BASELINES_DIR" rev-parse HEAD > "$MANIFEST_DIR/kinder-baselines-revision.txt"
