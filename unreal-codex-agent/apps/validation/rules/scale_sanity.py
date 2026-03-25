from __future__ import annotations

from typing import Any

from apps.validation.report_builder import build_rule_result


def _triplet_from_scale(scale_value: Any) -> list[float]:
    if isinstance(scale_value, dict) and {"x", "y", "z"} <= set(scale_value.keys()):
        return [float(scale_value["x"]), float(scale_value["y"]), float(scale_value["z"])]
    if isinstance(scale_value, (list, tuple)) and len(scale_value) == 3:
        return [float(scale_value[0]), float(scale_value[1]), float(scale_value[2])]
    return []


def validate_scale_sanity(
    *,
    action: dict[str, Any],
    asset_record: dict[str, Any] | None,
    enabled: bool,
    fail_hard: bool,
) -> dict[str, Any]:
    if not enabled:
        return build_rule_result(name="scale_sanity", passed=True, blocking=False, warnings=["scale_sanity validator disabled"])
    scale = _triplet_from_scale((action.get("transform") or {}).get("scale"))
    if not scale:
        return build_rule_result(name="scale_sanity", passed=True, blocking=False, warnings=["no explicit scale provided in action"])
    limits = (asset_record or {}).get("scale_limits", {}) or {}
    min_scale = float(limits.get("min", 0.0))
    max_scale = float(limits.get("max", 999.0))
    issues: list[str] = []
    if min_scale > 0:
        for axis_name, value in zip(("x", "y", "z"), scale):
            if value < min_scale or value > max_scale:
                issues.append(f"scale axis {axis_name}={value:.3f} outside safe limits [{min_scale:.3f}, {max_scale:.3f}]")
    return build_rule_result(
        name="scale_sanity",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        details={"applied_scale": scale, "limits": {"min": min_scale, "max": max_scale}},
    )


def check_scale(size_cm: tuple[float, float, float]) -> bool:
    return all(value >= 0 for value in size_cm)
