from __future__ import annotations

from typing import Any

from apps.placement.structure_validation import validate_structure_plan
from apps.validation.report_builder import build_rule_result


def _placement_hint(action: Any) -> dict[str, Any]:
    if hasattr(action, "raw") and isinstance(action.raw, dict):
        return dict(action.raw.get("placement_hint") or {})
    if isinstance(action, dict):
        return dict(action.get("placement_hint") or {})
    return {}


def validate_structure_functionality(
    *,
    scene_state: dict[str, Any],
    action: Any,
    enabled: bool,
    fail_hard: bool,
) -> dict[str, Any]:
    if not enabled:
        return build_rule_result(name="structure_functionality", passed=True, blocking=False, warnings=["structure_functionality validator disabled"])

    hint = _placement_hint(action)
    structure_type = str(hint.get("structure_type") or "").strip().lower()
    if not structure_type:
        return build_rule_result(
            name="structure_functionality",
            passed=True,
            blocking=False,
            details={"skipped": "no_structure_plan_available"},
        )

    structure_plan = {
        "structure_type": hint.get("structure_type"),
        "story_count": hint.get("story_count"),
        "circulation_plan": dict(hint.get("circulation_plan") or {}),
        "reserved_volumes": list(hint.get("reserved_volumes") or []),
        "functional_openings": list(hint.get("functional_openings") or []),
        "roof_envelope": dict(hint.get("roof_envelope") or {}),
        "segments": list(scene_state.get("assembly_segments") or []),
    }
    live_by_slot = {
        str(item.get("managed_slot") or ""): dict(item)
        for item in list(scene_state.get("assembly_segments") or [])
        if isinstance(item, dict) and str(item.get("managed_slot") or "").strip()
    }
    report = validate_structure_plan(structure_plan, live_actors_by_slot=live_by_slot)
    issues: list[str] = []
    for category_name in (
        "circulation_path",
        "landing_clearance",
        "opening_integrity",
        "roof_envelope_fit",
        "assembly_interference",
        "navigable_floor_fit",
    ):
        category = dict(report.get(category_name) or {})
        issues.extend(str(item) for item in list(category.get("issues") or []) if str(item).strip())
    return build_rule_result(
        name="structure_functionality",
        passed=bool(report.get("passed", False)),
        blocking=fail_hard,
        issues=issues,
        details=report,
    )
