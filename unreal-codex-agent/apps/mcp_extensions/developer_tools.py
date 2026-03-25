from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import typer

from apps.developer_overlay.scene_xray import (
    build_scene_xray_error_report,
    build_scene_xray_report,
    render_scene_xray_html,
    write_scene_xray_artifacts,
)
from apps.developer_overlay.settings import (
    load_project_config,
    merge_developer_tools_config,
    save_project_config,
    scene_xray_enabled,
    scene_xray_settings,
)
from apps.mcp_extensions.scene_tools import enrich_scene_state

app = typer.Typer(help="Developer scan and x-ray helper tools.")


@app.callback()
def _app_callback() -> None:
    """Require explicit subcommands for developer helper tooling."""


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def _project_with_defaults(repo_root: Path) -> dict[str, Any]:
    project = load_project_config(repo_root)
    project["developer_tools"] = merge_developer_tools_config(project)
    return project


def _save_developer_tools(repo_root: Path, developer_tools: dict[str, Any]) -> dict[str, Any]:
    project = load_project_config(repo_root)
    project["developer_tools"] = developer_tools
    save_project_config(repo_root, project)
    return project


def _parse_bool_text(value: str, label: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise typer.BadParameter(f"{label} must be one of: true/false, yes/no, on/off, 1/0.")


@app.command("status")
def status_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    project = _project_with_defaults(repo_root)
    typer.echo(json.dumps(project.get("developer_tools", {}), indent=2))


@app.command("enable")
def enable_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    developer_tools = merge_developer_tools_config(load_project_config(repo_root))
    developer_tools["enabled"] = True
    project = _save_developer_tools(repo_root, developer_tools)
    typer.echo(json.dumps({"status": "ok", "developer_tools": project["developer_tools"]}, indent=2))


@app.command("disable")
def disable_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    developer_tools = merge_developer_tools_config(load_project_config(repo_root))
    developer_tools["enabled"] = False
    project = _save_developer_tools(repo_root, developer_tools)
    typer.echo(json.dumps({"status": "ok", "developer_tools": project["developer_tools"]}, indent=2))


@app.command("toggle-scene-xray")
def toggle_scene_xray_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    developer_tools = merge_developer_tools_config(load_project_config(repo_root))
    scene_xray = dict(developer_tools.get("scene_xray") or {})
    scene_xray["enabled"] = not bool(scene_xray.get("enabled", True))
    developer_tools["scene_xray"] = scene_xray
    project = _save_developer_tools(repo_root, developer_tools)
    typer.echo(json.dumps({"status": "ok", "scene_xray": project["developer_tools"]["scene_xray"]}, indent=2))


@app.command("toggle-scene-xray-auto")
def toggle_scene_xray_auto_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    developer_tools = merge_developer_tools_config(load_project_config(repo_root))
    scene_xray = dict(developer_tools.get("scene_xray") or {})
    scene_xray["auto_generate_per_cycle"] = not bool(scene_xray.get("auto_generate_per_cycle", True))
    developer_tools["scene_xray"] = scene_xray
    project = _save_developer_tools(repo_root, developer_tools)
    typer.echo(json.dumps({"status": "ok", "scene_xray": project["developer_tools"]["scene_xray"]}, indent=2))


@app.command("toggle-scene-xray-tool-list")
def toggle_scene_xray_tool_list_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    developer_tools = merge_developer_tools_config(load_project_config(repo_root))
    scene_xray = dict(developer_tools.get("scene_xray") or {})
    scene_xray["default_show_tool_list"] = not bool(scene_xray.get("default_show_tool_list", True))
    developer_tools["scene_xray"] = scene_xray
    project = _save_developer_tools(repo_root, developer_tools)
    typer.echo(json.dumps({"status": "ok", "scene_xray": project["developer_tools"]["scene_xray"]}, indent=2))


@app.command("set-defaults")
def set_defaults_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    xray_on: str = typer.Option("true", help="Default x-ray glow state."),
    show_identified: str = typer.Option("true", help="Default identified visibility."),
    show_undefined: str = typer.Option("true", help="Default undefined visibility."),
    show_labels: str = typer.Option("true", help="Default label visibility."),
    show_tool_list: str = typer.Option("true", help="Default tool list visibility."),
) -> None:
    developer_tools = merge_developer_tools_config(load_project_config(repo_root))
    scene_xray = dict(developer_tools.get("scene_xray") or {})
    scene_xray["default_xray_on"] = _parse_bool_text(xray_on, "xray_on")
    scene_xray["default_show_identified"] = _parse_bool_text(show_identified, "show_identified")
    scene_xray["default_show_undefined"] = _parse_bool_text(show_undefined, "show_undefined")
    scene_xray["default_show_labels"] = _parse_bool_text(show_labels, "show_labels")
    scene_xray["default_show_tool_list"] = _parse_bool_text(show_tool_list, "show_tool_list")
    developer_tools["scene_xray"] = scene_xray
    project = _save_developer_tools(repo_root, developer_tools)
    typer.echo(json.dumps({"status": "ok", "scene_xray": project["developer_tools"]["scene_xray"]}, indent=2))


@app.command("scene-xray")
def scene_xray_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    scene_state_json: Path | None = typer.Option(None, help="Path to a saved scene-state JSON file."),
    session_id: str | None = typer.Option(None, help="Session id used to derive saved scene state."),
    cycle_number: int = typer.Option(1, help="Cycle number for session-derived scans."),
    output_dir: Path | None = typer.Option(None, help="Optional explicit output directory."),
    force: bool = typer.Option(False, help="Generate the report even if scene xray is disabled in project config."),
) -> None:
    if scene_state_json is None and session_id is None:
        raise typer.BadParameter("Provide --scene-state-json or --session-id.")
    project = _project_with_defaults(repo_root)
    if not force and not scene_xray_enabled(project):
        raise typer.BadParameter("Scene xray is disabled. Use developer_tools enable/toggle commands or pass --force.")

    session_path: Path | None = None
    warnings: list[str] = []
    if session_id:
        session_path = repo_root / "data" / "sessions" / session_id
        if not session_path.exists():
            raise typer.BadParameter(f"Unknown session_id: {session_id}")
        if scene_state_json is None:
            scene_state_json = session_path / "scene_state" / f"cycle_{cycle_number:04d}.json"
    if scene_state_json is None or not scene_state_json.exists():
        warnings.append(f"Scene state file could not be resolved: {scene_state_json}")
        scene_state = enrich_scene_state({}, repo_root)
    else:
        try:
            scene_state = enrich_scene_state(_load_json(scene_state_json), repo_root)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Scene state could not be parsed cleanly: {exc}")
            scene_state = enrich_scene_state({}, repo_root)

    try:
        report = build_scene_xray_report(
            repo_root=repo_root,
            scene_state=scene_state,
            viewer_settings=scene_xray_settings(project),
            session_id=session_id,
            cycle_number=cycle_number,
            zone_id=f"zone_{cycle_number:04d}",
            warnings=warnings,
        )
    except Exception as exc:  # noqa: BLE001
        report = build_scene_xray_error_report(
            repo_root=repo_root,
            error_message=str(exc),
            viewer_settings=scene_xray_settings(project),
            session_id=session_id,
            cycle_number=cycle_number,
            zone_id=f"zone_{cycle_number:04d}",
        )

    if output_dir is None:
        if session_path is not None:
            artifacts = write_scene_xray_artifacts(
                session_path=session_path,
                cycle_number=cycle_number,
                report=report,
            )
        else:
            temp_session = repo_root / "data" / "cache" / "developer_xray_temp"
            artifacts = write_scene_xray_artifacts(
                session_path=temp_session,
                cycle_number=cycle_number,
                report=report,
            )
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"cycle_{cycle_number:04d}.json"
        html_path = output_dir / f"cycle_{cycle_number:04d}.html"
        report_json = json.dumps(report, indent=2)

        def _write_atomic(path: Path, payload: str) -> None:
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

        _write_atomic(json_path, report_json)
        _write_atomic(html_path, render_scene_xray_html(report))
        artifacts = {"json_path": str(json_path), "html_path": str(html_path)}

    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "summary": report["summary"],
                "warnings": report.get("warnings", []),
                "artifacts": artifacts,
            },
            indent=2,
        )
    )


def developer_tools() -> list[str]:
    return [
        "status",
        "enable",
        "disable",
        "toggle-scene-xray",
        "toggle-scene-xray-auto",
        "toggle-scene-xray-tool-list",
        "set-defaults",
        "scene-xray",
    ]


if __name__ == "__main__":
    app()
