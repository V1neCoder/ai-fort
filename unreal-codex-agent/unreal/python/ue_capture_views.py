from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import unreal  # type: ignore
except Exception:
    unreal = None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ensure_placeholder(path: Path, label: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(f"placeholder image for {label}", encoding="utf-8")
        return
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1024, 768), color=(20, 24, 34))
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("arial.ttf", 40)
        body_font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.rectangle([(20, 20), (1004, 748)], outline=(100, 170, 255), width=3)
    draw.text((50, 70), label, fill=(240, 245, 255), font=title_font)
    draw.text((50, 140), "Unreal capture placeholder", fill=(180, 195, 225), font=body_font)
    draw.text((50, 185), "Replace with real viewport/camera capture later", fill=(160, 170, 190), font=body_font)
    image.save(path)


def materialize_capture_packet(packet: dict[str, Any]) -> dict[str, Any]:
    images = packet.get("images", []) or []
    realized = []
    for image in images:
        path = Path(str(image.get("path", "")))
        label = str(image.get("label", "unknown"))
        _ensure_placeholder(path, label)
        realized.append({"label": label, "path": path.as_posix(), "exists": path.exists(), "mode": "placeholder"})
    packet_out = dict(packet)
    packet_out["materialized_images"] = realized
    packet_out["capture_backend"] = "placeholder"
    return packet_out


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "reason": "usage: ue_capture_views.py <packet_json_path>"}))
    else:
        packet_path = Path(sys.argv[1])
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        result = materialize_capture_packet(packet)
        _write_json(packet_path, result)
        print(json.dumps({"status": "ok", "packet_path": packet_path.as_posix()}, indent=2))
