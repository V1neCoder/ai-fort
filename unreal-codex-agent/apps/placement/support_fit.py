from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_triplet(value: Any, default: list[float] | None = None) -> list[float]:
    fallback = list(default or [0.0, 0.0, 0.0])
    if isinstance(value, dict):
        return [
            _safe_float(value.get("x"), fallback[0]),
            _safe_float(value.get("y"), fallback[1]),
            _safe_float(value.get("z"), fallback[2]),
        ]
    if isinstance(value, (list, tuple)):
        padded = list(value[:3]) + fallback[len(value[:3]) :]
        return [
            _safe_float(padded[0], fallback[0]),
            _safe_float(padded[1], fallback[1]),
            _safe_float(padded[2], fallback[2]),
        ]
    return fallback


def actor_bottom_z(actor_payload: dict[str, Any]) -> float | None:
    bounds = dict(actor_payload.get("bounds_cm") or {})
    origin = bounds.get("origin")
    extent = bounds.get("box_extent")
    if not isinstance(origin, list) or not isinstance(extent, list) or len(origin) < 3 or len(extent) < 3:
        return None
    return float(origin[2]) - float(extent[2])


def _is_floor_like_mount_type(mount_type: Any) -> bool:
    normalized = str(mount_type or "").strip().lower()
    if not normalized:
        return True
    return normalized in {"floor", "surface", "exterior_ground"}


def support_anchor_for_scene(scene_state: dict[str, Any]) -> tuple[str | None, list[float] | None, str]:
    placement_targets = dict(scene_state.get("placement_targets") or {})
    dirty_bounds = dict(scene_state.get("dirty_bounds") or {})
    for anchor_key in ("surface_anchor", "ground_anchor", "landscape_anchor"):
        value = placement_targets.get(anchor_key)
        if isinstance(value, list) and len(value) >= 3:
            support_kind = str(
                placement_targets.get("support_surface_kind")
                or dirty_bounds.get("support_surface_kind")
                or ("landscape" if anchor_key != "surface_anchor" else "support_surface")
            )
            return anchor_key, _safe_triplet(value), support_kind
        value = dirty_bounds.get(anchor_key)
        if isinstance(value, list) and len(value) >= 3:
            support_kind = str(
                dirty_bounds.get("support_surface_kind")
                or ("landscape" if anchor_key != "surface_anchor" else "support_surface")
            )
            return anchor_key, _safe_triplet(value), support_kind
    return None, None, ""


def classify_support_surface_fit(
    delta_cm: float,
    *,
    on_surface_tolerance_cm: float = 2.0,
    slight_offset_tolerance_cm: float = 6.0,
) -> dict[str, Any]:
    delta = round(_safe_float(delta_cm, 0.0), 3)
    absolute = abs(delta)
    if absolute <= on_surface_tolerance_cm:
        state = "on_surface"
    elif absolute <= slight_offset_tolerance_cm:
        state = "slightly_offset"
    elif delta < 0.0:
        state = "embedded"
    else:
        state = "floating"
    return {
        "support_surface_delta_cm": delta,
        "support_surface_fit_state": state,
        "support_surface_fit_ok": state in {"on_surface", "slightly_offset"},
    }


def derive_support_surface_fit(
    *,
    scene_state: dict[str, Any],
    active_actor: dict[str, Any],
    mount_type: str | None = None,
    on_surface_tolerance_cm: float = 2.0,
    slight_offset_tolerance_cm: float = 6.0,
) -> dict[str, Any]:
    anchor_type, support_anchor, support_kind = support_anchor_for_scene(scene_state)
    if anchor_type is None or support_anchor is None:
        return {}
    if not _is_floor_like_mount_type(mount_type):
        support_z = float(support_anchor[2])
        bottom_z = actor_bottom_z(active_actor)
        return {
            "support_surface_delta_cm": round((_safe_float(bottom_z, support_z) - support_z), 3),
            "support_surface_fit_state": "not_applicable",
            "support_surface_fit_ok": True,
            "support_fit_skipped": "mount_type_not_floor_like",
            "support_anchor_type": anchor_type,
            "support_surface_kind": support_kind,
            "support_surface_z": round(support_z, 3),
            "actor_bottom_z": round(_safe_float(bottom_z, support_z), 3),
        }
    bottom_z = actor_bottom_z(active_actor)
    if bottom_z is None:
        return {}
    support_z = float(support_anchor[2])
    details = classify_support_surface_fit(
        bottom_z - support_z,
        on_surface_tolerance_cm=on_surface_tolerance_cm,
        slight_offset_tolerance_cm=slight_offset_tolerance_cm,
    )
    details.update(
        {
            "support_anchor_type": anchor_type,
            "support_surface_kind": support_kind,
            "support_surface_z": round(support_z, 3),
            "actor_bottom_z": round(float(bottom_z), 3),
        }
    )
    return details
