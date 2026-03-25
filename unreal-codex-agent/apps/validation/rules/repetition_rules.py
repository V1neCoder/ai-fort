from __future__ import annotations

from apps.validation.report_builder import build_rule_result


def validate_repetition_rules(
    *,
    scene_state: dict,
    asset_record: dict | None,
    enabled: bool,
    fail_hard: bool,
    max_same_focal_asset_per_room: int,
    max_same_support_asset_per_room: int,
) -> dict:
    if not enabled:
        return build_rule_result(name="repetition_rules", passed=True, blocking=False, warnings=["repetition_rules validator disabled"])
    if not asset_record:
        return build_rule_result(name="repetition_rules", passed=True, blocking=False, warnings=["no active asset record available for repetition analysis"])
    actors = scene_state.get("actors", []) or []
    room_type = scene_state.get("room_type", "unknown")
    active_asset_path = asset_record.get("asset_path")
    same_asset_count = 0
    same_category_count = 0
    active_category = (asset_record.get("tags") or {}).get("category")
    visibility_role = ((asset_record.get("tags") or {}).get("visibility_role") or "support").lower()
    for actor in actors:
        if actor.get("room_type", room_type) != room_type:
            continue
        if actor.get("asset_path") == active_asset_path:
            same_asset_count += 1
        if actor.get("category") == active_category:
            same_category_count += 1
    limit = max_same_focal_asset_per_room if visibility_role == "focal" else max_same_support_asset_per_room
    issues: list[str] = []
    warnings: list[str] = []
    if same_asset_count > limit:
        issues.append(f"asset repetition too high in room: same asset count {same_asset_count} exceeds limit {limit}")
    elif same_category_count > (limit * 2):
        warnings.append(f"category repetition may be high in room: category count {same_category_count}")
    return build_rule_result(
        name="repetition_rules",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={
            "same_asset_count": same_asset_count,
            "same_category_count": same_category_count,
            "room_type": room_type,
            "limit": limit,
        },
    )


def repetition_ok(count: int, limit: int = 3) -> bool:
    return count <= limit
