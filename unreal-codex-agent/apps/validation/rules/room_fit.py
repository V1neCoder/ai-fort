from __future__ import annotations

from apps.validation.report_builder import build_rule_result


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


def validate_room_fit(
    *,
    scene_state: dict,
    dirty_zone: dict,
    asset_record: dict | None,
    enabled: bool,
    fail_hard: bool,
    require_room_type_match: bool,
    require_mount_type_match: bool,
) -> dict:
    if not enabled:
        return build_rule_result(name="room_fit", passed=True, blocking=False, warnings=["room_fit validator disabled"])
    if not asset_record:
        return build_rule_result(name="room_fit", passed=True, blocking=False, warnings=["no active asset record available for room-fit validation"])
    tags = asset_record.get("tags", {}) or {}
    room_type = dirty_zone.get("room_type") or scene_state.get("room_type") or "unknown"
    room_types = tags.get("room_types", []) or []
    mount_type = tags.get("mount_type")
    prefab_family = tags.get("prefab_family")
    scene_mount_type = scene_state.get("expected_mount_type")
    active_actor = scene_state.get("active_actor", {}) or {}
    issues: list[str] = []
    warnings: list[str] = []
    if require_room_type_match and room_types and room_type not in room_types:
        issues.append(f"asset not tagged for room type '{room_type}'")
    compatible = set(MOUNT_COMPATIBILITY.get(scene_mount_type, {scene_mount_type})) if scene_mount_type else set()
    mount_candidates = {str(value) for value in (mount_type, prefab_family) if value}
    if require_mount_type_match and mount_candidates and scene_mount_type and not (mount_candidates & compatible):
        issues.append(
            f"asset mount family {sorted(mount_candidates)} does not match expected '{scene_mount_type}'"
        )
    if not room_types:
        warnings.append("asset has no room_type tags")
    if not mount_type:
        warnings.append("asset has no mount_type tag")
    if bool(tags.get("is_prefab", False)) and not prefab_family:
        warnings.append("prefab asset has no prefab_family tag")
    return build_rule_result(
        name="room_fit",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={
            "room_type": room_type,
            "asset_room_types": room_types,
            "asset_mount_type": mount_type,
            "asset_prefab_family": prefab_family,
            "expected_mount_type": scene_mount_type,
            "compatible_mount_types": sorted(compatible) if compatible else [],
            "support_surface_fit_ok": active_actor.get("support_surface_fit_ok"),
            "support_surface_delta_cm": active_actor.get("support_surface_delta_cm"),
            "support_surface_fit_state": active_actor.get("support_surface_fit_state"),
            "support_surface_kind": active_actor.get("support_surface_kind"),
        },
    )


def room_fit(room_area: float, item_area: float) -> bool:
    return item_area <= room_area
