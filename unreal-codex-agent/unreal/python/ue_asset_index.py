from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ue_runtime import load_unreal

unreal = load_unreal(("AssetRegistryHelpers",))


DEFAULT_OUTPUT = Path("./data/catalog/raw_assets.jsonl")
DEFAULT_ROOT_PATHS = ["/Game"]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _asset_class_name(asset_data: Any) -> str:
    try:
        class_path = getattr(asset_data, "asset_class_path", None)
        if class_path is not None and hasattr(class_path, "asset_name"):
            return str(class_path.asset_name)
    except Exception:
        pass
    for attr in ("asset_class", "class_name"):
        try:
            value = getattr(asset_data, attr, None)
            if value:
                return str(value)
        except Exception:
            pass
    return "Unknown"


def _string_attr(obj: Any, name: str, default: str = "") -> str:
    try:
        value = getattr(obj, name, None)
        return str(value) if value is not None else default
    except Exception:
        return default


def _asset_tags(asset_data: Any) -> dict[str, Any]:
    tags: dict[str, Any] = {}
    try:
        raw = getattr(asset_data, "tags_and_values", None)
        if raw is None:
            return tags
        if hasattr(raw, "keys"):
            for key in raw.keys():
                try:
                    tags[str(key)] = str(raw[key])
                except Exception:
                    tags[str(key)] = ""
            return tags
        if isinstance(raw, dict):
            for key, value in raw.items():
                tags[str(key)] = str(value)
            return tags
    except Exception:
        pass
    return tags


def _asset_data_to_record(asset_data: Any) -> dict[str, Any]:
    asset_path = _string_attr(asset_data, "object_path")
    package_path = _string_attr(asset_data, "package_path")
    asset_name = _string_attr(asset_data, "asset_name")
    if not asset_name and asset_path:
        asset_name = asset_path.split("/")[-1]
    return {
        "asset_path": asset_path,
        "package_path": package_path,
        "asset_name": asset_name,
        "asset_class": _asset_class_name(asset_data),
        "native_class": _asset_class_name(asset_data),
        "tags": _asset_tags(asset_data),
        "metadata_tags": {},
        "dimensions_cm": {},
        "bounds_cm": {},
        "collision_verified": None,
        "validator_passed": None,
        "pivot_suspect": False,
        "preview_set": {},
    }


def scan_asset_registry(root_paths: list[str] | None = None, recursive: bool = True) -> list[dict[str, Any]]:
    if unreal is None:
        raise RuntimeError("Unreal Python API is not available in this environment.")
    roots = root_paths or DEFAULT_ROOT_PATHS
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    records: list[dict[str, Any]] = []
    for root in roots:
        try:
            asset_data_list = registry.get_assets_by_path(root, recursive=recursive)
        except TypeError:
            asset_data_list = registry.get_assets_by_path(root, recursive)
        for asset_data in asset_data_list:
            records.append(_asset_data_to_record(asset_data))
    return records


def run(output_path: str | Path = DEFAULT_OUTPUT, root_paths: list[str] | None = None) -> dict[str, Any]:
    out = Path(output_path)
    records = scan_asset_registry(root_paths=root_paths)
    _write_jsonl(out, records)
    return {"status": "ok", "output_path": out.as_posix(), "count": len(records)}


if __name__ == "__main__":
    try:
        result = run()
    except Exception as exc:
        result = {"status": "error", "reason": str(exc)}
    print(json.dumps(result, indent=2))
