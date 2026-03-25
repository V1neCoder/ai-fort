from __future__ import annotations

from typing import Any

from apps.placement.support_surfaces import (
    actor_origin_and_extent,
    compatible_support_kinds,
    is_support_kind_compatible,
    support_anchor_for_actor,
    support_kind_for_actor,
    support_level_for_actor,
)

FLOOR_LIKE_MOUNT_TYPES = {"floor", "surface", "exterior_ground"}
IGNORED_INTERFERENCE_CLASSES = {
    "LevelBounds",
    "Device_ExperienceSettings_V2_UEFN_C",
}
IGNORED_INTERFERENCE_LABELS = {
    "LevelBounds",
    "IslandSettings0",
}
TOOL_GENERATED_LABEL_PREFIXES = ("UCA_",)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


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


def _actor_origin_and_extent(actor_payload: dict[str, Any]) -> tuple[list[float], list[float]] | None:
    try:
        return actor_origin_and_extent(actor_payload)
    except Exception:
        bounds = dict(actor_payload.get("bounds_cm") or {})
        origin = bounds.get("origin")
        extent = bounds.get("box_extent")
        if not isinstance(origin, (list, tuple, dict)) or not isinstance(extent, (list, tuple, dict)):
            location = actor_payload.get("location")
            if not isinstance(location, (list, tuple, dict)):
                return None
            return _safe_triplet(location), [0.0, 0.0, 0.0]
        return _safe_triplet(origin), _safe_triplet(extent)


def _actor_bounds(actor_payload: dict[str, Any]) -> tuple[list[float], list[float]] | None:
    values = _actor_origin_and_extent(actor_payload)
    if values is None:
        return None
    origin, extent = values
    minimum = [origin[i] - extent[i] for i in range(3)]
    maximum = [origin[i] + extent[i] for i in range(3)]
    return minimum, maximum


def _axis_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    return max(0.0, min(a_max, b_max) - max(a_min, b_min))


def _actor_distance_xy(a: dict[str, Any], b: dict[str, Any]) -> float:
    loc_a = _safe_triplet(a.get("location"))
    loc_b = _safe_triplet(b.get("location"))
    dx = loc_a[0] - loc_b[0]
    dy = loc_a[1] - loc_b[1]
    return (dx * dx + dy * dy) ** 0.5


def _same_transform(a: dict[str, Any], b: dict[str, Any], *, tolerance_cm: float = 5.0) -> bool:
    if _actor_distance_xy(a, b) > tolerance_cm:
        return False
    loc_a = _safe_triplet(a.get("location"))
    loc_b = _safe_triplet(b.get("location"))
    if abs(loc_a[2] - loc_b[2]) > tolerance_cm:
        return False
    scale_a = _safe_triplet(a.get("scale"), [1.0, 1.0, 1.0])
    scale_b = _safe_triplet(b.get("scale"), [1.0, 1.0, 1.0])
    if any(abs(scale_a[i] - scale_b[i]) > 0.05 for i in range(3)):
        return False
    return True


def _is_support_actor(actor_payload: dict[str, Any], support_reference: dict[str, Any]) -> bool:
    support_label = _safe_text(
        support_reference.get("parent_support_actor")
        or support_reference.get("support_actor_label")
    ).lower()
    support_path = _safe_text(support_reference.get("support_actor_path")).lower()
    actor_label = _safe_text(actor_payload.get("label")).lower()
    actor_path = _safe_text(actor_payload.get("actor_path")).lower()
    if support_path and actor_path == support_path:
        return True
    if support_label and actor_label == support_label:
        return True
    return False


def _xy_overlap(active_actor: dict[str, Any], other_actor: dict[str, Any]) -> tuple[float, float, float]:
    active_bounds = _actor_bounds(active_actor)
    other_bounds = _actor_bounds(other_actor)
    if active_bounds is None or other_bounds is None:
        return (0.0, 0.0, 0.0)
    active_min, active_max = active_bounds
    other_min, other_max = other_bounds
    x_overlap = _axis_overlap(active_min[0], active_max[0], other_min[0], other_max[0])
    y_overlap = _axis_overlap(active_min[1], active_max[1], other_min[1], other_max[1])
    return (x_overlap, y_overlap, round(x_overlap * y_overlap, 3))


def _actor_bottom_z(actor_payload: dict[str, Any]) -> float | None:
    origin_and_extent = _actor_origin_and_extent(actor_payload)
    if origin_and_extent is None:
        return None
    origin, extent = origin_and_extent
    return float(origin[2]) - float(extent[2])


def _actor_top_z(actor_payload: dict[str, Any]) -> float | None:
    origin_and_extent = _actor_origin_and_extent(actor_payload)
    if origin_and_extent is None:
        return None
    origin, extent = origin_and_extent
    return float(origin[2]) + float(extent[2])


def _reserved_volume_bounds(volume_payload: dict[str, Any]) -> tuple[list[float], list[float]] | None:
    minimum = _safe_triplet(volume_payload.get("min"))
    maximum = _safe_triplet(volume_payload.get("max"))
    if minimum == [0.0, 0.0, 0.0] and maximum == [0.0, 0.0, 0.0] and not volume_payload.get("min") and not volume_payload.get("max"):
        return None
    return minimum, maximum


def _reserved_volume_conflicts(
    active_actor: dict[str, Any],
    reserved_volumes: list[dict[str, Any]],
    *,
    allowed_reserved_volume_kinds: set[str] | None = None,
    overlap_tolerance_cm: float = 1.0,
) -> list[dict[str, Any]]:
    actor_bounds = _actor_bounds(active_actor)
    if actor_bounds is None:
        return []
    active_min, active_max = actor_bounds
    allowed_kinds = {str(value or "").strip().lower() for value in set(allowed_reserved_volume_kinds or set()) if str(value or "").strip()}
    conflicts: list[dict[str, Any]] = []
    for raw_volume in reserved_volumes:
        if not isinstance(raw_volume, dict):
            continue
        volume = dict(raw_volume)
        if not bool(volume.get("protected", True)):
            continue
        volume_kind = _safe_text(volume.get("kind")).lower()
        if volume_kind in allowed_kinds:
            continue
        bounds = _reserved_volume_bounds(volume)
        if bounds is None:
            continue
        volume_min, volume_max = bounds
        x_overlap = _axis_overlap(active_min[0], active_max[0], volume_min[0], volume_max[0])
        y_overlap = _axis_overlap(active_min[1], active_max[1], volume_min[1], volume_max[1])
        z_overlap = _axis_overlap(active_min[2], active_max[2], volume_min[2], volume_max[2])
        if x_overlap <= overlap_tolerance_cm or y_overlap <= overlap_tolerance_cm or z_overlap <= overlap_tolerance_cm:
            continue
        conflicts.append(
            {
                "volume_name": _safe_text(volume.get("name")),
                "volume_kind": volume_kind,
                "overlap_cm": [round(x_overlap, 3), round(y_overlap, 3), round(z_overlap, 3)],
                "overlap_volume_cm3": round(x_overlap * y_overlap * z_overlap, 3),
            }
        )
    conflicts.sort(key=lambda item: (-float(item.get("overlap_volume_cm3") or 0.0), _safe_text(item.get("volume_name"))))
    return conflicts


def infer_support_contact(
    active_actor: dict[str, Any],
    scene_actors: list[dict[str, Any]],
    *,
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
    max_support_gap_cm: float = 25.0,
    embed_tolerance_cm: float = 4.0,
) -> dict[str, Any] | None:
    active_bottom = _actor_bottom_z(active_actor)
    if active_bottom is None:
        return None
    active_path = _safe_text(active_actor.get("actor_path"))
    ignore_paths = {str(value or "").strip() for value in set(ignore_actor_paths or set()) if str(value or "").strip()}
    ignore_labels = {str(value or "").strip() for value in set(ignore_actor_labels or set()) if str(value or "").strip()}
    if active_path:
        ignore_paths.add(active_path)

    best_contact: dict[str, Any] | None = None
    best_key: tuple[float, float, int, str] | None = None

    for raw_other in scene_actors:
        if not isinstance(raw_other, dict):
            continue
        other = dict(raw_other)
        other_path = _safe_text(other.get("actor_path"))
        other_label = _safe_text(other.get("label"))
        other_class = _safe_text(other.get("class_name"))
        if other_path and other_path in ignore_paths:
            continue
        if other_label and other_label in ignore_labels:
            continue
        if other_class in IGNORED_INTERFERENCE_CLASSES or other_label in IGNORED_INTERFERENCE_LABELS:
            continue
        support_kind = support_kind_for_actor(other)
        if not support_kind:
            continue
        top_z = _actor_top_z(other)
        if top_z is None:
            continue
        x_overlap, y_overlap, overlap_area = _xy_overlap(active_actor, other)
        if x_overlap <= 1.0 or y_overlap <= 1.0:
            continue
        delta_cm = round(active_bottom - top_z, 3)
        if delta_cm < -embed_tolerance_cm or delta_cm > max_support_gap_cm:
            continue
        actor_key = _safe_text(other.get("actor_path") or other.get("label") or other.get("actor_name")).lower()
        candidate = {
            "actor_path": other_path,
            "actor_label": other_label,
            "class_name": other_class,
            "support_surface_kind": support_kind,
            "support_level": support_level_for_actor(other),
            "surface_anchor": support_anchor_for_actor(other),
            "support_surface_z": round(float(top_z), 3),
            "support_surface_delta_cm": delta_cm,
            "xy_overlap_cm": [round(x_overlap, 3), round(y_overlap, 3)],
            "xy_overlap_area_cm2": overlap_area,
        }
        key = (
            abs(delta_cm),
            -overlap_area,
            support_level_for_actor(other),
            actor_key,
        )
        if best_key is None or key < best_key:
            best_key = key
            best_contact = candidate
    return best_contact


def _support_occupancy(
    active_actor: dict[str, Any],
    scene_actors: list[dict[str, Any]],
    *,
    support_contact: dict[str, Any] | None,
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
    same_surface_tolerance_cm: float = 6.0,
) -> list[dict[str, Any]]:
    if not isinstance(support_contact, dict):
        return []
    support_z = _safe_float(support_contact.get("support_surface_z"), 0.0)
    support_kind = _safe_text(support_contact.get("support_surface_kind")).lower()
    support_actor_path = _safe_text(support_contact.get("actor_path"))
    active_path = _safe_text(active_actor.get("actor_path"))
    ignore_paths = {str(value or "").strip() for value in set(ignore_actor_paths or set()) if str(value or "").strip()}
    ignore_labels = {str(value or "").strip() for value in set(ignore_actor_labels or set()) if str(value or "").strip()}
    if active_path:
        ignore_paths.add(active_path)
    if support_actor_path:
        ignore_paths.add(support_actor_path)

    occupancy: list[dict[str, Any]] = []
    for raw_other in scene_actors:
        if not isinstance(raw_other, dict):
            continue
        other = dict(raw_other)
        other_path = _safe_text(other.get("actor_path"))
        other_label = _safe_text(other.get("label"))
        other_class = _safe_text(other.get("class_name"))
        if other_path and other_path in ignore_paths:
            continue
        if other_label and other_label in ignore_labels:
            continue
        if other_class in IGNORED_INTERFERENCE_CLASSES or other_label in IGNORED_INTERFERENCE_LABELS:
            continue
        other_bottom = _actor_bottom_z(other)
        if other_bottom is None:
            continue
        if abs(other_bottom - support_z) > same_surface_tolerance_cm:
            continue
        other_support_kind = _safe_text(support_kind_for_actor(other)).lower()
        if other_support_kind and other_support_kind != support_kind:
            continue
        x_overlap, y_overlap, overlap_area = _xy_overlap(active_actor, other)
        if x_overlap <= 1.0 or y_overlap <= 1.0:
            continue
        occupancy.append(
            {
                "actor_path": other_path,
                "actor_label": other_label,
                "asset_path": _safe_text(other.get("asset_path")),
                "support_surface_kind": other_support_kind,
                "support_surface_delta_cm": round(other_bottom - support_z, 3),
                "xy_overlap_cm": [round(x_overlap, 3), round(y_overlap, 3)],
                "xy_overlap_area_cm2": overlap_area,
            }
        )
    occupancy.sort(key=lambda item: (-float(item.get("xy_overlap_area_cm2") or 0.0), _safe_text(item.get("actor_path") or item.get("actor_label"))))
    return occupancy


def _is_tool_generated_duplicate(duplicate_item: dict[str, Any]) -> bool:
    label = _safe_text(duplicate_item.get("actor_label"))
    return any(label.startswith(prefix) for prefix in TOOL_GENERATED_LABEL_PREFIXES)


def translated_actor(actor_payload: dict[str, Any], location: list[float]) -> dict[str, Any]:
    updated = dict(actor_payload or {})
    original_location = _safe_triplet(updated.get("location"))
    target_location = _safe_triplet(location)
    delta = [target_location[i] - original_location[i] for i in range(3)]
    updated["location"] = target_location
    bounds = dict(updated.get("bounds_cm") or {})
    origin = _safe_triplet(bounds.get("origin"), original_location)
    bounds["origin"] = [round(origin[i] + delta[i], 3) for i in range(3)]
    bounds["box_extent"] = _safe_triplet(bounds.get("box_extent"))
    updated["bounds_cm"] = bounds
    return updated


def detect_actor_conflicts(
    active_actor: dict[str, Any],
    scene_actors: list[dict[str, Any]],
    *,
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
    support_reference: dict[str, Any] | None = None,
    mount_type: str = "",
    reserved_volumes: list[dict[str, Any]] | None = None,
    allowed_reserved_volume_kinds: list[str] | None = None,
    overlap_tolerance_cm: float = 1.0,
) -> dict[str, Any]:
    ignore_paths = {str(value) for value in set(ignore_actor_paths or set()) if str(value or "").strip()}
    ignore_labels = {str(value) for value in set(ignore_actor_labels or set()) if str(value or "").strip()}
    support_reference = dict(support_reference or {})
    active_path = _safe_text(active_actor.get("actor_path"))
    active_label = _safe_text(active_actor.get("label"))
    active_bounds = _actor_bounds(active_actor)
    if active_bounds is None:
        return {
            "checked": False,
            "interference_policy": "",
            "blocking_interference_count": 0,
            "duplicate_count": 0,
            "blocking_overlaps": [],
            "duplicates": [],
        }

    (active_min, active_max) = active_bounds
    blocking_overlaps: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    checked_actor_count = 0

    for raw_other in scene_actors:
        if not isinstance(raw_other, dict):
            continue
        other = dict(raw_other)
        other_path = _safe_text(other.get("actor_path"))
        other_label = _safe_text(other.get("label"))
        other_class = _safe_text(other.get("class_name"))
        if other_path and other_path in ignore_paths:
            continue
        if other_label and other_label in ignore_labels:
            continue
        if active_path and other_path == active_path:
            continue
        if other_class in IGNORED_INTERFERENCE_CLASSES or other_label in IGNORED_INTERFERENCE_LABELS:
            continue
        if active_label and other_label == active_label and _same_transform(active_actor, other):
            duplicates.append(
                {
                    "actor_path": other_path,
                    "actor_label": other_label,
                    "asset_path": _safe_text(other.get("asset_path")),
                    "reason": "same_label_same_transform",
                }
            )
            continue

        checked_actor_count += 1
        if _is_support_actor(other, support_reference):
            continue
        other_bounds = _actor_bounds(other)
        if other_bounds is None:
            continue
        other_min, other_max = other_bounds
        x_overlap = _axis_overlap(active_min[0], active_max[0], other_min[0], other_max[0])
        y_overlap = _axis_overlap(active_min[1], active_max[1], other_min[1], other_max[1])
        z_overlap = _axis_overlap(active_min[2], active_max[2], other_min[2], other_max[2])
        if x_overlap <= overlap_tolerance_cm or y_overlap <= overlap_tolerance_cm or z_overlap <= overlap_tolerance_cm:
            continue
        blocking_overlaps.append(
            {
                "actor_path": other_path,
                "actor_label": other_label,
                "asset_path": _safe_text(other.get("asset_path")),
                "class_name": _safe_text(other.get("class_name")),
                "overlap_cm": [
                    round(x_overlap, 3),
                    round(y_overlap, 3),
                    round(z_overlap, 3),
                ],
                "overlap_volume_cm3": round(x_overlap * y_overlap * z_overlap, 3),
            }
        )

    support_contact = infer_support_contact(
        active_actor,
        scene_actors,
        ignore_actor_paths=ignore_paths,
        ignore_actor_labels=ignore_labels,
    )
    support_mismatch = False
    support_compatibility = "unknown"
    if mount_type:
        observed_support_kind = _safe_text((support_contact or {}).get("support_surface_kind")).lower()
        if observed_support_kind:
            support_mismatch = not is_support_kind_compatible(mount_type, observed_support_kind)
            support_compatibility = "compatible" if not support_mismatch else "incompatible"
    support_occupancy = _support_occupancy(
        active_actor,
        scene_actors,
        support_contact=support_contact,
        ignore_actor_paths=ignore_paths,
        ignore_actor_labels=ignore_labels,
    )
    reserved_conflicts = _reserved_volume_conflicts(
        active_actor,
        list(reserved_volumes or []),
        allowed_reserved_volume_kinds={str(value or "").strip().lower() for value in list(allowed_reserved_volume_kinds or []) if str(value or "").strip()},
        overlap_tolerance_cm=overlap_tolerance_cm,
    )

    return {
        "checked": True,
        "checked_actor_count": checked_actor_count,
        "blocking_interference_count": len(blocking_overlaps),
        "duplicate_count": len(duplicates),
        "blocking_overlaps": blocking_overlaps,
        "duplicates": duplicates,
        "support_contact": support_contact or {},
        "support_compatibility": support_compatibility,
        "support_mismatch": support_mismatch,
        "expected_mount_type": _safe_text(mount_type).lower(),
        "support_occupancy_count": len(support_occupancy),
        "support_occupancy": support_occupancy,
        "reserved_volume_conflict_count": len(reserved_conflicts),
        "reserved_volume_conflicts": reserved_conflicts,
    }


def _spiral_offsets(step_cm: float, max_rings: int) -> list[tuple[float, float]]:
    offsets = [(0.0, 0.0)]
    step = max(step_cm, 1.0)
    for ring in range(1, max_rings + 1):
        distance = step * ring
        for dx in range(-ring, ring + 1):
            for dy in range(-ring, ring + 1):
                if max(abs(dx), abs(dy)) != ring:
                    continue
                offsets.append((dx * distance / ring, dy * distance / ring))
    return offsets


def find_non_interfering_location(
    active_actor: dict[str, Any],
    scene_actors: list[dict[str, Any]],
    *,
    requested_location: list[float],
    support_z: float,
    grid_cm: float,
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
    support_reference: dict[str, Any] | None = None,
    mount_type: str = "",
    reserved_volumes: list[dict[str, Any]] | None = None,
    allowed_reserved_volume_kinds: list[str] | None = None,
    max_rings: int = 6,
    overlap_tolerance_cm: float = 1.0,
) -> dict[str, Any] | None:
    base_location = _safe_triplet(requested_location)
    target_z = _safe_float(support_z, base_location[2])
    base_location[2] = target_z
    step = max(_safe_float(grid_cm, 0.0), 10.0)
    for offset_x, offset_y in _spiral_offsets(step, max_rings):
        candidate_location = [
            round(base_location[0] + offset_x, 3),
            round(base_location[1] + offset_y, 3),
            round(target_z, 3),
        ]
        translated = translated_actor(active_actor, candidate_location)
        conflicts = detect_actor_conflicts(
            translated,
            scene_actors,
            ignore_actor_paths=ignore_actor_paths,
            ignore_actor_labels=ignore_actor_labels,
            support_reference=support_reference,
            mount_type=mount_type,
            reserved_volumes=reserved_volumes,
            allowed_reserved_volume_kinds=allowed_reserved_volume_kinds,
            overlap_tolerance_cm=overlap_tolerance_cm,
        )
        if (
            conflicts["blocking_interference_count"] == 0
            and conflicts.get("support_occupancy_count", 0) == 0
            and conflicts.get("reserved_volume_conflict_count", 0) == 0
            and not bool(conflicts.get("support_mismatch", False))
        ):
            return {
                "location": candidate_location,
                "offset_cm": [
                    round(candidate_location[0] - base_location[0], 3),
                    round(candidate_location[1] - base_location[1], 3),
                    round(candidate_location[2] - base_location[2], 3),
                ],
                "checked_candidates": len(_spiral_offsets(step, max_rings)),
                "grid_cm": step,
                "conflicts": conflicts,
            }
    return None
