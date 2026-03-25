from __future__ import annotations

import json
from typing import Any

from ue_runtime import load_unreal

unreal = load_unreal(("EditorAssetLibrary",))


def _bbox_to_dimensions(box: Any) -> tuple[dict[str, float], dict[str, Any]]:
    try:
        min_v = box.min
        max_v = box.max
        width = float(max_v.x - min_v.x)
        depth = float(max_v.y - min_v.y)
        height = float(max_v.z - min_v.z)
        return (
            {"width": round(width, 3), "depth": round(depth, 3), "height": round(height, 3)},
            {
                "origin": [
                    round((min_v.x + max_v.x) / 2.0, 3),
                    round((min_v.y + max_v.y) / 2.0, 3),
                    round((min_v.z + max_v.z) / 2.0, 3),
                ],
                "box_extent": [round(width / 2.0, 3), round(depth / 2.0, 3), round(height / 2.0, 3)],
            },
        )
    except Exception as exc:
        raise RuntimeError(f"Unable to convert bounding box: {exc}") from exc


def _load_asset(asset_path: str) -> Any:
    if unreal is None:
        raise RuntimeError("Unreal Python API is not available in this environment.")
    return unreal.EditorAssetLibrary.load_asset(asset_path)


def measure_asset(asset_path: str) -> dict[str, Any]:
    asset = _load_asset(asset_path)
    if asset is None:
        return {"status": "not_found", "asset_path": asset_path}
    try:
        if hasattr(asset, "get_bounding_box"):
            box = asset.get_bounding_box()
            dims, bounds = _bbox_to_dimensions(box)
            return {
                "status": "ok",
                "asset_path": asset_path,
                "dimensions_cm": dims,
                "bounds_cm": bounds,
                "method": "asset.get_bounding_box",
            }
    except Exception:
        pass
    try:
        if hasattr(asset, "get_bounds"):
            bounds_obj = asset.get_bounds()
            origin = bounds_obj.origin
            extent = bounds_obj.box_extent
            dims = {
                "width": round(float(extent.x) * 2.0, 3),
                "depth": round(float(extent.y) * 2.0, 3),
                "height": round(float(extent.z) * 2.0, 3),
            }
            bounds = {
                "origin": [round(float(origin.x), 3), round(float(origin.y), 3), round(float(origin.z), 3)],
                "box_extent": [round(float(extent.x), 3), round(float(extent.y), 3), round(float(extent.z), 3)],
            }
            return {
                "status": "ok",
                "asset_path": asset_path,
                "dimensions_cm": dims,
                "bounds_cm": bounds,
                "method": "asset.get_bounds",
            }
    except Exception:
        pass
    return {"status": "unsupported", "asset_path": asset_path, "reason": "No supported bounds method found on loaded asset."}


if __name__ == "__main__":
    import sys

    asset_path = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        result = measure_asset(asset_path)
    except Exception as exc:
        result = {"status": "error", "asset_path": asset_path, "reason": str(exc)}
    print(json.dumps(result, indent=2))
