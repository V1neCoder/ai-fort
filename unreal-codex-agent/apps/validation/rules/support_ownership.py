from __future__ import annotations

from typing import Any

from apps.placement.support_surfaces import support_family_for_kind
from apps.validation.report_builder import build_rule_result


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _placement_hint(action: Any) -> dict[str, Any]:
    if hasattr(action, "raw") and isinstance(action.raw, dict):
        return dict(action.raw.get("placement_hint") or {})
    if isinstance(action, dict):
        return dict(action.get("placement_hint") or {})
    return {}


def _family_for_support_kind(value: str) -> str:
    return support_family_for_kind(_safe_text(value).lower())


def validate_support_ownership(
    *,
    scene_state: dict[str, Any],
    action: Any,
    enabled: bool,
    fail_hard: bool,
) -> dict[str, Any]:
    if not enabled:
        return build_rule_result(name="support_ownership", passed=True, blocking=False, warnings=["support_ownership validator disabled"])

    hint = _placement_hint(action)
    placement_phase = _safe_text(hint.get("placement_phase") or "initial_place").lower()
    snap_policy = _safe_text(hint.get("snap_policy") or "initial_only").lower()
    if placement_phase == "reposition" and snap_policy != "force":
        return build_rule_result(
            name="support_ownership",
            passed=True,
            blocking=False,
            details={
                "placement_phase": placement_phase,
                "snap_policy": snap_policy,
                "skipped": "preserve_requested_transform",
            },
        )

    managed_record = dict(scene_state.get("active_managed_record") or {})
    placement_targets = dict(scene_state.get("placement_targets") or {})
    dirty_bounds = dict(scene_state.get("dirty_bounds") or {})
    active_actor = dict(scene_state.get("active_actor") or {})

    expected_support_kind = _safe_text(
        hint.get("support_surface_kind")
        or dict(managed_record.get("support_reference") or {}).get("support_surface_kind")
        or placement_targets.get("support_surface_kind")
        or dirty_bounds.get("support_surface_kind")
    ).lower()
    expected_support_actor = _safe_text(
        hint.get("parent_support_actor")
        or hint.get("support_actor_label")
        or dict(managed_record.get("support_reference") or {}).get("parent_support_actor")
        or dict(managed_record.get("support_reference") or {}).get("support_actor_label")
        or placement_targets.get("support_actor_label")
    )
    actual_support_kind = _safe_text(
        active_actor.get("observed_support_surface_kind")
        or active_actor.get("support_surface_kind")
        or placement_targets.get("support_surface_kind")
        or dirty_bounds.get("support_surface_kind")
    ).lower()
    actual_support_actor = _safe_text(
        active_actor.get("observed_support_actor_label")
        or active_actor.get("parent_support_actor")
        or active_actor.get("support_actor_label")
        or placement_targets.get("support_actor_label")
    )

    issues: list[str] = []
    warnings: list[str] = []
    if expected_support_kind and actual_support_kind:
        expected_family = _family_for_support_kind(expected_support_kind)
        actual_family = _family_for_support_kind(actual_support_kind)
        if expected_family != actual_family:
            issues.append(
                f"actor is resting on {actual_support_kind or 'unknown support'} but expected {expected_support_kind or 'unknown support'}"
            )
    elif expected_support_kind and not actual_support_kind:
        warnings.append("expected support ownership could not be verified from the live actor snapshot")

    if expected_support_actor and actual_support_actor and expected_support_actor != actual_support_actor:
        warnings.append(
            f"support actor changed from {expected_support_actor} to {actual_support_actor}"
        )

    return build_rule_result(
        name="support_ownership",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={
            "placement_phase": placement_phase,
            "snap_policy": snap_policy,
            "expected_support_kind": expected_support_kind,
            "actual_support_kind": actual_support_kind,
            "expected_support_actor": expected_support_actor,
            "actual_support_actor": actual_support_actor,
        },
    )
