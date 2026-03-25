from __future__ import annotations

from apps.validation.report_builder import build_rule_result


def validate_shell_alignment(
    *,
    scene_state: dict,
    dirty_zone: dict,
    enabled: bool,
    fail_hard: bool,
    check_inside_outside_consistency: bool,
) -> dict:
    if not enabled:
        return build_rule_result(name="shell_alignment", passed=True, blocking=False, warnings=["shell_alignment validator disabled"])
    if not dirty_zone.get("shell_sensitive", False):
        return build_rule_result(name="shell_alignment", passed=True, blocking=False, details={"skipped": "zone_not_shell_sensitive"})
    shell_state = scene_state.get("shell_alignment", {}) or {}
    is_consistent = shell_state.get("is_consistent")
    has_inside = bool(shell_state.get("inside_checked", False))
    has_outside = bool(shell_state.get("outside_checked", False))
    issues: list[str] = []
    warnings: list[str] = []
    if check_inside_outside_consistency:
        if not has_inside:
            warnings.append("inside shell check missing")
        if not has_outside:
            warnings.append("outside shell check missing")
    if is_consistent is False:
        issues.append("inside/outside shell alignment mismatch detected")
    return build_rule_result(
        name="shell_alignment",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={"inside_checked": has_inside, "outside_checked": has_outside, "is_consistent": is_consistent},
    )


def is_shell_aligned(offset_cm: float, tolerance_cm: float = 2) -> bool:
    return abs(offset_cm) <= tolerance_cm
