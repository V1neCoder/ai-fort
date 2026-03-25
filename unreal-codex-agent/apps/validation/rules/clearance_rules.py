from __future__ import annotations

from apps.validation.report_builder import build_rule_result


def _clearance_value(source: dict, key: str) -> float | None:
    value = source.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_clearance_rules(
    *,
    scene_state: dict,
    asset_record: dict | None,
    enabled: bool,
    fail_hard: bool,
) -> dict:
    if not enabled:
        return build_rule_result(name="clearance_rules", passed=True, blocking=False, warnings=["clearance_rules validator disabled"])
    placement_rules = (asset_record or {}).get("placement_rules", {}) or {}
    required_front = _clearance_value(placement_rules, "min_front_clearance_cm")
    required_side = _clearance_value(placement_rules, "min_side_clearance_cm")
    required_back = _clearance_value(placement_rules, "min_back_clearance_cm")
    observations = scene_state.get("clearance_observations", {}) or {}
    actual_front = _clearance_value(observations, "front_cm")
    actual_side = _clearance_value(observations, "side_cm")
    actual_back = _clearance_value(observations, "back_cm")
    warnings: list[str] = []
    issues: list[str] = []
    if required_front is not None:
        if actual_front is None:
            warnings.append("front clearance observation missing")
        elif actual_front < required_front:
            issues.append(f"front clearance {actual_front:.1f}cm below required {required_front:.1f}cm")
    if required_side is not None:
        if actual_side is None:
            warnings.append("side clearance observation missing")
        elif actual_side < required_side:
            issues.append(f"side clearance {actual_side:.1f}cm below required {required_side:.1f}cm")
    if required_back is not None:
        if actual_back is None:
            warnings.append("back clearance observation missing")
        elif actual_back < required_back:
            issues.append(f"back clearance {actual_back:.1f}cm below required {required_back:.1f}cm")
    return build_rule_result(
        name="clearance_rules",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={
            "required": {"front_cm": required_front, "side_cm": required_side, "back_cm": required_back},
            "observed": {"front_cm": actual_front, "side_cm": actual_side, "back_cm": actual_back},
        },
    )


def has_clearance(distance_cm: float, minimum_cm: float = 45) -> bool:
    return distance_cm >= minimum_cm
