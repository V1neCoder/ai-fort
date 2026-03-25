from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from apps.integrations.uefn_backend import choose_action_backend, choose_scene_backend
from apps.orchestrator.action_queue import Action
from apps.orchestrator.dirty_zone import DirtyZone
from apps.mcp_extensions.scene_tools import derive_dirty_zone, enrich_scene_state
from apps.validation.run_validators import LocalValidator

app = typer.Typer(help="Validator helper tools for local MCP-style workflows.")


@app.callback()
def _app_callback() -> None:
    """Require explicit subcommands for validator helper tooling."""


def run_validation(
    *,
    repo_root: Path,
    scene_state: dict[str, Any],
    dirty_zone_payload: dict[str, Any],
    action_payload: dict[str, Any],
) -> dict[str, Any]:
    validator = LocalValidator(repo_root=repo_root)
    dirty_zone = DirtyZone(
        zone_id=str(dirty_zone_payload.get("zone_id") or "zone_0001"),
        actor_ids=list(dirty_zone_payload.get("actor_ids", [])) if isinstance(dirty_zone_payload.get("actor_ids"), list) else [],
        room_type=str(dirty_zone_payload.get("room_type") or "unknown"),
        zone_type=str(dirty_zone_payload.get("zone_type") or "generic"),
        shell_sensitive=bool(dirty_zone_payload.get("shell_sensitive", False)),
        capture_profile=str(dirty_zone_payload.get("capture_profile") or "default_room"),
        bounds=dict(dirty_zone_payload.get("bounds", {})) if isinstance(dirty_zone_payload.get("bounds"), dict) else {},
    )
    action = Action.from_dict(action_payload)
    report = validator.validate(context=None, scene_state=scene_state, dirty_zone=dirty_zone, action=action)
    report["validation_backend"] = "local_rules"
    report["scene_state_backend"] = choose_scene_backend(repo_root)
    report["action_backend"] = choose_action_backend(repo_root)
    return report


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def _load_action_from_history(session_path: Path, cycle_number: int) -> tuple[dict[str, Any], list[str]]:
    action_history_path = session_path / "action_history.jsonl"
    if not action_history_path.exists():
        return {}, [f"missing action history: {action_history_path}"]
    last_match: dict[str, Any] | None = None
    warnings: list[str] = []
    for raw_line in action_history_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            warnings.append("skipped malformed action history row")
            continue
        if int(payload.get("cycle_number", -1)) == cycle_number:
            last_match = payload
    if last_match is None:
        warnings.append(f"no action record found for cycle {cycle_number}")
        return {}, warnings
    return dict(last_match.get("action") or {}), warnings


@app.command("run")
def run_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    scene_state_json: Path | None = typer.Option(None, help="Path to scene state JSON."),
    dirty_zone_json: Path | None = typer.Option(None, help="Path to dirty zone JSON."),
    action_json: Path | None = typer.Option(None, help="Path to action JSON."),
    session_id: str | None = typer.Option(None, help="Session id for deriving saved inputs."),
    cycle_number: int = typer.Option(1, help="Cycle number used with --session-id."),
) -> None:
    if scene_state_json is None and session_id is None:
        raise typer.BadParameter("Provide --scene-state-json or --session-id.")

    helper_warnings: list[str] = []

    if session_id:
        session_path = repo_root / "data" / "sessions" / session_id
        if not session_path.exists():
            raise typer.BadParameter(f"Unknown session_id: {session_id}")
        if scene_state_json is None:
            scene_state_json = session_path / "scene_state" / f"cycle_{cycle_number:04d}.json"
        if action_json is None:
            action_payload, warnings = _load_action_from_history(session_path, cycle_number)
            helper_warnings.extend(warnings)
        else:
            try:
                action_payload = _load_json(action_json)
            except Exception as exc:  # noqa: BLE001
                helper_warnings.append(f"action payload could not be parsed cleanly: {exc}")
                action_payload = {}
    else:
        if action_json is not None:
            try:
                action_payload = _load_json(action_json)
            except Exception as exc:  # noqa: BLE001
                helper_warnings.append(f"action payload could not be parsed cleanly: {exc}")
                action_payload = {}
        else:
            action_payload = {}

    if scene_state_json is None:
        raise typer.BadParameter("Scene state path could not be resolved.")

    if scene_state_json.exists():
        try:
            scene_state = enrich_scene_state(_load_json(scene_state_json), repo_root)
        except Exception as exc:  # noqa: BLE001
            helper_warnings.append(f"scene state could not be parsed cleanly: {exc}")
            scene_state = enrich_scene_state({}, repo_root)
    else:
        helper_warnings.append(f"scene state file not found: {scene_state_json}")
        scene_state = enrich_scene_state({}, repo_root)

    if dirty_zone_json is not None:
        try:
            dirty_zone_payload = _load_json(dirty_zone_json)
        except Exception as exc:  # noqa: BLE001
            helper_warnings.append(f"dirty zone payload could not be parsed cleanly: {exc}")
            dirty_zone_payload = derive_dirty_zone(scene_state=scene_state, cycle_number=cycle_number)
    else:
        dirty_zone_payload = derive_dirty_zone(scene_state=scene_state, cycle_number=cycle_number)

    if not action_payload:
        helper_warnings.append("action payload could not be resolved; using no_op fallback action")
        action_payload = {"action": "no_op", "target_zone": dirty_zone_payload.get("zone_id", f"zone_{cycle_number:04d}")}

    report = run_validation(
        repo_root=repo_root,
        scene_state=scene_state,
        dirty_zone_payload=dirty_zone_payload,
        action_payload=action_payload,
    )
    deduped_warnings: list[str] = []
    seen: set[str] = set()
    for warning in helper_warnings:
        text = str(warning).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped_warnings.append(text)
    report["status"] = "ok"
    report["helper_warnings"] = deduped_warnings
    report["helper_warning_count"] = len(deduped_warnings)
    report["input_mode"] = "session" if session_id else "direct"
    typer.echo(json.dumps(report, indent=2))


def validator_tools() -> list[str]:
    return ["run"]


if __name__ == "__main__":
    app()
