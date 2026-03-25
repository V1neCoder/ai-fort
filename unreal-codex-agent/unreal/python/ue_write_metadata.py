from __future__ import annotations

import json
from typing import Any

from ue_runtime import load_unreal

unreal = load_unreal(("EditorAssetLibrary",))


def _ensure_unreal() -> None:
    if unreal is None:
        raise RuntimeError("Unreal Python API is not available in this environment.")


def _load_asset(asset_path: str) -> Any:
    _ensure_unreal()
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Unable to load asset: {asset_path}")
    return asset


def _serialize_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, bool, int, float)):
        return json.dumps(value)
    return str(value)


def set_metadata(asset_path: str, metadata: dict[str, Any]) -> dict[str, Any]:
    _ensure_unreal()
    asset = _load_asset(asset_path)
    subsystem = None
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    except Exception:
        subsystem = None
    applied: dict[str, str] = {}
    for key, value in metadata.items():
        text_value = _serialize_value(value)
        try:
            if subsystem and hasattr(subsystem, "set_metadata_tag"):
                subsystem.set_metadata_tag(asset, key, text_value)
            elif hasattr(unreal.EditorAssetLibrary, "set_metadata_tag"):
                unreal.EditorAssetLibrary.set_metadata_tag(asset, key, text_value)
            else:
                raise RuntimeError("No metadata write function is available in this UE environment.")
            applied[key] = text_value
        except Exception as exc:
            applied[key] = f"ERROR:{exc}"
    try:
        unreal.EditorAssetLibrary.save_loaded_asset(asset)
    except Exception:
        pass
    return {"status": "ok", "asset_path": asset_path, "applied": applied}


def get_metadata(asset_path: str, keys: list[str] | None = None) -> dict[str, Any]:
    _ensure_unreal()
    asset = _load_asset(asset_path)
    subsystem = None
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    except Exception:
        subsystem = None
    results: dict[str, Any] = {}
    for key in keys or []:
        try:
            if subsystem and hasattr(subsystem, "get_metadata_tag"):
                results[key] = subsystem.get_metadata_tag(asset, key)
            elif hasattr(unreal.EditorAssetLibrary, "get_metadata_tag"):
                results[key] = unreal.EditorAssetLibrary.get_metadata_tag(asset, key)
            else:
                results[key] = None
        except Exception:
            results[key] = None
    return {"status": "ok", "asset_path": asset_path, "metadata": results}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "reason": "usage: ue_write_metadata.py <asset_path> <json_metadata>"}))
    else:
        asset_path = sys.argv[1]
        metadata = json.loads(sys.argv[2])
        try:
            result = set_metadata(asset_path, metadata)
        except Exception as exc:
            result = {"status": "error", "asset_path": asset_path, "reason": str(exc)}
        print(json.dumps(result, indent=2))
