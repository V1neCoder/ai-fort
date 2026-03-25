from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from apps.integrations.uefn_backend import choose_action_backend, choose_capture_backend
from apps.capture_service.capture_manager import CaptureManager
from apps.mcp_extensions.scene_tools import derive_dirty_zone, enrich_scene_state, load_scene_state_for_context
from apps.orchestrator.dirty_zone import DirtyZone

app = typer.Typer(help="Capture helper tools for local MCP-style workflows.")


class _CaptureContext:
    def __init__(self, repo_root: Path, session_path: Path) -> None:
        self.repo_root = repo_root
        self.session_path = session_path


def build_capture_for_zone(
    *,
    repo_root: Path,
    session_path: Path,
    dirty_zone_payload: dict[str, Any],
) -> dict[str, Any]:
    session_path.mkdir(parents=True, exist_ok=True)
    manager = CaptureManager(repo_root=repo_root)
    dirty_zone = DirtyZone(
        zone_id=str(dirty_zone_payload.get("zone_id") or "zone_0001"),
        actor_ids=list(dirty_zone_payload.get("actor_ids", [])) if isinstance(dirty_zone_payload.get("actor_ids"), list) else [],
        room_type=str(dirty_zone_payload.get("room_type") or "unknown"),
        zone_type=str(dirty_zone_payload.get("zone_type") or "generic"),
        shell_sensitive=bool(dirty_zone_payload.get("shell_sensitive", False)),
        capture_profile=str(dirty_zone_payload.get("capture_profile") or "default_room"),
        bounds=dict(dirty_zone_payload.get("bounds", {})) if isinstance(dirty_zone_payload.get("bounds"), dict) else {},
    )
    packet = manager.build_capture_packet(_CaptureContext(repo_root, session_path), dirty_zone)
    packet.setdefault("notes", [])
    packet["notes"] = list(packet["notes"]) + [
        f"capture_backend_selected={packet.get('capture_backend', 'placeholder')}",
        f"capture_backend_preferred={choose_capture_backend(repo_root)}",
        f"action_backend_preferred={choose_action_backend(repo_root)}",
    ]
    packet["status"] = "ok"
    packet["image_count"] = len(list(packet.get("images") or []))
    packet["warning_count"] = len([note for note in list(packet.get("notes") or []) if str(note).strip()])
    return packet


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


@app.command("zone")
def capture_zone_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_path: Path = typer.Option(Path("./data/sessions/manual_capture"), help="Session path used for image output."),
    dirty_zone_json: Path | None = typer.Option(None, help="Path to dirty zone JSON."),
    session_id: str | None = typer.Option(None, help="Session id used to derive a dirty zone."),
    cycle_number: int = typer.Option(1, help="Cycle number used with --session-id."),
) -> None:
    if dirty_zone_json is None and session_id is None:
        raise typer.BadParameter("Provide --dirty-zone-json or --session-id.")
    warnings: list[str] = []
    if dirty_zone_json is not None:
        try:
            dirty_zone_payload = _load_json(dirty_zone_json)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"dirty zone payload could not be parsed cleanly: {exc}")
            dirty_zone_payload = {"zone_id": f"zone_{cycle_number:04d}"}
    else:
        resolved_session_path = repo_root / "data" / "sessions" / str(session_id)
        session_path = resolved_session_path
        scene_state_path = resolved_session_path / "scene_state" / f"cycle_{cycle_number:04d}.json"
        if not scene_state_path.exists():
            warnings.append(f"missing scene state for session/cycle: {scene_state_path}")
            scene_state = enrich_scene_state({}, repo_root)
        else:
            try:
                scene_state = enrich_scene_state(_load_json(scene_state_path), repo_root)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"scene state could not be parsed cleanly: {exc}")
                scene_state = enrich_scene_state({}, repo_root)
        dirty_zone_payload = derive_dirty_zone(scene_state=scene_state, cycle_number=cycle_number)
    packet = build_capture_for_zone(repo_root=repo_root, session_path=session_path, dirty_zone_payload=dirty_zone_payload)
    if warnings:
        packet["notes"] = list(packet.get("notes", [])) + warnings
    typer.echo(json.dumps(packet, indent=2))


@app.command("scene")
def capture_scene_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_path: Path = typer.Option(Path("./data/sessions/manual_capture"), help="Session path used for image output."),
    cycle_number: int = typer.Option(1, help="Cycle number used to derive the zone."),
) -> None:
    scene_state = load_scene_state_for_context(repo_root)
    dirty_zone_payload = derive_dirty_zone(scene_state=scene_state, cycle_number=cycle_number)
    typer.echo(json.dumps(build_capture_for_zone(repo_root=repo_root, session_path=session_path, dirty_zone_payload=dirty_zone_payload), indent=2))


def capture_tools() -> list[str]:
    return ["scene", "zone"]


if __name__ == "__main__":
    app()
