import json
from pathlib import Path

from apps.capture_service.capture_manager import CaptureManager
from apps.orchestrator.dirty_zone import DirtyZone


class DummyContext:
    def __init__(self, repo_root: Path, session_path: Path) -> None:
        self.repo_root = repo_root
        self.session_path = session_path


def write_capture_profiles(repo_root: Path) -> None:
    config_dir = repo_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "profiles": {
            "default_room": {
                "max_images": 6,
                "views": [
                    {"name": "local_object", "type": "2d", "purpose": "object_focus"},
                    {"name": "room_context", "type": "2d", "purpose": "context"},
                    {"name": "left_angle", "type": "2d", "purpose": "side_check"},
                ],
                "use_cube_capture_for_hard_cases": True,
                "include_top_view": True,
                "include_closeup": True,
                "shell_crosscheck": False,
            },
            "shell_sensitive": {
                "max_images": 8,
                "views": [
                    {"name": "local_object", "type": "2d", "purpose": "object_focus"},
                    {"name": "outside_context", "type": "2d", "purpose": "exterior_check"},
                ],
                "use_cube_capture_for_hard_cases": True,
                "include_top_view": True,
                "include_closeup": True,
                "shell_crosscheck": True,
            },
        },
    }
    (config_dir / "capture_profiles.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_capture_manager_builds_packet_and_materializes_placeholder_images(tmp_path: Path):
    repo_root = tmp_path
    write_capture_profiles(repo_root)

    session_path = repo_root / "data" / "sessions" / "test_session"
    session_path.mkdir(parents=True, exist_ok=True)

    context = DummyContext(repo_root=repo_root, session_path=session_path)
    manager = CaptureManager(repo_root=repo_root)

    dirty_zone = DirtyZone(
        zone_id="zone_0001",
        actor_ids=["Actor_A"],
        room_type="living_room",
        zone_type="room_local",
        shell_sensitive=False,
        capture_profile="default_room",
        bounds={},
    )

    packet = manager.build_capture_packet(context=context, dirty_zone=dirty_zone)

    assert packet["zone_id"] == "zone_0001"
    assert packet["profile"] == "default_room"
    assert len(packet["images"]) >= 4

    labels = {image["label"] for image in packet["images"]}
    assert "local_object" in labels
    assert "room_context" in labels
    assert "closeup_detail" in labels or "top_view" in labels

    for image in packet["images"]:
        assert Path(image["path"]).exists()


def test_capture_manager_adds_shell_crosscheck_views(tmp_path: Path):
    repo_root = tmp_path
    write_capture_profiles(repo_root)

    session_path = repo_root / "data" / "sessions" / "test_session"
    session_path.mkdir(parents=True, exist_ok=True)

    context = DummyContext(repo_root=repo_root, session_path=session_path)
    manager = CaptureManager(repo_root=repo_root)

    dirty_zone = DirtyZone(
        zone_id="zone_shell",
        actor_ids=["Window_A"],
        room_type="facade",
        zone_type="shell_boundary",
        shell_sensitive=True,
        capture_profile="shell_sensitive",
        bounds={},
    )

    packet = manager.build_capture_packet(context=context, dirty_zone=dirty_zone)
    labels = {image["label"] for image in packet["images"]}

    assert packet["shell_crosscheck"] is True
    assert "outside_context" in labels
    assert "inside_context" in labels
    assert "cross_boundary" in labels
