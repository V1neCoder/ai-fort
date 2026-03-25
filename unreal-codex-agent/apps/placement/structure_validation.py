from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _triplet(value: Any, default: list[float] | None = None) -> list[float]:
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


def _internal_rotation_to_live_triplet(rotation: Any) -> list[float]:
    values = _triplet(rotation)
    roll, pitch, yaw = values[0], values[1], values[2]
    return [pitch, yaw, roll]


def _axis_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    return max(0.0, min(a_max, b_max) - max(a_min, b_min))


def _bounds_for_segment(segment: dict[str, Any]) -> tuple[list[float], list[float]]:
    location = _triplet(segment.get("location"))
    bounds = dict(segment.get("bounds_cm") or {})
    if bounds:
        origin = _triplet(bounds.get("origin"), location)
        extent = _triplet(bounds.get("box_extent"))
        return (
            [origin[i] - extent[i] for i in range(3)],
            [origin[i] + extent[i] for i in range(3)],
        )
    scale = _triplet(segment.get("scale"), [1.0, 1.0, 1.0])
    extent = [abs(scale[0]) * 50.0, abs(scale[1]) * 50.0, abs(scale[2]) * 50.0]
    return (
        [location[i] - extent[i] for i in range(3)],
        [location[i] + extent[i] for i in range(3)],
    )


def _volume_bounds(volume: dict[str, Any]) -> tuple[list[float], list[float]]:
    return _triplet(volume.get("min")), _triplet(volume.get("max"))


def _overlap_details(
    first_bounds: tuple[list[float], list[float]],
    second_bounds: tuple[list[float], list[float]],
) -> dict[str, Any] | None:
    first_min, first_max = first_bounds
    second_min, second_max = second_bounds
    x_overlap = _axis_overlap(first_min[0], first_max[0], second_min[0], second_max[0])
    y_overlap = _axis_overlap(first_min[1], first_max[1], second_min[1], second_max[1])
    z_overlap = _axis_overlap(first_min[2], first_max[2], second_min[2], second_max[2])
    if x_overlap <= 0.0 or y_overlap <= 0.0 or z_overlap <= 0.0:
        return None
    return {
        "overlap_cm": [round(x_overlap, 3), round(y_overlap, 3), round(z_overlap, 3)],
        "overlap_volume_cm3": round(x_overlap * y_overlap * z_overlap, 3),
    }


def _merge_segment_with_live_actor(segment: dict[str, Any], live_actor: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(segment)
    if not isinstance(live_actor, dict) or not live_actor:
        return merged
    merged["location"] = list(live_actor.get("location") or merged.get("location") or [0.0, 0.0, 0.0])
    merged["rotation"] = list(live_actor.get("rotation") or merged.get("rotation") or [0.0, 0.0, 0.0])
    merged["scale"] = list(live_actor.get("scale") or merged.get("scale") or [1.0, 1.0, 1.0])
    if isinstance(live_actor.get("bounds_cm"), dict):
        merged["bounds_cm"] = dict(live_actor.get("bounds_cm") or {})
    merged["actor_path"] = _safe_text(live_actor.get("actor_path"))
    merged["actor_label"] = _safe_text(live_actor.get("label") or segment.get("spawn_label"))
    return merged


def validate_structure_plan(
    structure_plan: dict[str, Any],
    *,
    live_actors_by_slot: dict[str, dict[str, Any]] | None = None,
    tolerance_cm: float = 4.0,
) -> dict[str, Any]:
    plan = dict(structure_plan or {})
    segments = [dict(item) for item in list(plan.get("segments") or []) if isinstance(item, dict)]
    reserved_volumes = [dict(item) for item in list(plan.get("reserved_volumes") or []) if isinstance(item, dict)]
    circulation_plan = dict(plan.get("circulation_plan") or {})
    roof_envelope = dict(plan.get("roof_envelope") or {})
    clearance_requirements = dict(plan.get("clearance_requirements") or {})
    live_actors_by_slot = {
        str(slot): dict(actor)
        for slot, actor in dict(live_actors_by_slot or {}).items()
        if isinstance(actor, dict)
    }
    live_slots = set(live_actors_by_slot)

    merged_segments = [
        _merge_segment_with_live_actor(segment, live_actors_by_slot.get(str(segment.get("managed_slot") or "")))
        for segment in segments
    ]
    by_slot = {str(segment.get("managed_slot") or ""): segment for segment in merged_segments}
    stair_segments = sorted(
        [segment for segment in merged_segments if str(segment.get("structure_piece_role") or "") == "stair_run"],
        key=lambda item: _triplet(item.get("location"))[2],
    )
    protected_volumes = [volume for volume in reserved_volumes if bool(volume.get("protected", True))]

    reserved_volume_conflicts: list[dict[str, Any]] = []
    stairwell_conflicts: list[dict[str, Any]] = []
    landing_conflicts: list[dict[str, Any]] = []
    door_conflicts: list[dict[str, Any]] = []

    for segment in merged_segments:
        segment_bounds = _bounds_for_segment(segment)
        allowed_kinds = {
            _safe_text(value).lower()
            for value in list(segment.get("allowed_reserved_volume_kinds") or [])
            if _safe_text(value)
        }
        for volume in protected_volumes:
            volume_kind = _safe_text(volume.get("kind")).lower()
            if volume_kind in allowed_kinds:
                continue
            overlap = _overlap_details(segment_bounds, _volume_bounds(volume))
            if overlap is None or overlap["overlap_volume_cm3"] <= 0.0:
                continue
            if volume_kind == "landing_clearance":
                clearance_headroom_cm = _safe_float(clearance_requirements.get("stair_clearance_headroom_cm"), 0.0)
                volume_min, _volume_max = _volume_bounds(volume)
                segment_min, _segment_max = segment_bounds
                if clearance_headroom_cm > 0.0 and segment_min[2] >= (volume_min[2] + clearance_headroom_cm - tolerance_cm):
                    continue
            conflict = {
                "managed_slot": _safe_text(segment.get("managed_slot")),
                "structure_piece_role": _safe_text(segment.get("structure_piece_role")),
                "volume_name": _safe_text(volume.get("name")),
                "volume_kind": volume_kind,
                **overlap,
            }
            reserved_volume_conflicts.append(conflict)
            if volume_kind == "floor_void":
                stairwell_conflicts.append(conflict)
            elif volume_kind == "landing_clearance":
                landing_conflicts.append(conflict)
            elif volume_kind == "door_opening":
                door_conflicts.append(conflict)

    stairwell_volume = next((item for item in protected_volumes if _safe_text(item.get("name")) == "stairwell_opening"), {})
    landing_volume = next((item for item in protected_volumes if _safe_text(item.get("name")) == "stair_arrival_clearance"), {})
    stairwell_bounds = _volume_bounds(stairwell_volume) if stairwell_volume else None
    landing_bounds = _volume_bounds(landing_volume) if landing_volume else None

    circulation_issues: list[str] = []
    landing_issues: list[str] = []
    opening_issues: list[str] = []
    roof_issues: list[str] = []
    navigable_floor_issues: list[str] = []

    if stair_segments and stairwell_bounds is None:
        circulation_issues.append("stairs were generated without a matching stairwell opening")
    if stair_segments and landing_bounds is None:
        landing_issues.append("stairs were generated without a protected upper landing volume")
    if stairwell_conflicts:
        circulation_issues.append("structural pieces are blocking the stairwell opening")
        navigable_floor_issues.append("one or more floor or wall segments intrude into the stairwell opening")
    if landing_conflicts:
        circulation_issues.append("structural pieces are blocking the stair landing clearance")
        landing_issues.append("upper landing clearance is blocked")
    if door_conflicts:
        opening_issues.append("door opening volume is occupied by structural pieces")

    if stair_segments and stairwell_bounds is not None:
        top_step = stair_segments[-1]
        top_step_bounds = _bounds_for_segment(top_step)
        stair_top_overlap = _overlap_details(top_step_bounds, stairwell_bounds)
        if stair_top_overlap is None:
            circulation_issues.append("top stair step does not align with the stairwell opening")
        if landing_bounds is not None:
            top_step_min, top_step_max = top_step_bounds
            landing_min, landing_max = landing_bounds
            landing_xy_overlap = (
                _axis_overlap(top_step_min[0], top_step_max[0], landing_min[0], landing_max[0]) > 0.0
                and top_step_max[1] >= (landing_min[1] - 2.0)
                and top_step_min[1] <= (landing_max[1] + 2.0)
            )
            top_step_surface_z = top_step_max[2]
            landing_entry_ok = landing_xy_overlap and top_step_surface_z >= (landing_min[2] - 10.0)
            if not landing_entry_ok:
                circulation_issues.append("top stair step does not exit into the landing zone")
                landing_issues.append("landing is not reachable from the top of the stairs")

    expected_roof_parts = [
        ("roof_left", dict(roof_envelope.get("left_panel") or {})),
        ("roof_right", dict(roof_envelope.get("right_panel") or {})),
        ("roof_ridge", dict(roof_envelope.get("ridge") or {})),
    ]
    for slot, expected in expected_roof_parts:
        if not expected:
            continue
        live_segment = by_slot.get(slot)
        if not live_segment:
            roof_issues.append(f"missing roof element {slot}")
            continue
        expected_location = _triplet(expected.get("expected_location") or expected.get("location"))
        actual_location = _triplet(live_segment.get("location"))
        if any(abs(actual_location[index] - expected_location[index]) > tolerance_cm for index in range(3)):
            roof_issues.append(f"{slot} is outside the solved roof envelope position tolerance")
        if slot in live_slots:
            expected_rotation = _internal_rotation_to_live_triplet(expected.get("expected_rotation") or live_segment.get("rotation"))
        else:
            expected_rotation = _triplet(expected.get("expected_rotation") or live_segment.get("rotation"))
        actual_rotation = _triplet(live_segment.get("rotation"))
        rotation_tolerance = max(tolerance_cm, 6.0)
        if any(abs(actual_rotation[index] - expected_rotation[index]) > rotation_tolerance for index in range(3)):
            roof_issues.append(f"{slot} is outside the solved roof envelope rotation tolerance")

    for closure_key in ("gable_front", "gable_back"):
        closure = dict(roof_envelope.get(closure_key) or {})
        for slot in list(closure.get("slots") or []):
            if _safe_text(slot) and not by_slot.get(_safe_text(slot)):
                roof_issues.append(f"missing roof closure element {_safe_text(slot)}")

    summary = {
        "structure_type": _safe_text(plan.get("structure_type")),
        "story_count": int(_safe_float(plan.get("story_count"), 0)),
        "circulation_path": {
            "passed": len(circulation_issues) == 0,
            "issues": circulation_issues,
        },
        "landing_clearance": {
            "passed": len(landing_issues) == 0,
            "issues": landing_issues,
        },
        "opening_integrity": {
            "passed": len(opening_issues) == 0,
            "issues": opening_issues,
        },
        "roof_envelope_fit": {
            "passed": len(roof_issues) == 0,
            "issues": roof_issues,
        },
        "assembly_interference": {
            "passed": len(reserved_volume_conflicts) == 0,
            "issues": [f"{item['managed_slot']} overlaps {item['volume_name']}" for item in reserved_volume_conflicts],
            "conflicts": reserved_volume_conflicts,
        },
        "navigable_floor_fit": {
            "passed": len(navigable_floor_issues) == 0,
            "issues": navigable_floor_issues,
        },
    }
    summary["passed"] = all(bool(category.get("passed")) for key, category in summary.items() if isinstance(category, dict) and "passed" in category)
    return summary
