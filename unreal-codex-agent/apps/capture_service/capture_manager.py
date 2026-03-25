from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from apps.capture_service.capture_packet import CapturePacket
from apps.integrations.uefn_backend import capture_import_root, choose_capture_backend
from apps.capture_service.image_cache import ImageCache
from apps.capture_service.shell_cameras import shell_camera_views
from apps.capture_service.zone_cameras import zone_camera_views
from apps.orchestrator.state_store import SessionStateStore


class CaptureManager:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.image_cache = ImageCache()

    @staticmethod
    def _default_profiles() -> dict[str, Any]:
        return {
            "profiles": {
                "default_room": {
                    "views": [
                        {"name": "local_object", "type": "2d", "purpose": "object_focus"},
                        {"name": "room_context", "type": "2d", "purpose": "context"},
                        {"name": "left_angle", "type": "2d", "purpose": "side_check"},
                    ],
                    "include_top_view": True,
                    "include_closeup": True,
                    "shell_crosscheck": False,
                }
            }
        }

    def _load_profiles(self) -> dict[str, Any]:
        path = self.repo_root / "config" / "capture_profiles.json"
        if not path.exists():
            return self._default_profiles()
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return self._default_profiles()
        return payload if isinstance(payload, dict) else self._default_profiles()

    def _project_capture_backend(self) -> str:
        try:
            return choose_capture_backend(self.repo_root)
        except Exception:
            return "placeholder"

    def _render_root(self, context: Any, dirty_zone: Any) -> Path:
        return context.session_path / "image_packets" / "renders" / dirty_zone.zone_id

    def _materialize_placeholder(self, path: Path, label: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return
        try:
            from PIL import Image, ImageDraw, ImageFont  # type: ignore
        except Exception:
            path.write_text(f"placeholder image for {label}", encoding="utf-8")
            return

        image = Image.new("RGB", (960, 720), color=(20, 24, 34))
        draw = ImageDraw.Draw(image)
        try:
            title_font = ImageFont.truetype("arial.ttf", 36)
            body_font = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
        draw.rectangle([(20, 20), (940, 700)], outline=(100, 170, 255), width=3)
        draw.text((50, 60), label, fill=(240, 245, 255), font=title_font)
        draw.text((50, 130), "capture placeholder", fill=(180, 195, 225), font=body_font)
        image.save(path)

    def _materialize_with_backend(self, packet_dict: dict[str, Any]) -> dict[str, Any]:
        backend = self._project_capture_backend()
        if backend == "placeholder":
            return packet_dict

        if backend.startswith("uefn_"):
            import_root = capture_import_root(self.repo_root)
            if import_root.exists():
                imported = dict(packet_dict)
                imported_images: list[dict[str, Any]] = []
                for image in list(packet_dict.get("images") or []):
                    source = import_root / packet_dict["zone_id"] / Path(str(image.get("path", ""))).name
                    if source.exists():
                        image_copy = dict(image)
                        image_copy["path"] = source.as_posix()
                        imported_images.append(image_copy)
                    else:
                        imported_images.append(dict(image))
                imported["images"] = imported_images
                imported["capture_backend"] = "uefn_capture_import"
                imported["notes"] = list(imported.get("notes", [])) + ["used imported UEFN viewport references when available"]
                return imported

        script_path = self.repo_root / "unreal" / "python" / "ue_capture_views.py"
        packet_path = self.repo_root / "data" / "cache" / "latest_scene_packets" / f"{packet_dict['zone_id']}_capture_request.json"
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        if not script_path.exists():
            fallback = dict(packet_dict)
            fallback["notes"] = list(fallback.get("notes", [])) + [f"capture backend '{backend}' is configured but the Unreal capture script is missing"]
            fallback["capture_backend"] = "placeholder"
            return fallback

        temp_path: Path | None = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=packet_path.parent, suffix=".tmp") as handle:
                handle.write(json.dumps(packet_dict, indent=2))
                temp_path = Path(handle.name)
            temp_path.replace(packet_path)
        finally:
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        completed = subprocess.run(
            [sys.executable, str(script_path), str(packet_path)],
            text=True,
            capture_output=True,
            cwd=str(self.repo_root),
            check=False,
        )
        if completed.returncode != 0 or not packet_path.exists():
            fallback = dict(packet_dict)
            fallback["notes"] = list(fallback.get("notes", [])) + [f"capture backend '{backend}' failed, used placeholder flow"]
            fallback["capture_backend"] = "placeholder"
            return fallback

        try:
            materialized = json.loads(packet_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            fallback = dict(packet_dict)
            fallback["notes"] = list(fallback.get("notes", [])) + [f"capture backend '{backend}' returned malformed output, used placeholder flow"]
            fallback["capture_backend"] = "placeholder"
            return fallback
        return materialized

    def build_capture_packet(self, context: Any, dirty_zone: Any) -> dict[str, Any]:
        profiles = self._load_profiles().get("profiles", {})
        profile_name = dirty_zone.capture_profile or "default_room"
        notes: list[str] = []
        self.image_cache.invalidate_prefix(f"{dirty_zone.zone_id}:")
        profile = profiles.get(profile_name)
        if not isinstance(profile, dict):
            profile = profiles.get("default_room", {})
            notes.append(f"capture profile '{profile_name}' was missing or invalid, used default_room")
            profile_name = "default_room"

        if dirty_zone.shell_sensitive or bool(profile.get("shell_crosscheck", False)):
            views = shell_camera_views(profile)
            shell_crosscheck = True
        else:
            views = zone_camera_views(profile)
            shell_crosscheck = bool(profile.get("shell_crosscheck", False))

        if not views:
            views = [{"name": "local_object", "type": "2d", "purpose": "object_focus"}]
            notes.append("capture profile produced no valid views, used local_object fallback")

        render_root = self._render_root(context, dirty_zone)
        images: list[dict[str, Any]] = []
        for view in views:
            image_path = render_root / f"{view['name']}.png"
            self._materialize_placeholder(image_path, view["name"])
            self.image_cache.put(f"{dirty_zone.zone_id}:{view['name']}", image_path.as_posix())
            images.append(
                {
                    "label": view["name"],
                    "path": image_path.as_posix(),
                    "image_type": view.get("type", "2d"),
                    "purpose": view.get("purpose", "unknown"),
                    "zone_id": dirty_zone.zone_id,
                }
            )

        packet = CapturePacket(
            packet_id=f"{dirty_zone.zone_id}_{SessionStateStore.utcnow_static().replace(':', '').replace('-', '')}",
            zone_id=dirty_zone.zone_id,
            profile=profile_name,
            shell_crosscheck=shell_crosscheck,
            images=images,
            notes=notes,
            timestamp_utc=SessionStateStore.utcnow_static(),
            capture_backend=self._project_capture_backend(),
        )
        packet_dict = packet.to_dict()
        materialized = self._materialize_with_backend(packet_dict)
        if materialized.get("capture_backend") == "placeholder" and materialized is packet_dict:
            for image in images:
                self._materialize_placeholder(Path(str(image["path"])), str(image["label"]))
        return materialized
