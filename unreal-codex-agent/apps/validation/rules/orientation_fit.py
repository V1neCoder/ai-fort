from __future__ import annotations

from typing import Any

from apps.placement.profile_store import load_pose_profile
from apps.validation.report_builder import build_rule_result


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rotation_triplet(value: Any) -> list[float]:
    if isinstance(value, (list, tuple)):
        padded = list(value[:3]) + [0.0, 0.0, 0.0]
        return [_safe_float(padded[0]), _safe_float(padded[1]), _safe_float(padded[2])]
    return [0.0, 0.0, 0.0]


def _angle_delta_deg(a: float, b: float) -> float:
    delta = (float(a) - float(b) + 180.0) % 360.0 - 180.0
    return abs(delta)


def _placement_hint(action: Any) -> dict[str, Any]:
    if hasattr(action, "raw") and isinstance(action.raw, dict):
        return dict(action.raw.get("placement_hint") or {})
    if isinstance(action, dict):
        return dict(action.get("placement_hint") or {})
    return {}


def validate_orientation_fit(
    *,
    repo_root,
    scene_state: dict,
    action: Any,
    enabled: bool,
    fail_hard: bool,
    roll_pitch_tolerance_deg: float = 5.0,
) -> dict:
    if not enabled:
        return build_rule_result(name="orientation_fit", passed=True, blocking=False, warnings=["orientation_fit validator disabled"])
    hint = _placement_hint(action)
    placement_phase = str(hint.get("placement_phase") or "initial_place").strip().lower()
    snap_policy = str(hint.get("snap_policy") or "initial_only").strip().lower()
    mount_type = str(hint.get("mount_type") or hint.get("expected_mount_type") or scene_state.get("expected_mount_type") or "").strip().lower()
    if mount_type not in {"floor", "surface", "exterior_ground"}:
        return build_rule_result(name="orientation_fit", passed=True, blocking=False, details={"skipped": "mount_type_not_floor_like", "mount_type": mount_type})
    if placement_phase == "reposition" and snap_policy != "force":
        return build_rule_result(name="orientation_fit", passed=True, blocking=False, details={"skipped": "preserve_requested_transform", "placement_phase": placement_phase})

    active_actor = dict(scene_state.get("active_actor") or {})
    if not active_actor:
        return build_rule_result(name="orientation_fit", passed=True, blocking=False, warnings=["no active actor available for orientation-fit validation"])

    asset_path = str(getattr(action, "asset_path", None) or (action.get("asset_path") if isinstance(action, dict) else "") or "").strip()
    profile = load_pose_profile(repo_root, asset_path)
    if not profile:
        return build_rule_result(name="orientation_fit", passed=True, blocking=False, warnings=["no cached pose profile is available for this asset"])

    active_rotation = _rotation_triplet(active_actor.get("rotation"))
    profile_rotation = _rotation_triplet(profile.get("rest_rotation_internal"))
    roll_delta = round(_angle_delta_deg(active_rotation[0], profile_rotation[0]), 3)
    pitch_delta = round(_angle_delta_deg(active_rotation[1], profile_rotation[1]), 3)
    issues: list[str] = []
    if roll_delta > roll_pitch_tolerance_deg or pitch_delta > roll_pitch_tolerance_deg:
        issues.append("actor orientation does not match the cached rest pose for this support placement")

    active_height = _safe_float(active_actor.get("orientation_height_cm"), 0.0)
    profile_height = _safe_float(profile.get("height_cm"), 0.0)
    if profile_height > 0.0 and active_height > 0.0 and active_height > profile_height * 1.25:
        issues.append("actor appears to be resting on the wrong side for a floor/support placement")

    return build_rule_result(
        name="orientation_fit",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        details={
            "placement_phase": placement_phase,
            "snap_policy": snap_policy,
            "mount_type": mount_type,
            "profile_rotation_internal": profile_rotation,
            "active_rotation": active_rotation,
            "roll_delta_deg": roll_delta,
            "pitch_delta_deg": pitch_delta,
            "profile_height_cm": profile_height,
            "active_height_cm": active_height,
        },
    )
