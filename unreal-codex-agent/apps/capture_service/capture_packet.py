from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CapturePacket:
    packet_id: str = ""
    zone_id: str = ""
    profile: str = "default_room"
    shell_crosscheck: bool = False
    images: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    timestamp_utc: str = ""
    capture_backend: str = "placeholder"

    @property
    def image_paths(self) -> list[str]:
        return [str(image.get("path", "")) for image in self.images]

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "zone_id": self.zone_id,
            "profile": self.profile,
            "shell_crosscheck": self.shell_crosscheck,
            "images": self.images,
            "notes": self.notes,
            "timestamp_utc": self.timestamp_utc,
            "capture_backend": self.capture_backend,
        }
