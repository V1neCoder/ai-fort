#!/usr/bin/env bash
set -euo pipefail

UNREAL_PROJECT_PATH="${1:-${UNREAL_PROJECT_PATH:-${UEFN_PROJECT_PATH:-}}}"
PLUGIN_FOLDER_NAME="${PREFABRICATOR_PLUGIN_FOLDER_NAME:-Prefabricator}"
REPO_URL="${PREFABRICATOR_REPO_URL:-https://github.com/unknownworlds/prefabricator-ue5}"

if [[ -z "$UNREAL_PROJECT_PATH" ]]; then
  echo "Provide the Unreal project path as the first argument or set UNREAL_PROJECT_PATH. This helper is for a desktop Unreal reference project, not the primary UEFN runtime." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to install Prefabricator UE5." >&2
  exit 1
fi

PROJECT_FILE="$(cd "$(dirname "$UNREAL_PROJECT_PATH")" && pwd)/$(basename "$UNREAL_PROJECT_PATH")"
if [[ "$PROJECT_FILE" == *.uefnproject ]]; then
  echo "Prefabricator installation is reference-only here and expects a desktop Unreal .uproject, not a .uefnproject." >&2
  exit 1
fi
PROJECT_DIR="$(dirname "$PROJECT_FILE")"
PLUGINS_DIR="$PROJECT_DIR/Plugins"
TARGET_DIR="$PLUGINS_DIR/$PLUGIN_FOLDER_NAME"

mkdir -p "$PLUGINS_DIR"

if [[ -d "$TARGET_DIR/.git" ]]; then
  echo "Updating existing Prefabricator plugin at $TARGET_DIR"
  git -C "$TARGET_DIR" pull --ff-only
elif [[ -e "$TARGET_DIR" ]]; then
  echo "Target plugin directory already exists and is not a git repository: $TARGET_DIR" >&2
  exit 1
else
  echo "Cloning Prefabricator UE5 into $TARGET_DIR"
  git clone "$REPO_URL" "$TARGET_DIR"
fi

MANIFEST="$(find "$TARGET_DIR" -name '*.uplugin' | head -n 1 || true)"
if [[ -z "$MANIFEST" ]]; then
  echo "No .uplugin file was found after installation." >&2
  exit 1
fi

echo
echo "Installed Prefabricator UE5:"
echo "  Project: $PROJECT_FILE"
echo "  Plugin:  $TARGET_DIR"
echo "  Manifest: $MANIFEST"
echo
echo "Next steps:"
echo "  1. Open the desktop Unreal reference project."
echo "  2. Enable the Prefabricator plugin if Unreal prompts you."
echo "  3. Rebuild the project if Unreal requests a compile."
