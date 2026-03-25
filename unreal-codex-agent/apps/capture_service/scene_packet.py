from __future__ import annotations

from typing import Any


def build_scene_packet(
    *,
    build_goal: str,
    scene_state: dict[str, Any],
    dirty_zone: dict[str, Any],
    capture_packet: dict[str, Any],
    shortlist: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    shortlist_rows = shortlist or []
    placement_context = dict(scene_state.get("placement_context") or {}) if isinstance(scene_state, dict) else {}
    image_count = len(list(capture_packet.get("images") or [])) if isinstance(capture_packet, dict) else 0
    return {
        "build_goal": build_goal,
        "scene_state": scene_state,
        "dirty_zone": dirty_zone,
        "capture_packet": capture_packet,
        "shortlist": shortlist_rows,
        "summary": {
            "room_type": (scene_state or {}).get("room_type") if isinstance(scene_state, dict) else None,
            "expected_mount_type": (scene_state or {}).get("expected_mount_type") if isinstance(scene_state, dict) else None,
            "placement_family": placement_context.get("placement_family"),
            "placement_phase": placement_context.get("placement_phase"),
            "snap_policy": placement_context.get("snap_policy"),
            "support_surface_kind": ((scene_state or {}).get("placement_targets") or {}).get("support_surface_kind") if isinstance(scene_state, dict) else None,
            "image_count": image_count,
            "shortlist_count": len(shortlist_rows),
            "shell_sensitive": bool((dirty_zone or {}).get("shell_sensitive", False)) if isinstance(dirty_zone, dict) else False,
            "capture_profile": (capture_packet or {}).get("profile") if isinstance(capture_packet, dict) else None,
            "capture_backend": (capture_packet or {}).get("capture_backend") if isinstance(capture_packet, dict) else None,
        },
    }
