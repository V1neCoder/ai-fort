from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_capture_images(capture_packet: dict[str, Any]) -> list[dict[str, Any]]:
    images = capture_packet.get("images", []) or []
    normalized: list[dict[str, Any]] = []
    for image in images:
        path = str(image.get("path", ""))
        normalized.append(
            {
                "label": image.get("label", "unknown"),
                "path": path,
                "exists": Path(path).exists() if path else False,
                "image_type": image.get("image_type", "2d"),
                "purpose": image.get("purpose", "unknown"),
                "zone_id": image.get("zone_id"),
            }
        )
    return normalized


def build_image_review_summary(capture_packet: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_capture_images(capture_packet)
    return {
        "packet_id": capture_packet.get("packet_id"),
        "zone_id": capture_packet.get("zone_id"),
        "profile": capture_packet.get("profile"),
        "shell_crosscheck": bool(capture_packet.get("shell_crosscheck", False)),
        "image_count": len(normalized),
        "images": normalized,
        "notes": capture_packet.get("notes", []),
    }
