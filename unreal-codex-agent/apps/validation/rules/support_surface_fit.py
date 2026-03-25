from __future__ import annotations

from typing import Any

from apps.placement.support_fit import derive_support_surface_fit
from apps.validation.report_builder import build_rule_result


def _placement_hint(action: Any) -> dict[str, Any]:
    if hasattr(action, "raw") and isinstance(action.raw, dict):
        return dict(action.raw.get("placement_hint") or {})
    if isinstance(action, dict):
        return dict(action.get("placement_hint") or {})
    return {}


def validate_support_surface_fit(
    *,
    scene_state: dict,
    action: Any,
    enabled: bool,
    fail_hard: bool,
) -> dict:
    if not enabled:
        return build_rule_result(name="support_surface_fit", passed=True, blocking=False, warnings=["support_surface_fit validator disabled"])
    active_actor = dict(scene_state.get("active_actor") or {})
    if not active_actor:
        return build_rule_result(name="support_surface_fit", passed=True, blocking=False, warnings=["no active actor available for support-surface fit validation"])

    hint = _placement_hint(action)
    placement_phase = str(hint.get("placement_phase") or "initial_place").strip().lower()
    snap_policy = str(hint.get("snap_policy") or "initial_only").strip().lower()
    mount_type = str(
        hint.get("mount_type")
        or hint.get("expected_mount_type")
        or scene_state.get("expected_mount_type")
        or ""
    ).strip().lower()
    if mount_type not in {"", "floor", "surface", "exterior_ground"}:
        return build_rule_result(
            name="support_surface_fit",
            passed=True,
            blocking=False,
            details={
                "placement_phase": placement_phase,
                "snap_policy": snap_policy,
                "mount_type": mount_type,
                "skipped": "mount_type_not_floor_like",
            },
        )
    if placement_phase == "reposition" and snap_policy != "force":
        return build_rule_result(
            name="support_surface_fit",
            passed=True,
            blocking=False,
            details={
                "placement_phase": placement_phase,
                "snap_policy": snap_policy,
                "mount_type": mount_type,
                "skipped": "preserve_requested_transform",
            },
        )

    details = derive_support_surface_fit(scene_state=scene_state, active_actor=active_actor)
    if not details:
        return build_rule_result(name="support_surface_fit", passed=True, blocking=False, warnings=["support-surface fit could not be derived from the current scene state"])

    state = str(details.get("support_surface_fit_state") or "")
    issues: list[str] = []
    warnings: list[str] = []
    if state in {"embedded", "floating"}:
        issues.append(
            f"actor is {state.replace('_', ' ')} relative to the {details.get('support_anchor_type') or 'support surface'}"
        )
    elif state == "slightly_offset":
        warnings.append("actor is slightly offset from the support surface")

    return build_rule_result(
        name="support_surface_fit",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={
            **details,
            "placement_phase": placement_phase,
            "snap_policy": snap_policy,
            "mount_type": mount_type,
        },
    )
