from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from apps.integrations.uefn_backend import (
    backend_summary,
    choose_action_backend,
    choose_scene_backend,
    verse_generated_root,
)
from apps.uefn.verse_templates import render_placement_coordinator, render_scene_monitor


def _write_atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _write_atomic_text(path, json.dumps(payload, indent=2))


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _build_debug_overlay_payload(
    *,
    scene_state: dict[str, Any],
    dirty_zone: dict[str, Any],
    action_payload: dict[str, Any],
    placement_summary: dict[str, Any],
) -> dict[str, Any]:
    dirty_bounds = _dict_payload(scene_state.get("dirty_bounds") or dirty_zone.get("bounds"))
    placement_targets = _dict_payload(scene_state.get("placement_targets"))
    action_transform = _dict_payload(action_payload.get("transform"))

    def pick(*keys: str) -> Any:
        for key in keys:
            if placement_targets.get(key) is not None:
                return placement_targets.get(key)
            if dirty_bounds.get(key) is not None:
                return dirty_bounds.get(key)
            if placement_summary.get(key) is not None:
                return placement_summary.get(key)
        return None

    return {
        "zone_id": str(dirty_zone.get("zone_id") or ""),
        "room_type": str(scene_state.get("room_type") or dirty_zone.get("room_type") or "unknown"),
        "action": str(action_payload.get("action") or "no_op"),
        "asset_path": str(action_payload.get("asset_path") or ""),
        "spawn_label": str(action_payload.get("spawn_label") or ""),
        "managed_slot": str(action_payload.get("managed_slot") or "primary"),
        "identity_policy": str(action_payload.get("identity_policy") or "reuse_or_create"),
        "placement_strategy": str(action_payload.get("placement_strategy") or ""),
        "target_location": action_transform.get("location"),
        "target_rotation": action_transform.get("rotation"),
        "target_scale": action_transform.get("scale"),
        "anchor_point": pick("anchor_point"),
        "ground_anchor": pick("ground_anchor"),
        "landscape_anchor": pick("landscape_anchor"),
        "plane_anchor": pick("plane_anchor"),
        "corner_anchor": pick("corner_anchor"),
        "surface_anchor": pick("surface_anchor"),
        "support_actor_label": str(pick("support_actor_label") or ""),
        "support_actor_class": str(pick("support_actor_class") or ""),
        "support_surface_kind": str(pick("support_surface_kind") or ""),
        "support_level": pick("support_level"),
        "parent_support_actor": str(pick("parent_support_actor") or ""),
        "reference_actor_label": str(pick("reference_actor_label") or ""),
        "dirty_bounds": {
            "origin": dirty_bounds.get("origin"),
            "box_extent": dirty_bounds.get("box_extent"),
        },
    }


def export_cycle_artifacts(
    *,
    repo_root: Path,
    session_path: Path,
    cycle_number: int,
    scene_state: dict[str, Any],
    dirty_zone: dict[str, Any],
    action_payload: dict[str, Any],
    placement_summary: dict[str, Any],
) -> dict[str, Any]:
    generated_root = verse_generated_root(repo_root)
    session_bridge_root = session_path / "uefn_bridge"
    intent_root = session_bridge_root / "placement_intents"
    apply_root = session_bridge_root / "apply_queue"
    manifest_root = session_bridge_root / "manifests"
    debug_root = session_bridge_root / "debug_overlay"
    current_zone = str(dirty_zone.get("zone_id") or f"zone_{cycle_number:04d}")
    room_type = str(scene_state.get("room_type") or "unknown")
    project_name = "unreal-codex-agent"
    debug_overlay = _build_debug_overlay_payload(
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        action_payload=action_payload,
        placement_summary=placement_summary,
    )
    manifest = {
        "platform": "uefn",
        "cycle_number": cycle_number,
        "zone_id": current_zone,
        "room_type": room_type,
        "scene_backend": choose_scene_backend(repo_root),
        "action_backend": choose_action_backend(repo_root),
        "backend_summary": backend_summary(repo_root),
        "placement_summary": placement_summary,
        "action_payload": action_payload,
        "managed_action": {
            "managed_slot": str(action_payload.get("managed_slot") or "primary"),
            "identity_policy": str(action_payload.get("identity_policy") or "reuse_or_create"),
            "placement_phase": str((action_payload.get("placement_hint") or {}).get("placement_phase") or ""),
            "snap_policy": str((action_payload.get("placement_hint") or {}).get("snap_policy") or ""),
            "support_surface_kind": str((action_payload.get("placement_hint") or {}).get("support_surface_kind") or ""),
            "support_level": (action_payload.get("placement_hint") or {}).get("support_level"),
            "parent_support_actor": str((action_payload.get("placement_hint") or {}).get("parent_support_actor") or ""),
        },
        "scene_state_excerpt": {
            "map_name": scene_state.get("map_name"),
            "room_type": room_type,
            "expected_mount_type": scene_state.get("expected_mount_type"),
            "dirty_actor_ids": scene_state.get("dirty_actor_ids", []),
            "placement_targets": scene_state.get("placement_targets", {}),
            "support_graph": scene_state.get("support_graph", []),
        },
        "debug_overlay": debug_overlay,
    }

    intent_path = intent_root / f"cycle_{cycle_number:04d}.json"
    current_intent_path = intent_root / "current.json"
    apply_path = apply_root / f"cycle_{cycle_number:04d}.json"
    current_apply_path = apply_root / "current.json"
    manifest_path = manifest_root / f"cycle_{cycle_number:04d}.json"
    current_manifest_path = manifest_root / "current.json"
    debug_overlay_path = debug_root / f"cycle_{cycle_number:04d}.json"
    current_debug_overlay_path = debug_root / "current.json"
    placement_verse_path = generated_root / "UCA_PlacementCoordinator.generated.verse"
    scene_monitor_path = generated_root / "UCA_SceneMonitor.generated.verse"

    _write_atomic_json(intent_path, action_payload)
    _write_atomic_json(current_intent_path, action_payload)
    _write_atomic_json(apply_path, manifest["managed_action"] | {"action_payload": action_payload, "cycle_number": cycle_number, "zone_id": current_zone})
    _write_atomic_json(current_apply_path, manifest["managed_action"] | {"action_payload": action_payload, "cycle_number": cycle_number, "zone_id": current_zone})
    _write_atomic_json(manifest_path, manifest)
    _write_atomic_json(current_manifest_path, manifest)
    _write_atomic_json(debug_overlay_path, debug_overlay)
    _write_atomic_json(current_debug_overlay_path, debug_overlay)
    _write_atomic_text(
        placement_verse_path,
        render_placement_coordinator(
            project_name=project_name,
            zone_id=current_zone,
            cycle_number=cycle_number,
            action_payload=action_payload,
            placement_summary=placement_summary,
            debug_overlay=debug_overlay,
        ),
    )
    _write_atomic_text(
        scene_monitor_path,
        render_scene_monitor(
            project_name=project_name,
            room_type=room_type,
            scene_backend=choose_scene_backend(repo_root),
        ),
    )

    return {
        "status": "ok",
        "action_backend": choose_action_backend(repo_root),
        "scene_backend": choose_scene_backend(repo_root),
        "artifacts": {
            "intent_path": intent_path.as_posix(),
            "apply_path": apply_path.as_posix(),
            "manifest_path": manifest_path.as_posix(),
            "debug_overlay_path": debug_overlay_path.as_posix(),
            "placement_verse_path": placement_verse_path.as_posix(),
            "scene_monitor_path": scene_monitor_path.as_posix(),
        },
    }


def apply_action_via_verse_export(
    *,
    repo_root: Path,
    session_path: Path,
    cycle_number: int,
    scene_state: dict[str, Any],
    dirty_zone: dict[str, Any],
    action_payload: dict[str, Any],
) -> dict[str, Any]:
    artifacts = export_cycle_artifacts(
        repo_root=repo_root,
        session_path=session_path,
        cycle_number=cycle_number,
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        action_payload=action_payload,
        placement_summary=dict(scene_state.get("placement_context") or {}),
    )
    return {
        "status": "exported",
        "backend": "uefn_verse_apply",
        "applied_mode": "uefn_verse_apply",
        "degraded_to_fallback": True,
        "applied": False,
        "action": str(action_payload.get("action") or "no_op"),
        "placement_phase": str((action_payload.get("placement_hint") or {}).get("placement_phase") or ""),
        "snap_policy": str((action_payload.get("placement_hint") or {}).get("snap_policy") or ""),
        "managed_slot": str(action_payload.get("managed_slot") or "primary"),
        "identity_policy": str(action_payload.get("identity_policy") or "reuse_or_create"),
        "registry_status": "claimed",
        "reconciled_actor_path": "",
        "reconciliation_attempted": False,
        "reconciliation_status": "clean",
        "drift_status": "none",
        "reason": "Action was exported for publish-safe Verse/device handling.",
        "artifacts": artifacts.get("artifacts", {}),
    }
