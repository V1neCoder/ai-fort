#!/usr/bin/env bash
set -euo pipefail

GOAL="Build a polished room that fits the task."
CYCLES=1
SESSION_NAME=""
BOOTSTRAP_IF_MISSING=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --goal)
      GOAL="$2"
      shift 2
      ;;
    --cycles)
      CYCLES="$2"
      shift 2
      ;;
    --session-name)
      SESSION_NAME="$2"
      shift 2
      ;;
    --bootstrap-if-missing)
      BOOTSTRAP_IF_MISSING=true
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$REPO_ROOT/.venv"
PYTHON_EXE="$VENV_PATH/bin/python"
ACTIVATE_SCRIPT="$VENV_PATH/bin/activate"

if [[ ! -f "$ACTIVATE_SCRIPT" ]]; then
  if [[ "$BOOTSTRAP_IF_MISSING" == "true" ]]; then
    "$REPO_ROOT/scripts/bootstrap.sh"
    if [[ ! -f "$ACTIVATE_SCRIPT" ]]; then
      echo "Bootstrap completed but the virtual environment activation script is still missing." >&2
      exit 1
    fi
  else
    if command -v python >/dev/null 2>&1; then
      PYTHON_EXE="$(command -v python)"
    elif command -v python3 >/dev/null 2>&1; then
      PYTHON_EXE="$(command -v python3)"
    else
      echo "Virtual environment not found and no python executable is available on PATH." >&2
      exit 1
    fi
  fi
fi

if [[ -f "$ACTIVATE_SCRIPT" ]]; then
  # shellcheck disable=SC1090
  source "$ACTIVATE_SCRIPT"
fi

mkdir -p \
  "$REPO_ROOT/data/catalog" \
  "$REPO_ROOT/data/sessions" \
  "$REPO_ROOT/data/previews" \
  "$REPO_ROOT/data/uefn_bridge/captures" \
  "$REPO_ROOT/data/cache/latest_shortlists" \
  "$REPO_ROOT/data/cache/latest_scene_packets" \
  "$REPO_ROOT/uefn/verse/generated" \
  "$REPO_ROOT/logs"

ARGS=(
  -m apps.orchestrator.main
  start
  --repo-root "$REPO_ROOT"
  --goal "$GOAL"
  --cycles "$CYCLES"
)

if [[ -n "$SESSION_NAME" ]]; then
  ARGS+=(--session-name "$SESSION_NAME")
fi

echo "Starting agent..."
echo "Goal: $GOAL"
"$PYTHON_EXE" "${ARGS[@]}"
