from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from apps.orchestrator.state_store import SessionStateStore

REGISTRY_VERSION = 1
DEFAULT_MANAGED_SLOT = "primary"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _registry_shape() -> dict[str, Any]:
    return {
        "version": REGISTRY_VERSION,
        "zones": {},
        "updated_at_utc": SessionStateStore.utcnow_static(),
    }


def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(json.dumps(payload, indent=2))
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def registry_path(session_path: Path) -> Path:
    return session_path / "managed_layout.json"


def load_registry(session_path: Path) -> dict[str, Any]:
    path = registry_path(session_path)
    if not path.exists():
        return _registry_shape()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return _registry_shape()
    if not isinstance(payload, dict):
        return _registry_shape()
    payload.setdefault("version", REGISTRY_VERSION)
    payload.setdefault("zones", {})
    payload.setdefault("updated_at_utc", SessionStateStore.utcnow_static())
    return payload


def save_registry(session_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload or {})
    normalized.setdefault("version", REGISTRY_VERSION)
    normalized.setdefault("zones", {})
    normalized["updated_at_utc"] = SessionStateStore.utcnow_static()
    _write_atomic_json(registry_path(session_path), normalized)
    return normalized


def default_managed_slot(action_payload: dict[str, Any] | None) -> str:
    payload = dict(action_payload or {})
    raw = _safe_text(payload.get("managed_slot"))
    return raw or DEFAULT_MANAGED_SLOT


def default_identity_policy(action_name: str) -> str:
    normalized = _safe_text(action_name).lower()
    if normalized == "place_asset":
        return "reuse_or_create"
    if normalized in {"move_actor", "set_transform", "rotate_actor", "scale_actor", "delete_actor"}:
        return "reuse_only"
    return "reuse_or_create"


def managed_record_key(zone_id: str, managed_slot: str) -> str:
    return f"{_safe_text(zone_id) or 'unknown_zone'}:{_safe_text(managed_slot) or DEFAULT_MANAGED_SLOT}"


def get_zone(session_path: Path, zone_id: str) -> dict[str, Any]:
    registry = load_registry(session_path)
    zones = dict(registry.get("zones") or {})
    zone = dict(zones.get(_safe_text(zone_id)) or {})
    zone.setdefault("slots", {})
    return zone


def get_slot_record(session_path: Path, zone_id: str, managed_slot: str = DEFAULT_MANAGED_SLOT) -> dict[str, Any] | None:
    zone = get_zone(session_path, zone_id)
    slots = dict(zone.get("slots") or {})
    slot = dict(slots.get(_safe_text(managed_slot) or DEFAULT_MANAGED_SLOT) or {})
    if not slot:
        return None
    slot.setdefault("managed_slot", _safe_text(managed_slot) or DEFAULT_MANAGED_SLOT)
    slot.setdefault("zone_id", _safe_text(zone_id))
    return slot


def upsert_slot_record(
    session_path: Path,
    *,
    zone_id: str,
    managed_slot: str,
    action_name: str,
    identity_policy: str,
    actor_label: str,
    actor_path: str,
    asset_path: str,
    support_reference: dict[str, Any] | None,
    placement_phase: str,
    last_confirmed_transform: dict[str, Any] | None,
    fit_status: dict[str, Any] | None,
    registry_status: str,
    ownership: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = load_registry(session_path)
    zones = dict(registry.get("zones") or {})
    zone_key = _safe_text(zone_id) or "unknown_zone"
    slot_key = _safe_text(managed_slot) or DEFAULT_MANAGED_SLOT
    zone = dict(zones.get(zone_key) or {})
    slots = dict(zone.get("slots") or {})
    existing = dict(slots.get(slot_key) or {})
    created_at = _safe_text(existing.get("created_at_utc")) or SessionStateStore.utcnow_static()
    record = {
        "zone_id": zone_key,
        "managed_slot": slot_key,
        "registry_key": managed_record_key(zone_key, slot_key),
        "action_name": _safe_text(action_name),
        "identity_policy": _safe_text(identity_policy) or default_identity_policy(action_name),
        "actor_label": _safe_text(actor_label),
        "actor_path": _safe_text(actor_path),
        "asset_path": _safe_text(asset_path),
        "support_reference": dict(support_reference or {}),
        "placement_phase": _safe_text(placement_phase) or "initial_place",
        "last_confirmed_transform": dict(last_confirmed_transform or {}),
        "fit_status": dict(fit_status or {}),
        "registry_status": _safe_text(registry_status) or "claimed",
        "ownership": {
            "claimed": True,
            "released": False,
            "allow_cleanup": True,
            **dict(existing.get("ownership") or {}),
            **dict(ownership or {}),
        },
        "created_at_utc": created_at,
        "updated_at_utc": SessionStateStore.utcnow_static(),
    }
    slots[slot_key] = record
    zone["slots"] = slots
    zone["updated_at_utc"] = SessionStateStore.utcnow_static()
    zones[zone_key] = zone
    registry["zones"] = zones
    save_registry(session_path, registry)
    return record


def release_slot(
    session_path: Path,
    *,
    zone_id: str,
    managed_slot: str = DEFAULT_MANAGED_SLOT,
    reason: str = "",
) -> dict[str, Any] | None:
    registry = load_registry(session_path)
    zones = dict(registry.get("zones") or {})
    zone_key = _safe_text(zone_id) or "unknown_zone"
    slot_key = _safe_text(managed_slot) or DEFAULT_MANAGED_SLOT
    zone = dict(zones.get(zone_key) or {})
    slots = dict(zone.get("slots") or {})
    existing = dict(slots.get(slot_key) or {})
    if not existing:
        return None
    existing["registry_status"] = "released"
    existing["ownership"] = {
        **dict(existing.get("ownership") or {}),
        "claimed": False,
        "released": True,
    }
    existing["release_reason"] = _safe_text(reason)
    existing["updated_at_utc"] = SessionStateStore.utcnow_static()
    slots[slot_key] = existing
    zone["slots"] = slots
    zones[zone_key] = zone
    registry["zones"] = zones
    save_registry(session_path, registry)
    return existing


def registry_owned_actor_paths(session_path: Path) -> set[str]:
    registry = load_registry(session_path)
    owned: set[str] = set()
    for zone in dict(registry.get("zones") or {}).values():
        if not isinstance(zone, dict):
            continue
        for slot in dict(zone.get("slots") or {}).values():
            if not isinstance(slot, dict):
                continue
            ownership = dict(slot.get("ownership") or {})
            actor_path = _safe_text(slot.get("actor_path"))
            if actor_path and bool(ownership.get("claimed", True)) and not bool(ownership.get("released", False)):
                owned.add(actor_path)
    return owned


def registry_owned_actor_labels(session_path: Path) -> set[str]:
    registry = load_registry(session_path)
    owned: set[str] = set()
    for zone in dict(registry.get("zones") or {}).values():
        if not isinstance(zone, dict):
            continue
        for slot in dict(zone.get("slots") or {}).values():
            if not isinstance(slot, dict):
                continue
            ownership = dict(slot.get("ownership") or {})
            actor_label = _safe_text(slot.get("actor_label"))
            if actor_label and bool(ownership.get("claimed", True)) and not bool(ownership.get("released", False)):
                owned.add(actor_label)
    return owned


def managed_records_for_zone(session_path: Path, zone_id: str) -> list[dict[str, Any]]:
    zone = get_zone(session_path, zone_id)
    slots = dict(zone.get("slots") or {})
    records: list[dict[str, Any]] = []
    for key in sorted(slots):
        slot = dict(slots.get(key) or {})
        if not slot:
            continue
        records.append(slot)
    return records


def claimed_records(session_path: Path) -> list[dict[str, Any]]:
    registry = load_registry(session_path)
    records: list[dict[str, Any]] = []
    for zone_key, zone in sorted(dict(registry.get("zones") or {}).items()):
        if not isinstance(zone, dict):
            continue
        for slot_key, slot in sorted(dict(zone.get("slots") or {}).items()):
            if not isinstance(slot, dict):
                continue
            ownership = dict(slot.get("ownership") or {})
            if bool(ownership.get("released", False)) or not bool(ownership.get("claimed", True)):
                continue
            record = dict(slot)
            record.setdefault("zone_id", _safe_text(zone_key))
            record.setdefault("managed_slot", _safe_text(slot_key) or DEFAULT_MANAGED_SLOT)
            records.append(record)
    return records


def detect_duplicate_claims(session_path: Path) -> dict[str, list[dict[str, Any]]]:
    by_actor_path: dict[str, list[dict[str, Any]]] = {}
    by_actor_label: dict[str, list[dict[str, Any]]] = {}
    for record in claimed_records(session_path):
        actor_path = _safe_text(record.get("actor_path"))
        actor_label = _safe_text(record.get("actor_label"))
        if actor_path:
            by_actor_path.setdefault(actor_path, []).append(record)
        if actor_label:
            by_actor_label.setdefault(actor_label, []).append(record)
    return {
        "actor_paths": [
            {"actor_path": key, "records": value}
            for key, value in sorted(by_actor_path.items())
            if len(value) > 1
        ],
        "actor_labels": [
            {"actor_label": key, "records": value}
            for key, value in sorted(by_actor_label.items())
            if len(value) > 1
        ],
    }


def zone_registry_snapshot(session_path: Path, zone_id: str) -> dict[str, Any]:
    zone = get_zone(session_path, zone_id)
    slots = dict(zone.get("slots") or {})
    return {
        "zone_id": _safe_text(zone_id),
        "slot_count": len(slots),
        "slots": {
            slot_key: {
                "actor_label": _safe_text(slot.get("actor_label")),
                "actor_path": _safe_text(slot.get("actor_path")),
                "asset_path": _safe_text(slot.get("asset_path")),
                "registry_status": _safe_text(slot.get("registry_status")),
                "placement_phase": _safe_text(slot.get("placement_phase")),
                "support_reference": dict(slot.get("support_reference") or {}),
                "fit_status": dict(slot.get("fit_status") or {}),
                "ownership": dict(slot.get("ownership") or {}),
            }
            for slot_key, slot in sorted(slots.items())
            if isinstance(slot, dict)
        },
    }


def registry_layout_snapshot(session_path: Path) -> dict[str, Any]:
    registry = load_registry(session_path)
    summary: dict[str, Any] = {
        "version": registry.get("version", REGISTRY_VERSION),
        "updated_at_utc": registry.get("updated_at_utc"),
        "zones": {},
    }
    for zone_key, zone in sorted(dict(registry.get("zones") or {}).items()):
        if not isinstance(zone, dict):
            continue
        slots = dict(zone.get("slots") or {})
        summary["zones"][zone_key] = {
            "slot_count": len(slots),
            "slots": {
                slot_key: {
                    "actor_label": _safe_text(slot.get("actor_label")),
                    "actor_path": _safe_text(slot.get("actor_path")),
                    "asset_path": _safe_text(slot.get("asset_path")),
                    "registry_status": _safe_text(slot.get("registry_status")),
                    "placement_phase": _safe_text(slot.get("placement_phase")),
                    "support_reference": dict(slot.get("support_reference") or {}),
                    "fit_status": dict(slot.get("fit_status") or {}),
                }
                for slot_key, slot in sorted(slots.items())
                if isinstance(slot, dict)
            },
        }
    return summary
