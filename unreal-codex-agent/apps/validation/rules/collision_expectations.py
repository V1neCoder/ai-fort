from __future__ import annotations

from apps.validation.report_builder import build_rule_result


def validate_collision_expectations(
    *,
    scene_state: dict,
    asset_record: dict | None,
    enabled: bool,
    fail_hard: bool,
) -> dict:
    if not enabled:
        return build_rule_result(name="collision_expectations", passed=True, blocking=False, warnings=["collision_expectations validator disabled"])
    collision_issues = scene_state.get("collision_issues", []) or []
    requires_collision = bool(((asset_record or {}).get("tags") or {}).get("collision_required", False))
    collision_verified = (asset_record or {}).get("quality_flags", {}).get("collision_verified")
    active_actor = scene_state.get("active_actor", {}) or {}
    if collision_verified is None:
        for key in ("collision_enabled", "query_collision_enabled", "actor_collision_enabled"):
            if isinstance(active_actor.get(key), bool):
                collision_verified = bool(active_actor.get(key))
                break
    issues: list[str] = []
    warnings: list[str] = []
    if collision_issues:
        issues.extend(str(item) for item in collision_issues)
    if requires_collision and collision_verified is False:
        issues.append("asset requires collision but collision verification is false")
    elif collision_verified is None:
        warnings.append("collision verification is unknown")
    return build_rule_result(
        name="collision_expectations",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={
            "requires_collision": requires_collision,
            "collision_verified": collision_verified,
            "collision_issue_count": len(collision_issues),
        },
    )


def collision_expected(colliding: bool) -> bool:
    return colliding
