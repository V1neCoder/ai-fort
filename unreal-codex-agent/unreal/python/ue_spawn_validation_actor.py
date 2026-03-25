from __future__ import annotations

import json
from typing import Any

from ue_runtime import load_unreal

unreal = load_unreal(("EditorAssetLibrary", "EditorLevelLibrary", "Vector", "Rotator"))


def _ensure_unreal() -> None:
    if unreal is None:
        raise RuntimeError("Unreal Python API is not available in this environment.")


def _vector_from_list(values: list[float] | None) -> Any:
    values = values or [0.0, 0.0, 0.0]
    return unreal.Vector(float(values[0]), float(values[1]), float(values[2]))


def _rotator_from_list(values: list[float] | None) -> Any:
    values = values or [0.0, 0.0, 0.0]
    return unreal.Rotator(float(values[1]), float(values[2]), float(values[0]))


def spawn_validation_actor(
    asset_path: str,
    actor_label: str = "UCA_ValidationActor",
    location: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
) -> dict[str, Any]:
    _ensure_unreal()
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None:
        return {"status": "not_found", "asset_path": asset_path}
    loc = _vector_from_list(location)
    rot = _rotator_from_list(rotation)
    try:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(asset, loc, rot)
    except Exception as exc:
        return {"status": "error", "asset_path": asset_path, "reason": f"spawn_actor_from_object failed: {exc}"}
    if actor is None:
        return {"status": "error", "asset_path": asset_path, "reason": "Spawn returned None."}
    try:
        actor.set_actor_label(actor_label)
    except Exception:
        pass
    if scale and len(scale) == 3:
        try:
            actor.set_actor_scale3d(unreal.Vector(float(scale[0]), float(scale[1]), float(scale[2])))
        except Exception:
            pass
    return {"status": "ok", "asset_path": asset_path, "actor_label": actor_label, "actor_name": actor.get_name()}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "reason": "usage: ue_spawn_validation_actor.py <asset_path>"}))
    else:
        try:
            result = spawn_validation_actor(sys.argv[1])
        except Exception as exc:
            result = {"status": "error", "asset_path": sys.argv[1], "reason": str(exc)}
        print(json.dumps(result, indent=2))
