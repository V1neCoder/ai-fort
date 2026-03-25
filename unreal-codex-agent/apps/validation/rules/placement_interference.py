from __future__ import annotations

from typing import Any

from apps.validation.report_builder import build_rule_result


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _placement_hint(action: Any) -> dict[str, Any]:
    if hasattr(action, "raw") and isinstance(action.raw, dict):
        return dict(action.raw.get("placement_hint") or {})
    if isinstance(action, dict):
        return dict(action.get("placement_hint") or {})
    return {}


def validate_placement_interference(
    *,
    scene_state: dict[str, Any],
    action: Any,
    enabled: bool,
    fail_hard: bool,
) -> dict[str, Any]:
    if not enabled:
        return build_rule_result(name="placement_interference", passed=True, blocking=False, warnings=["placement_interference validator disabled"])

    active_actor = dict(scene_state.get("active_actor") or {})
    report = dict(active_actor.get("interference_report") or scene_state.get("interference_report") or {})
    if not report:
        return build_rule_result(
            name="placement_interference",
            passed=True,
            blocking=False,
            details={"skipped": "no_interference_report_available"},
        )

    hint = _placement_hint(action)
    placement_phase = _safe_text(hint.get("placement_phase") or "initial_place").lower()
    interference_policy = _safe_text(report.get("interference_policy") or hint.get("interference_policy") or "avoid").lower()
    blocking_count = int(report.get("blocking_interference_count") or 0)
    duplicate_count = int(report.get("duplicate_count") or 0)
    support_occupancy_count = int(report.get("support_occupancy_count") or 0)
    reserved_volume_conflict_count = int(report.get("reserved_volume_conflict_count") or 0)
    support_mismatch = bool(report.get("support_mismatch", False))
    status = _safe_text(report.get("interference_status") or "")

    issues: list[str] = []
    warnings: list[str] = []
    if blocking_count > 0:
        issues.append(f"{blocking_count} blocking overlap(s) remain after placement reconciliation")
    if duplicate_count > 0 and interference_policy != "allow":
        issues.append(f"{duplicate_count} duplicate actor(s) remain near the managed placement")
    if support_occupancy_count > 0 and interference_policy != "allow":
        issues.append(f"{support_occupancy_count} occupied footprint overlap(s) remain on the support surface")
    if reserved_volume_conflict_count > 0 and interference_policy != "allow":
        issues.append(f"{reserved_volume_conflict_count} reserved functional volume conflict(s) remain after placement reconciliation")
    if support_mismatch:
        support_contact = dict(report.get("support_contact") or {})
        observed_kind = _safe_text(support_contact.get("support_surface_kind") or "unknown support")
        expected_kind = _safe_text(report.get("expected_mount_type") or "current mount")
        issues.append(f"actor is resting on incompatible support {observed_kind} for mount type {expected_kind}")

    if placement_phase == "reposition" and interference_policy == "allow":
        issues = []
        warnings = []

    return build_rule_result(
        name="placement_interference",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={
            "placement_phase": placement_phase,
            "interference_policy": interference_policy,
            "interference_status": status,
            "blocking_interference_count": blocking_count,
            "duplicate_count": duplicate_count,
            "support_occupancy_count": support_occupancy_count,
            "reserved_volume_conflict_count": reserved_volume_conflict_count,
            "support_mismatch": support_mismatch,
            "blocking_overlaps": list(report.get("blocking_overlaps") or []),
            "duplicates": list(report.get("duplicates") or []),
            "support_contact": dict(report.get("support_contact") or {}),
            "support_occupancy": list(report.get("support_occupancy") or []),
            "reserved_volume_conflicts": list(report.get("reserved_volume_conflicts") or []),
            "interference_correction": dict(report.get("interference_correction") or {}),
            "duplicate_cleanup": dict(report.get("duplicate_cleanup") or {}),
        },
    )
