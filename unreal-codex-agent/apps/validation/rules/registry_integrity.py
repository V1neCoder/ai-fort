from __future__ import annotations

from typing import Any

from apps.validation.report_builder import build_rule_result


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _flatten_claimed_slots(managed_registry: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    zones = dict(managed_registry.get("zones") or {})
    for zone_id, zone_payload in sorted(zones.items()):
        if not isinstance(zone_payload, dict):
            continue
        slots = dict(zone_payload.get("slots") or {})
        for managed_slot, slot_payload in sorted(slots.items()):
            if not isinstance(slot_payload, dict):
                continue
            ownership = dict(slot_payload.get("ownership") or {})
            if bool(ownership.get("released", False)) or not bool(ownership.get("claimed", True)):
                continue
            records.append(
                {
                    **dict(slot_payload),
                    "zone_id": _safe_text(slot_payload.get("zone_id")) or _safe_text(zone_id),
                    "managed_slot": _safe_text(slot_payload.get("managed_slot")) or _safe_text(managed_slot) or "primary",
                }
            )
    return records


def validate_registry_integrity(
    *,
    scene_state: dict[str, Any],
    action: Any,
    enabled: bool,
    fail_hard: bool,
) -> dict[str, Any]:
    if not enabled:
        return build_rule_result(name="registry_integrity", passed=True, blocking=False, warnings=["registry_integrity validator disabled"])

    managed_registry = dict(scene_state.get("managed_registry") or {})
    if not managed_registry:
        return build_rule_result(name="registry_integrity", passed=True, blocking=False, warnings=["no managed registry snapshot was available"])

    zone_id = _safe_text(getattr(action, "target_zone", None) or (action.get("target_zone") if isinstance(action, dict) else ""))
    managed_slot = _safe_text(getattr(action, "managed_slot", None) or (action.get("managed_slot") if isinstance(action, dict) else "")) or "primary"
    action_name = _safe_text(getattr(action, "action", None) or (action.get("action") if isinstance(action, dict) else ""))
    claimed_records = _flatten_claimed_slots(managed_registry)

    duplicate_actor_paths: dict[str, list[str]] = {}
    duplicate_actor_labels: dict[str, list[str]] = {}
    for field_name, bucket in (("actor_path", duplicate_actor_paths), ("actor_label", duplicate_actor_labels)):
        grouped: dict[str, list[str]] = {}
        for record in claimed_records:
            value = _safe_text(record.get(field_name))
            if not value:
                continue
            grouped.setdefault(value, []).append(f"{record['zone_id']}:{record['managed_slot']}")
        for value, registry_keys in grouped.items():
            if len(registry_keys) > 1:
                bucket[value] = sorted(registry_keys)

    target_slot_record = None
    zones = dict(managed_registry.get("zones") or {})
    zone_payload = dict(zones.get(zone_id) or {})
    target_slot_record = dict(dict(zone_payload.get("slots") or {}).get(managed_slot) or {})
    ownership = dict(target_slot_record.get("ownership") or {})

    issues: list[str] = []
    warnings: list[str] = []

    if action_name not in {"", "no_op"}:
        if not target_slot_record:
            issues.append(f"managed registry does not contain slot {zone_id}:{managed_slot}")
        elif bool(ownership.get("released", False)) or not bool(ownership.get("claimed", True)):
            issues.append(f"managed slot {zone_id}:{managed_slot} is not currently claimed")

    for actor_path, registry_keys in sorted(duplicate_actor_paths.items()):
        issues.append(f"multiple managed slots claim actor path {actor_path}: {', '.join(registry_keys)}")
    for actor_label, registry_keys in sorted(duplicate_actor_labels.items()):
        issues.append(f"multiple managed slots claim actor label {actor_label}: {', '.join(registry_keys)}")

    return build_rule_result(
        name="registry_integrity",
        passed=len(issues) == 0,
        blocking=fail_hard,
        issues=issues,
        warnings=warnings,
        details={
            "zone_id": zone_id,
            "managed_slot": managed_slot,
            "claimed_slot_count": len(claimed_records),
            "target_slot_record": target_slot_record,
            "duplicate_actor_paths": duplicate_actor_paths,
            "duplicate_actor_labels": duplicate_actor_labels,
        },
    )
