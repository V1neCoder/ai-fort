from __future__ import annotations

import json
from typing import Any

from ue_runtime import load_unreal

unreal = load_unreal(("EditorAssetLibrary", "EditorLevelLibrary", "Vector", "Rotator"))


def _ensure_unreal() -> None:
    if unreal is None:
        raise RuntimeError("Unreal Python API is not available in this environment.")


def _vector(values: list[float] | None, default: list[float] | None = None) -> Any:
    vals = values or default or [0.0, 0.0, 0.0]
    return unreal.Vector(float(vals[0]), float(vals[1]), float(vals[2]))


def _rotator(values: list[float] | None, default: list[float] | None = None) -> Any:
    vals = values or default or [0.0, 0.0, 0.0]
    return unreal.Rotator(float(vals[1]), float(vals[2]), float(vals[0]))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _snap_value(value: float, step: float) -> float:
    if step <= 0:
        return value
    return round(value / step) * step


def _apply_transform_hints(transform: dict[str, Any], placement_hint: dict[str, Any] | None) -> dict[str, Any]:
    if not placement_hint:
        return transform
    normalized = dict(transform or {})
    snap_grid_cm = _safe_float(placement_hint.get("snap_grid_cm"), 0.0)
    yaw_step = _safe_float(placement_hint.get("preferred_yaw_step_deg"), 0.0)
    pitch_step = _safe_float(placement_hint.get("preferred_pitch_step_deg"), 0.0)
    lock_roll_to_zero = bool(placement_hint.get("lock_roll_to_zero", False))

    location = normalized.get("location")
    if isinstance(location, list) and len(location) == 3 and snap_grid_cm > 0:
        normalized["location"] = [_snap_value(_safe_float(value), snap_grid_cm) for value in location]

    rotation = normalized.get("rotation")
    if isinstance(rotation, list) and len(rotation) == 3:
        roll, pitch, yaw = [_safe_float(value) for value in rotation]
        if pitch_step > 0:
            pitch = _snap_value(pitch, pitch_step)
        if yaw_step > 0:
            yaw = _snap_value(yaw, yaw_step)
        if lock_roll_to_zero:
            roll = 0.0
        normalized["rotation"] = [roll, pitch, yaw]

    scale = normalized.get("scale")
    if isinstance(scale, list) and len(scale) == 3 and bool(placement_hint.get("requires_uniform_scale", False)):
        scalar = sum(_safe_float(value, 1.0) for value in scale) / 3.0
        normalized["scale"] = [scalar, scalar, scalar]
    return normalized


def _find_actor_by_label(label: str | None) -> Any | None:
    if not label:
        return None
    try:
        for actor in unreal.EditorLevelLibrary.get_all_level_actors():
            if actor.get_actor_label() == label:
                return actor
    except Exception:
        pass
    return None


def _target_label_from_action(action_payload: dict[str, Any]) -> str | None:
    return action_payload.get("target_actor_label") or action_payload.get("actor_label") or action_payload.get("target_label") or action_payload.get("label")


def _spawn_asset(action_payload: dict[str, Any]) -> dict[str, Any]:
    asset_path = action_payload.get("asset_path")
    if not asset_path:
        return {"status": "error", "reason": "place_asset requires asset_path"}
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None:
        return {"status": "not_found", "reason": f"Unable to load asset: {asset_path}"}
    transform = _apply_transform_hints(action_payload.get("transform", {}) or {}, action_payload.get("placement_hint"))
    actor = unreal.EditorLevelLibrary.spawn_actor_from_object(
        asset,
        _vector(transform.get("location"), [0.0, 0.0, 0.0]),
        _rotator(transform.get("rotation"), [0.0, 0.0, 0.0]),
    )
    if actor is None:
        return {"status": "error", "reason": "Spawn returned None"}
    if transform.get("scale"):
        try:
            actor.set_actor_scale3d(_vector(transform.get("scale"), [1.0, 1.0, 1.0]))
        except Exception:
            pass
    label = action_payload.get("target_actor_label") or action_payload.get("spawn_label")
    if label:
        try:
            actor.set_actor_label(label)
        except Exception:
            pass
    return {
        "status": "ok",
        "action": "place_asset",
        "actor_name": actor.get_name(),
        "actor_label": actor.get_actor_label(),
        "asset_path": asset_path,
    }


def _move_actor(action_payload: dict[str, Any]) -> dict[str, Any]:
    actor = _find_actor_by_label(_target_label_from_action(action_payload))
    if actor is None:
        return {"status": "not_found", "reason": "Target actor not found for move_actor"}
    transform = _apply_transform_hints(action_payload.get("transform", {}) or {}, action_payload.get("placement_hint"))
    location = transform.get("location")
    if not location:
        delta = action_payload.get("delta_cm")
        if delta and len(delta) == 3:
            current = actor.get_actor_location()
            location = [current.x + float(delta[0]), current.y + float(delta[1]), current.z + float(delta[2])]
    if not location:
        return {"status": "error", "reason": "move_actor requires transform.location or delta_cm"}
    actor.set_actor_location(_vector(location))
    return {"status": "ok", "action": "move_actor", "actor_label": actor.get_actor_label()}


def _rotate_actor(action_payload: dict[str, Any]) -> dict[str, Any]:
    actor = _find_actor_by_label(_target_label_from_action(action_payload))
    if actor is None:
        return {"status": "not_found", "reason": "Target actor not found for rotate_actor"}
    transform = _apply_transform_hints(action_payload.get("transform", {}) or {}, action_payload.get("placement_hint"))
    rotation = transform.get("rotation")
    if not rotation:
        return {"status": "error", "reason": "rotate_actor requires transform.rotation"}
    actor.set_actor_rotation(_rotator(rotation))
    return {"status": "ok", "action": "rotate_actor", "actor_label": actor.get_actor_label()}


def _scale_actor(action_payload: dict[str, Any]) -> dict[str, Any]:
    actor = _find_actor_by_label(_target_label_from_action(action_payload))
    if actor is None:
        return {"status": "not_found", "reason": "Target actor not found for scale_actor"}
    transform = _apply_transform_hints(action_payload.get("transform", {}) or {}, action_payload.get("placement_hint"))
    scale = transform.get("scale")
    if not scale:
        return {"status": "error", "reason": "scale_actor requires transform.scale"}
    actor.set_actor_scale3d(_vector(scale, [1.0, 1.0, 1.0]))
    return {"status": "ok", "action": "scale_actor", "actor_label": actor.get_actor_label()}


def _delete_actor(action_payload: dict[str, Any]) -> dict[str, Any]:
    actor = _find_actor_by_label(_target_label_from_action(action_payload))
    if actor is None:
        return {"status": "not_found", "reason": "Target actor not found for delete_actor"}
    label = actor.get_actor_label()
    unreal.EditorLevelLibrary.destroy_actor(actor)
    return {"status": "ok", "action": "delete_actor", "actor_label": label}


def _replace_asset(action_payload: dict[str, Any]) -> dict[str, Any]:
    actor = _find_actor_by_label(_target_label_from_action(action_payload))
    if actor is None:
        return {"status": "not_found", "reason": "Target actor not found for replace_asset"}
    asset_path = action_payload.get("asset_path")
    if not asset_path:
        return {"status": "error", "reason": "replace_asset requires asset_path"}
    loc = actor.get_actor_location()
    rot = actor.get_actor_rotation()
    scl = actor.get_actor_scale3d()
    label = actor.get_actor_label()
    unreal.EditorLevelLibrary.destroy_actor(actor)
    new_action = {
        "action": "place_asset",
        "asset_path": asset_path,
        "target_actor_label": label,
        "transform": {
            "location": [loc.x, loc.y, loc.z],
            "rotation": [rot.roll, rot.pitch, rot.yaw],
            "scale": [scl.x, scl.y, scl.z],
        },
    }
    return _spawn_asset(new_action)


def apply_action_payload(action_payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_unreal()
    action = action_payload.get("action", "no_op")
    if action == "no_op":
        return {"status": "ok", "action": "no_op"}
    if action == "place_asset":
        return _spawn_asset(action_payload)
    if action == "move_actor":
        return _move_actor(action_payload)
    if action == "rotate_actor":
        return _rotate_actor(action_payload)
    if action == "scale_actor":
        return _scale_actor(action_payload)
    if action == "replace_asset":
        return _replace_asset(action_payload)
    if action == "delete_actor":
        return _delete_actor(action_payload)
    return {"status": "unsupported", "action": action, "reason": f"Unsupported action '{action}'"}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "reason": "usage: ue_apply_edit.py <action_json>"}))
    else:
        try:
            payload = json.loads(sys.argv[1])
            result = apply_action_payload(payload)
        except Exception as exc:
            result = {"status": "error", "reason": str(exc)}
        print(json.dumps(result, indent=2))
