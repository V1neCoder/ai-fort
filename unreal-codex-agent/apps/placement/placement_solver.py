from __future__ import annotations

from typing import Any

from apps.placement.managed_registry import default_identity_policy, default_managed_slot


MOUNT_COMPATIBILITY: dict[str, set[str]] = {
    "floor": {"floor", "surface"},
    "surface": {"surface", "floor"},
    "wall": {"wall", "opening", "corner"},
    "opening": {"opening", "wall", "corner"},
    "corner": {"corner", "wall", "opening"},
    "ceiling": {"ceiling"},
    "roof": {"roof"},
    "exterior_ground": {"exterior_ground", "floor"},
}

MOUNT_KEYWORDS: dict[str, set[str]] = {
    "floor": {"floor", "ground", "land", "landscape", "terrain", "foundation", "platform"},
    "surface": {"surface", "floor", "ground", "platform", "table", "shelf"},
    "exterior_ground": {"ground", "terrain", "landscape", "soil", "grass", "dirt"},
    "roof": {"roof", "rooftop", "ridge", "gable", "dormer", "shingle", "chimney", "eave"},
    "corner": {"corner", "inside_corner", "outside_corner", "elbow"},
    "opening": {"door", "window", "gate", "opening"},
    "wall": {"wall", "facade", "panel", "trim", "sconce"},
    "ceiling": {"ceiling", "fan", "pendant", "chandelier"},
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_triplet(value: Any, default: list[float]) -> list[float]:
    if isinstance(value, dict):
        return [
            _safe_float(value.get("x"), default[0]),
            _safe_float(value.get("y"), default[1]),
            _safe_float(value.get("z"), default[2]),
        ]
    if isinstance(value, (list, tuple)):
        padded = list(value[:3]) + default[len(value[:3]) :]
        return [
            _safe_float(padded[0], default[0]),
            _safe_float(padded[1], default[1]),
            _safe_float(padded[2], default[2]),
        ]
    return list(default)


def _snap_value(value: float, step: float) -> float:
    if step <= 0:
        return value
    return round(value / step) * step


def _snap_value_relative(value: float, step: float, origin: float) -> float:
    if step <= 0:
        return value
    return origin + round((value - origin) / step) * step


def _snap_angle(value: float, step: float) -> float:
    if step <= 0:
        return value
    snapped = _snap_value(value, step)
    while snapped > 180.0:
        snapped -= 360.0
    while snapped <= -180.0:
        snapped += 360.0
    return snapped


def _snap_angle_relative(value: float, step: float, reference: float) -> float:
    if step <= 0:
        return value
    snapped = _snap_angle(value - reference, step) + reference
    while snapped > 180.0:
        snapped -= 360.0
    while snapped <= -180.0:
        snapped += 360.0
    return snapped


def _normalize_action_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _placement_phase_for_action(action_name: str, incoming_hint: dict[str, Any]) -> str:
    explicit = str(incoming_hint.get("placement_phase") or "").strip().lower()
    if explicit in {"initial_place", "reposition", "reanchor"}:
        return explicit
    if action_name in {"move_actor", "set_transform", "rotate_actor", "scale_actor"}:
        return "reposition"
    return "initial_place"


def _snap_policy_for_phase(placement_phase: str, incoming_hint: dict[str, Any]) -> str:
    explicit = str(incoming_hint.get("snap_policy") or "").strip().lower()
    if explicit in {"initial_only", "force", "none"}:
        return explicit
    if placement_phase == "reanchor":
        return "force"
    if placement_phase == "reposition":
        return "none"
    return "initial_only"


def _support_reference_policy(incoming_hint: dict[str, Any]) -> str:
    explicit = str(incoming_hint.get("support_reference_policy") or "").strip().lower()
    if explicit in {"selected_first", "nearest_surface", "explicit_only"}:
        return explicit
    return "selected_first"


def _interference_policy(action_name: str, placement_phase: str, incoming_hint: dict[str, Any]) -> str:
    explicit = str(incoming_hint.get("interference_policy") or "").strip().lower()
    if explicit in {"avoid", "allow", "replace_managed"}:
        return explicit
    if placement_phase == "reposition" or action_name in {"move_actor", "set_transform", "rotate_actor", "scale_actor"}:
        return "allow"
    return "avoid"


def _duplicate_policy(action_name: str, incoming_hint: dict[str, Any]) -> str:
    explicit = str(incoming_hint.get("duplicate_policy") or "").strip().lower()
    if explicit in {"reuse", "cleanup_managed", "allow"}:
        return explicit
    if action_name == "place_asset":
        return "cleanup_managed"
    return "reuse"


def _should_snap_to_support(placement_phase: str, snap_policy: str) -> bool:
    return snap_policy == "force" or placement_phase == "initial_place"


def _tokenize_mount_hints(scene_state: dict[str, Any], dirty_zone: dict[str, Any] | None) -> set[str]:
    tokens: set[str] = set()
    candidates: list[str] = [str(scene_state.get("map_name") or ""), str(scene_state.get("room_type") or "")]
    if dirty_zone:
        candidates.extend(
            [
                str(dirty_zone.get("zone_type") or ""),
                str(dirty_zone.get("room_type") or ""),
            ]
        )
    for actor in scene_state.get("actors", []) or []:
        if not isinstance(actor, dict):
            continue
        candidates.extend(
            [
                str(actor.get("label") or ""),
                str(actor.get("asset_path") or ""),
                str(actor.get("actor_name") or ""),
                str(actor.get("class_name") or ""),
            ]
        )
    for raw in candidates:
        lowered = raw.lower().replace("/", " ").replace("\\", " ").replace("-", " ").replace("_", " ")
        tokens.update(part for part in lowered.split() if part)
    return tokens


def infer_expected_mount_type(scene_state: dict[str, Any], dirty_zone: dict[str, Any] | None = None) -> str:
    tokens = _tokenize_mount_hints(scene_state, dirty_zone)
    room_type = str((dirty_zone or {}).get("room_type") or scene_state.get("room_type") or "unknown").lower()
    shell_sensitive = bool((dirty_zone or {}).get("shell_sensitive", scene_state.get("shell_sensitive", False)))

    for mount_type in ("roof", "corner", "opening", "wall", "ceiling"):
        if tokens & MOUNT_KEYWORDS[mount_type]:
            return mount_type

    if room_type in {"rooftop"}:
        return "roof"
    if shell_sensitive:
        return "opening"
    if room_type in {"facade", "balcony", "patio"}:
        return "wall"
    return "floor"


def compatible_mount_types(expected_mount_type: str) -> set[str]:
    return set(MOUNT_COMPATIBILITY.get(expected_mount_type, {expected_mount_type}))


def placement_context(
    *,
    scene_state: dict[str, Any],
    dirty_zone: dict[str, Any] | None = None,
    asset_record: dict[str, Any] | None = None,
    action_name: str | None = None,
    incoming_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    incoming = dict(incoming_hint or {})
    expected_mount_type = infer_expected_mount_type(scene_state, dirty_zone)
    tags = (asset_record or {}).get("tags", {}) or {}
    rules = dict((asset_record or {}).get("placement_rules", {}) or {})
    mount_type = str(tags.get("mount_type") or expected_mount_type)
    placement_behavior = list(tags.get("placement_behavior") or [])
    bounds = ((dirty_zone or {}).get("bounds") if dirty_zone else None) or scene_state.get("dirty_bounds") or {}

    yaw_step = _safe_float(rules.get("preferred_yaw_step_deg"), 0.0)
    pitch_step = _safe_float(rules.get("preferred_pitch_step_deg"), 0.0)
    snap_grid_cm = _safe_float(rules.get("snap_grid_cm"), 0.0)

    if yaw_step <= 0:
        if mount_type in {"opening", "corner", "wall", "ceiling"}:
            yaw_step = 90.0
        elif mount_type == "roof":
            yaw_step = 45.0
    if pitch_step <= 0 and mount_type == "roof":
        pitch_step = 15.0
    if snap_grid_cm <= 0:
        if mount_type in {"opening", "corner", "roof"}:
            snap_grid_cm = 10.0
        elif mount_type in {"wall", "ceiling"}:
            snap_grid_cm = 5.0

    requires_uniform_scale = bool(rules.get("allow_nonuniform_scale", mount_type in {"opening", "corner", "roof"}) is False)
    anchor_preference = "center"
    support_kind = str(bounds.get("support_surface_kind") or "").strip().lower() if isinstance(bounds, dict) else ""
    support_level = int(_safe_float(bounds.get("support_level"), 0.0)) if isinstance(bounds, dict) else 0
    parent_support_actor = str(bounds.get("parent_support_actor") or bounds.get("support_actor_label") or "").strip() if isinstance(bounds, dict) else ""
    if mount_type in {"floor", "surface"}:
        anchor_preference = "ground_anchor" if support_kind == "landscape" else "surface_anchor"
    elif mount_type == "exterior_ground":
        anchor_preference = "ground_anchor"
    elif mount_type in {"opening", "wall"}:
        anchor_preference = "plane_center"
    elif mount_type == "corner":
        anchor_preference = "corner_anchor"
    elif mount_type in {"ceiling", "roof"}:
        anchor_preference = "top_center"
    placement_phase = _placement_phase_for_action(_normalize_action_name(action_name), incoming)
    snap_policy = _snap_policy_for_phase(placement_phase, incoming)
    normalized_action_name = _normalize_action_name(action_name)
    return {
        "expected_mount_type": expected_mount_type,
        "compatible_mount_types": sorted(compatible_mount_types(expected_mount_type)),
        "mount_type": mount_type,
        "placement_behavior": placement_behavior,
        "preferred_yaw_step_deg": yaw_step,
        "preferred_pitch_step_deg": pitch_step,
        "snap_grid_cm": snap_grid_cm,
        "lock_roll_to_zero": mount_type in {"floor", "wall", "opening", "corner", "roof"},
        "requires_uniform_scale": requires_uniform_scale,
        "placement_family": mount_type,
        "anchor_preference": anchor_preference,
        "support_surface_kind": support_kind,
        "support_level": support_level,
        "parent_support_actor": parent_support_actor,
        "placement_phase": placement_phase,
        "snap_policy": snap_policy,
        "support_reference_policy": _support_reference_policy(incoming),
        "interference_policy": _interference_policy(normalized_action_name, placement_phase, incoming),
        "duplicate_policy": _duplicate_policy(normalized_action_name, incoming),
        "reference_yaw_deg": _safe_float(bounds.get("reference_yaw_deg"), 0.0) if isinstance(bounds, dict) else 0.0,
        "reference_pitch_deg": _safe_float(bounds.get("reference_pitch_deg"), 0.0) if isinstance(bounds, dict) else 0.0,
        "reference_actor_label": str(bounds.get("reference_actor_label") or "") if isinstance(bounds, dict) else "",
        "support_actor_label": str(bounds.get("support_actor_label") or "") if isinstance(bounds, dict) else "",
        "support_actor_path": str(bounds.get("support_actor_path") or "") if isinstance(bounds, dict) else "",
        "anchor_point": _safe_triplet(bounds.get("anchor_point"), [0.0, 0.0, 0.0]) if isinstance(bounds, dict) and bounds.get("anchor_point") is not None else None,
        "surface_anchor": _safe_triplet(bounds.get("surface_anchor"), [0.0, 0.0, 0.0]) if isinstance(bounds, dict) and bounds.get("surface_anchor") is not None else None,
        "ground_anchor": _safe_triplet(bounds.get("ground_anchor"), [0.0, 0.0, 0.0]) if isinstance(bounds, dict) and bounds.get("ground_anchor") is not None else None,
        "landscape_anchor": _safe_triplet(bounds.get("landscape_anchor"), [0.0, 0.0, 0.0]) if isinstance(bounds, dict) and bounds.get("landscape_anchor") is not None else None,
        "plane_anchor": _safe_triplet(bounds.get("plane_anchor"), [0.0, 0.0, 0.0]) if isinstance(bounds, dict) and bounds.get("plane_anchor") is not None else None,
        "corner_anchor": _safe_triplet(bounds.get("corner_anchor"), [0.0, 0.0, 0.0]) if isinstance(bounds, dict) and bounds.get("corner_anchor") is not None else None,
    }


def _default_location(
    scene_state: dict[str, Any],
    dirty_zone: dict[str, Any] | None,
    mount_type: str,
) -> list[float]:
    bounds = ((dirty_zone or {}).get("bounds") if dirty_zone else None) or scene_state.get("dirty_bounds") or {}
    origin = _safe_triplet(bounds.get("origin"), [0.0, 0.0, 0.0]) if isinstance(bounds, dict) else [0.0, 0.0, 0.0]
    extent = _safe_triplet(bounds.get("box_extent"), [0.0, 0.0, 0.0]) if isinstance(bounds, dict) else [0.0, 0.0, 0.0]
    if isinstance(bounds, dict):
        if mount_type in {"floor", "surface"} and bounds.get("surface_anchor") is not None:
            return _safe_triplet(bounds.get("surface_anchor"), [origin[0], origin[1], origin[2] - extent[2]])
        if mount_type in {"floor", "surface", "exterior_ground"} and bounds.get("ground_anchor") is not None:
            return _safe_triplet(bounds.get("ground_anchor"), [origin[0], origin[1], origin[2] - extent[2]])
        if mount_type in {"floor", "surface", "exterior_ground"} and bounds.get("landscape_anchor") is not None:
            return _safe_triplet(bounds.get("landscape_anchor"), [origin[0], origin[1], origin[2] - extent[2]])
        if mount_type == "corner" and bounds.get("corner_anchor") is not None:
            return _safe_triplet(bounds.get("corner_anchor"), [origin[0], origin[1], origin[2] - extent[2]])
        if mount_type in {"wall", "opening"} and bounds.get("plane_anchor") is not None:
            return _safe_triplet(bounds.get("plane_anchor"), origin)
        if mount_type in {"ceiling", "roof"} and bounds.get("surface_anchor") is not None:
            return _safe_triplet(bounds.get("surface_anchor"), [origin[0], origin[1], origin[2] + extent[2]])
        if bounds.get("anchor_point") is not None:
            return _safe_triplet(bounds.get("anchor_point"), origin)

    if mount_type in {"floor", "surface", "exterior_ground", "corner"}:
        return [origin[0], origin[1], origin[2] - extent[2]]
    if mount_type in {"wall", "opening"}:
        return [origin[0], origin[1], origin[2]]
    if mount_type in {"ceiling", "roof"}:
        return [origin[0], origin[1], origin[2] + extent[2]]
    return origin


def _default_rotation(
    scene_state: dict[str, Any],
    dirty_zone: dict[str, Any] | None,
    mount_type: str,
) -> list[float]:
    bounds = ((dirty_zone or {}).get("bounds") if dirty_zone else None) or scene_state.get("dirty_bounds") or {}
    if not isinstance(bounds, dict):
        return [0.0, 0.0, 0.0]
    yaw = _safe_float(bounds.get("reference_yaw_deg"), 0.0)
    pitch = _safe_float(bounds.get("reference_pitch_deg"), 0.0) if mount_type == "roof" else 0.0
    return [0.0, pitch, yaw]


def _is_placeholder_triplet(values: Any) -> bool:
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        return True
    return all(abs(_safe_float(value, 0.0)) < 0.001 for value in values)


def normalize_action_payload(
    *,
    action_payload: dict[str, Any],
    scene_state: dict[str, Any],
    dirty_zone: dict[str, Any] | None = None,
    asset_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(action_payload or {})
    transform = dict(payload.get("transform") or {})
    incoming_hint = dict(payload.get("placement_hint") or {})
    context = placement_context(
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        asset_record=asset_record,
        action_name=str(payload.get("action") or ""),
        incoming_hint=incoming_hint,
    )
    raw_location = transform.get("location")
    raw_rotation = transform.get("rotation")
    raw_scale = transform.get("scale")
    location = _safe_triplet(raw_location, _default_location(scene_state, dirty_zone, context["mount_type"]))
    rotation = _safe_triplet(raw_rotation, _default_rotation(scene_state, dirty_zone, context["mount_type"]))
    scale = _safe_triplet(raw_scale, [1.0, 1.0, 1.0])
    bounds = ((dirty_zone or {}).get("bounds") if dirty_zone else None) or scene_state.get("dirty_bounds") or {}
    reference_anchor = None
    if isinstance(bounds, dict):
        if context["mount_type"] in {"floor", "surface"} and bounds.get("surface_anchor") is not None:
            reference_anchor = _safe_triplet(bounds.get("surface_anchor"), location)
        elif context["mount_type"] in {"floor", "surface", "exterior_ground"} and bounds.get("ground_anchor") is not None:
            reference_anchor = _safe_triplet(bounds.get("ground_anchor"), location)
        elif context["mount_type"] in {"floor", "surface", "exterior_ground"} and bounds.get("landscape_anchor") is not None:
            reference_anchor = _safe_triplet(bounds.get("landscape_anchor"), location)
        elif context["mount_type"] == "corner" and bounds.get("corner_anchor") is not None:
            reference_anchor = _safe_triplet(bounds.get("corner_anchor"), location)
        elif context["mount_type"] in {"wall", "opening"} and bounds.get("plane_anchor") is not None:
            reference_anchor = _safe_triplet(bounds.get("plane_anchor"), location)
        elif context["mount_type"] in {"ceiling", "roof"} and bounds.get("surface_anchor") is not None:
            reference_anchor = _safe_triplet(bounds.get("surface_anchor"), location)
        elif bounds.get("anchor_point") is not None:
            reference_anchor = _safe_triplet(bounds.get("anchor_point"), location)
    has_reference_yaw = isinstance(bounds, dict) and bounds.get("reference_yaw_deg") is not None
    has_reference_pitch = isinstance(bounds, dict) and bounds.get("reference_pitch_deg") is not None
    reference_yaw = _safe_float(bounds.get("reference_yaw_deg"), rotation[2]) if has_reference_yaw else rotation[2]
    reference_pitch = _safe_float(bounds.get("reference_pitch_deg"), rotation[1]) if has_reference_pitch else rotation[1]
    should_snap = _should_snap_to_support(
        str(context.get("placement_phase") or "initial_place"),
        str(context.get("snap_policy") or "initial_only"),
    )

    if should_snap and reference_anchor is not None and _is_placeholder_triplet(raw_location) and context["mount_type"] in {"floor", "surface", "exterior_ground", "wall", "opening", "corner", "roof", "ceiling"}:
        location = list(reference_anchor)
    if should_snap and _is_placeholder_triplet(raw_rotation) and context["mount_type"] in {"wall", "opening", "corner", "roof", "ceiling"}:
        rotation = _default_rotation(scene_state, dirty_zone, context["mount_type"])
    if _is_placeholder_triplet(raw_scale):
        scale = [1.0, 1.0, 1.0]

    grid = _safe_float(context.get("snap_grid_cm"), 0.0)
    if should_snap and grid > 0:
        if reference_anchor is not None:
            location = [_snap_value_relative(location[i], grid, reference_anchor[i]) for i in range(3)]
        else:
            location = [_snap_value(value, grid) for value in location]

    yaw_step = _safe_float(context.get("preferred_yaw_step_deg"), 0.0)
    pitch_step = _safe_float(context.get("preferred_pitch_step_deg"), 0.0)
    if should_snap and yaw_step > 0:
        rotation[2] = _snap_angle_relative(rotation[2], yaw_step, reference_yaw) if has_reference_yaw and context["mount_type"] in {"wall", "opening", "corner", "roof", "ceiling"} else _snap_angle(rotation[2], yaw_step)
    if should_snap and pitch_step > 0:
        rotation[1] = _snap_angle_relative(rotation[1], pitch_step, reference_pitch) if has_reference_pitch and context["mount_type"] == "roof" else _snap_angle(rotation[1], pitch_step)
    if should_snap and bool(context.get("lock_roll_to_zero", False)):
        rotation[0] = 0.0

    limits = dict((asset_record or {}).get("scale_limits", {}) or {})
    scale_min = _safe_float(limits.get("min"), 0.0)
    scale_max = _safe_float(limits.get("max"), 999.0)
    preferred = _safe_float(limits.get("preferred"), 1.0)
    clamped_scale = list(scale)
    if should_snap and scale_max >= scale_min:
        clamped_scale = [min(max(value, scale_min), scale_max) for value in scale]
        if bool(context.get("requires_uniform_scale", False)):
            scalar = sum(clamped_scale) / len(clamped_scale) if clamped_scale else preferred
            if scale_min > 0:
                scalar = min(max(scalar, scale_min), scale_max)
            clamped_scale = [scalar, scalar, scalar]

    payload["transform"] = {
        **transform,
        "location": [round(value, 3) for value in location],
        "rotation": [round(value, 3) for value in rotation],
        "scale": [round(value, 3) for value in clamped_scale],
    }
    payload["managed_slot"] = str(payload.get("managed_slot") or default_managed_slot(payload))
    payload["identity_policy"] = str(payload.get("identity_policy") or default_identity_policy(str(payload.get("action") or "")))
    payload["placement_hint"] = {**incoming_hint, **context}
    return payload
