from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DirtyZone:
    zone_id: str
    actor_ids: list[str] = field(default_factory=list)
    room_type: str = "unknown"
    zone_type: str = "generic"
    shell_sensitive: bool = False
    capture_profile: str = "default_room"
    bounds: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "actor_ids": self.actor_ids,
            "room_type": self.room_type,
            "zone_type": self.zone_type,
            "shell_sensitive": self.shell_sensitive,
            "capture_profile": self.capture_profile,
            "bounds": self.bounds,
        }


class DirtyZoneDetector:
    def detect(self, scene_state: dict[str, Any], cycle_number: int) -> DirtyZone:
        dirty_actor_ids = scene_state.get("dirty_actor_ids", [])
        touched_room_type = scene_state.get("room_type", "unknown")
        shell_sensitive = bool(scene_state.get("shell_sensitive", False))
        expected_mount_type = str(scene_state.get("expected_mount_type") or "unknown")

        if expected_mount_type == "roof":
            capture_profile = "shell_sensitive"
            zone_type = "roof_edge"
            shell_sensitive = True
        elif shell_sensitive or expected_mount_type == "opening":
            capture_profile = "shell_sensitive"
            zone_type = "shell_boundary"
        elif expected_mount_type == "corner":
            capture_profile = "tight_interior"
            zone_type = "corner_anchor"
        elif touched_room_type in {"kitchen", "bathroom", "powder_room", "pantry"}:
            capture_profile = "tight_interior"
            zone_type = "room_local"
        else:
            capture_profile = "default_room"
            zone_type = "room_local"

        return DirtyZone(
            zone_id=f"zone_{cycle_number:04d}",
            actor_ids=dirty_actor_ids,
            room_type=touched_room_type,
            zone_type=zone_type,
            shell_sensitive=shell_sensitive,
            capture_profile=capture_profile,
            bounds=scene_state.get("dirty_bounds", {}),
        )
