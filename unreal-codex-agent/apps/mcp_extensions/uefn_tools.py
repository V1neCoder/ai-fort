from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import typer

from apps.integrations.uefn_backend import backend_summary, uefn_content_root, verse_generated_root
from apps.integrations.uefn_mcp import (
    _delete_actors_by_paths,
    apply_action_via_mcp,
    collect_scene_state,
    deploy_listener_files,
    find_actors_by_label,
    inspect_actor,
    mcp_content_python_root,
    mcp_status_summary,
    set_actor_material,
    write_client_config,
)
from apps.integrations.uefn_toolbelt import (
    deploy_toolbelt_files,
    toolbelt_content_python_root,
    toolbelt_launch,
    toolbelt_list_live_tools,
    toolbelt_list_source_tools,
    toolbelt_nuclear_reload,
    toolbelt_run_tool,
    toolbelt_status_summary,
)
from apps.mcp_extensions.scene_tools import enrich_scene_state
from apps.orchestrator.dirty_zone import DirtyZoneDetector
from apps.placement.managed_registry import (
    detect_duplicate_claims,
    get_slot_record,
    managed_records_for_zone,
    registry_layout_snapshot,
    release_slot,
    zone_registry_snapshot,
)
from apps.placement.assembly_builder import BoxRoomSpec, HouseSpec, build_box_room_actions, build_house_actions, build_house_structure_plan
from apps.placement.assembly_builder import plan_box_room_spec, plan_house_spec
from apps.placement.interference import detect_actor_conflicts, infer_support_contact
from apps.placement.structure_validation import validate_structure_plan
from apps.placement.support_fit import derive_support_surface_fit
from apps.uefn.verse_export import apply_action_via_verse_export, export_cycle_artifacts

app = typer.Typer(help="UEFN and Verse helper tools for local workflow scaffolding.")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def _write_atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _parse_json_object(raw_value: str, *, field_name: str) -> dict[str, Any]:
    text = raw_value.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{field_name} must decode to a JSON object.")
    return payload


def _echo_json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _toolbelt_live_call(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except ConnectionError as exc:
        _echo_json({"status": "error", "error": str(exc)})
        raise typer.Exit(code=1) from exc


def _extract_verse_class_name(payload: str) -> str | None:
    match = re.search(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=\s*class\(creative_device\)", payload, flags=re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=\s*class\(", payload, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1)


def _find_existing_verse_file_for_class(destination_root: Path, class_name: str) -> Path | None:
    for path in destination_root.rglob("*.verse"):
        try:
            contents = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        if re.search(rf"^\s*{re.escape(class_name)}\s*:=\s*class\(", contents, flags=re.MULTILINE):
            return path
    return None


def _sync_generated_verse_files(source_root: Path, destination_root: Path, *, dry_run: bool) -> list[dict[str, Any]]:
    synced: list[dict[str, Any]] = []
    for source_path in sorted(source_root.glob("*.verse")):
        payload = source_path.read_text(encoding="utf-8-sig")
        class_name = _extract_verse_class_name(payload)
        if not class_name:
            synced.append(
                {
                    "source": source_path.as_posix(),
                    "status": "skipped",
                    "reason": "No Verse class declaration found.",
                }
            )
            continue
        existing = _find_existing_verse_file_for_class(destination_root, class_name)
        destination_path = existing or (destination_root / f"{class_name}.verse")
        if not dry_run:
            _write_atomic_text(destination_path, payload)
        synced.append(
            {
                "source": source_path.as_posix(),
                "destination": destination_path.as_posix(),
                "class_name": class_name,
                "status": "synced" if not dry_run else "planned",
                "reused_existing_file": existing is not None,
            }
        )
    return synced


def _load_action_from_history(session_path: Path, cycle_number: int) -> dict[str, Any]:
    action_history_path = session_path / "action_history.jsonl"
    if not action_history_path.exists():
        return {}
    last_match: dict[str, Any] | None = None
    for raw_line in action_history_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(payload.get("cycle_number", -1)) == cycle_number:
            last_match = payload
    if last_match is None:
        return {}
    return dict(last_match.get("action") or {})


def _load_session_json(session_path: Path) -> dict[str, Any]:
    session_file = session_path / "session.json"
    if not session_file.exists():
        return {}
    try:
        return _load_json(session_file)
    except Exception:
        return {}


def _load_latest_action_for_zone(session_path: Path, zone_id: str) -> dict[str, Any]:
    action_history_path = session_path / "action_history.jsonl"
    if not action_history_path.exists():
        return {}
    last_match: dict[str, Any] | None = None
    for raw_line in action_history_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(payload.get("zone_id") or "").strip() == str(zone_id or "").strip():
            last_match = payload
    if last_match is None:
        return {}
    return dict(last_match.get("action") or {})


def _latest_cycle_number(session_path: Path, explicit_cycle: int = 0) -> int:
    if explicit_cycle > 0:
        return explicit_cycle
    session_payload = _load_session_json(session_path)
    return int(session_payload.get("last_cycle_number") or 0)


def _managed_action_from_record(
    *,
    zone_id: str,
    record: dict[str, Any],
    latest_action: dict[str, Any] | None = None,
    placement_phase: str = "reanchor",
) -> dict[str, Any]:
    latest_action = dict(latest_action or {})
    latest_hint = dict(latest_action.get("placement_hint") or {})
    last_transform = dict(record.get("last_confirmed_transform") or {})
    support_reference = dict(record.get("support_reference") or {})
    placement_hint = {
        **support_reference,
        "placement_phase": placement_phase,
        "snap_policy": "force" if placement_phase == "reanchor" else "none",
        "support_reference_policy": "selected_first",
        "support_surface_kind": support_reference.get("support_surface_kind") or latest_hint.get("support_surface_kind"),
        "support_level": support_reference.get("support_level") or latest_hint.get("support_level"),
        "parent_support_actor": support_reference.get("parent_support_actor") or latest_hint.get("parent_support_actor"),
    }
    action_name = str(record.get("action_name") or latest_action.get("action") or "").strip().lower()
    if action_name != "place_asset":
        action_name = "set_transform"
    return {
        "action": action_name,
        "target_zone": zone_id,
        "managed_slot": str(record.get("managed_slot") or latest_action.get("managed_slot") or "primary"),
        "identity_policy": "reuse_only",
        "asset_path": str(record.get("asset_path") or latest_action.get("asset_path") or ""),
        "actor_path": str(record.get("actor_path") or latest_action.get("actor_path") or ""),
        "spawn_label": str(record.get("actor_label") or latest_action.get("spawn_label") or ""),
        "transform": {
            "location": list(last_transform.get("location") or [0.0, 0.0, 0.0]),
            "rotation": list(last_transform.get("rotation") or [0.0, 0.0, 0.0]),
            "scale": list(last_transform.get("scale") or [1.0, 1.0, 1.0]),
        },
        "placement_hint": placement_hint,
    }


def _stray_tool_generated_paths_for_zone(
    repo_root: Path,
    zone_records: list[dict[str, Any]],
) -> list[str]:
    claimed_paths = {
        str(record.get("actor_path") or "").strip()
        for record in zone_records
        if str(record.get("actor_path") or "").strip()
    }
    stray_paths: list[str] = []
    seen: set[str] = set()
    for record in zone_records:
        actor_label = str(record.get("actor_label") or "").strip()
        if not actor_label:
            continue
        live_matches = find_actors_by_label(repo_root, actor_label)
        preferred_path = str(record.get("actor_path") or "").strip()
        ordered_matches = sorted(
            (dict(actor) for actor in live_matches),
            key=lambda actor: (
                0 if str(actor.get("actor_path") or "").strip() == preferred_path else 1,
                str(actor.get("actor_path") or "").strip().lower(),
            ),
        )
        for actor in ordered_matches:
            actor_path = str(actor.get("actor_path") or "").strip()
            actor_label_live = str(actor.get("label") or "").strip()
            if not actor_path or actor_path == preferred_path or actor_path in claimed_paths or actor_path in seen:
                continue
            if not actor_label_live.startswith("UCA_"):
                continue
            seen.add(actor_path)
            stray_paths.append(actor_path)
    return stray_paths


def _write_scaffold_readme(repo_root: Path) -> Path:
    verse_root = verse_generated_root(repo_root).parent
    readme_path = verse_root / "README.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(
        "\n".join(
            [
                "# UEFN Verse Scaffold",
                "",
                "This folder is the repo-side handoff point for UEFN-first workflows.",
                "",
                "Generated files under `generated/` are rewritten by the local orchestrator.",
                "Review them in UEFN, wire them to Fortnite devices or Scene Graph entities,",
                "and replace placeholder logic with project-specific Verse behavior.",
                "",
                "Expected flow:",
                "",
                "1. Run the local orchestrator.",
                "2. Inspect `data/sessions/<session_id>/uefn_bridge/` for cycle manifests and intents.",
                "3. Run `python -m apps.mcp_extensions.uefn_tools sync-verse --repo-root .` to copy generated Verse into the island Content folder.",
                "4. Compile Verse in UEFN and bind the devices to your island setup.",
                "5. Enable Verse Debug Draw during playtest if you want to see live placement markers.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return readme_path


@app.command("status")
def status_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    _echo_json(backend_summary(repo_root))


@app.command("scaffold-verse")
def scaffold_verse_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    readme_path = _write_scaffold_readme(repo_root)
    generated_root = verse_generated_root(repo_root)
    generated_root.mkdir(parents=True, exist_ok=True)
    _echo_json(
        {
            "status": "ok",
            "platform": "uefn",
            "verse_root": generated_root.parent.as_posix(),
            "generated_root": generated_root.as_posix(),
            "readme_path": readme_path.as_posix(),
        }
    )


@app.command("sync-verse")
def sync_verse_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    destination: Path | None = typer.Option(None, help="Optional destination root for Verse files."),
    dry_run: bool = typer.Option(False, help="Preview the sync without writing files."),
) -> None:
    generated_root = verse_generated_root(repo_root)
    if not generated_root.exists():
        raise typer.BadParameter(f"Generated Verse root does not exist: {generated_root}")
    destination_root = destination or uefn_content_root(repo_root)
    if destination_root is None:
        raise typer.BadParameter("Could not determine the UEFN Content root. Set UEFN_PROJECT_PATH first.")
    destination_root.mkdir(parents=True, exist_ok=True)
    synced = _sync_generated_verse_files(generated_root, destination_root, dry_run=dry_run)
    _echo_json(
        {
            "status": "ok",
            "platform": "uefn",
            "generated_root": generated_root.as_posix(),
            "destination_root": destination_root.as_posix(),
            "dry_run": dry_run,
            "files": synced,
        }
    )


@app.command("mcp-status")
def mcp_status_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    _echo_json(mcp_status_summary(repo_root))


@app.command("sync-mcp-listener")
def sync_mcp_listener_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    destination: Path | None = typer.Option(None, help="Optional destination root for Content/Python."),
) -> None:
    target_root = destination or mcp_content_python_root(repo_root)
    if target_root is None:
        raise typer.BadParameter("Could not determine the UEFN Content/Python root. Set UEFN_PROJECT_PATH first.")
    result = deploy_listener_files(repo_root, destination_root=target_root)
    _echo_json({"status": "ok", "platform": "uefn", **result})


@app.command("sync-stack")
def sync_stack_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    destination: Path | None = typer.Option(None, help="Optional destination root for Content/Python."),
    scaffold_verse: bool = typer.Option(True, help="Ensure the repo-side Verse scaffold exists."),
    write_mcp_config: bool = typer.Option(False, help="Also rewrite the local .mcp.json client config."),
    reload_live: bool = typer.Option(True, help="Run a Toolbelt nuclear reload in the live editor after syncing."),
) -> None:
    target_root = destination or mcp_content_python_root(repo_root)
    if target_root is None:
        raise typer.BadParameter("Could not determine the UEFN Content/Python root. Set UEFN_PROJECT_PATH first.")

    listener_result = deploy_listener_files(repo_root, destination_root=target_root)
    toolbelt_result = deploy_toolbelt_files(repo_root, destination_root=target_root)

    scaffold_result: dict[str, Any] | None = None
    if scaffold_verse:
        readme_path = _write_scaffold_readme(repo_root)
        generated_root = verse_generated_root(repo_root)
        generated_root.mkdir(parents=True, exist_ok=True)
        scaffold_result = {
            "status": "ok",
            "verse_root": generated_root.parent.as_posix(),
            "generated_root": generated_root.as_posix(),
            "readme_path": readme_path.as_posix(),
        }

    config_result: dict[str, Any] | None = None
    if write_mcp_config:
        config_path = write_client_config(repo_root)
        config_result = {
            "status": "ok",
            "client_config_path": config_path.as_posix(),
        }

    live_reload: dict[str, Any]
    actual_root = mcp_content_python_root(repo_root)
    if not reload_live:
        live_reload = {
            "status": "skipped",
            "reason": "reload_live was disabled.",
        }
    elif actual_root is None or actual_root.resolve() != target_root.resolve():
        live_reload = {
            "status": "skipped",
            "reason": "Live reload only runs when syncing directly into the configured UEFN Content/Python root.",
        }
    else:
        try:
            live_reload = toolbelt_nuclear_reload(repo_root)
        except ConnectionError as exc:
            live_reload = {
                "status": "error",
                "error": str(exc),
            }

    _echo_json(
        {
            "status": "ok",
            "platform": "uefn",
            "destination_root": target_root.as_posix(),
            "listener": listener_result,
            "toolbelt": toolbelt_result,
            "scaffold_verse": scaffold_result,
            "mcp_config": config_result,
            "live_reload": live_reload,
        }
    )


@app.command("sync-toolbelt")
def sync_toolbelt_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    destination: Path | None = typer.Option(None, help="Optional destination root for Content/Python."),
    reload_live: bool = typer.Option(False, help="Run a Toolbelt nuclear reload in the live editor after syncing."),
) -> None:
    target_root = destination or toolbelt_content_python_root(repo_root)
    if target_root is None:
        raise typer.BadParameter("Could not determine the UEFN Content/Python root. Set UEFN_PROJECT_PATH first.")
    result = deploy_toolbelt_files(repo_root, destination_root=target_root)
    actual_root = toolbelt_content_python_root(repo_root)
    live_reload: dict[str, Any] | None = None
    if reload_live:
        if actual_root is None or actual_root.resolve() != target_root.resolve():
            live_reload = {
                "status": "skipped",
                "reason": "Live reload only runs when syncing directly into the configured UEFN Content/Python root.",
            }
        else:
            try:
                live_reload = toolbelt_nuclear_reload(repo_root)
            except ConnectionError as exc:
                live_reload = {
                    "status": "error",
                    "error": str(exc),
                }
    _echo_json({"status": "ok", "platform": "uefn", **result, "live_reload": live_reload})


@app.command("toolbelt-status")
def toolbelt_status_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    _echo_json(toolbelt_status_summary(repo_root))


@app.command("toolbelt-source-tools")
def toolbelt_source_tools_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    category: str = typer.Option("", help="Optional exact category filter."),
    query: str = typer.Option("", help="Optional case-insensitive search across names, descriptions, and file paths."),
    limit: int = typer.Option(0, help="Optional max number of tools to return. 0 means no limit."),
) -> None:
    result = toolbelt_list_source_tools(repo_root, category=category, query=query)
    if limit > 0:
        result["tools"] = list(result.get("tools") or [])[:limit]
        result["tool_count"] = len(result["tools"])
    _echo_json(result)


@app.command("toolbelt-live-tools")
def toolbelt_live_tools_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    category: str = typer.Option("", help="Optional exact category filter."),
    query: str = typer.Option("", help="Optional case-insensitive search across names, descriptions, and tags."),
    limit: int = typer.Option(0, help="Optional max number of tools to return. 0 means no limit."),
    reload_live: bool = typer.Option(False, help="Perform a Toolbelt nuclear reload before listing tools."),
) -> None:
    result = _toolbelt_live_call(
        toolbelt_list_live_tools,
        repo_root,
        category=category,
        query=query,
        reload_modules=reload_live,
    )
    if limit > 0:
        result["tools"] = list(result.get("tools") or [])[:limit]
        result["tool_count"] = len(result["tools"])
    _echo_json(result)


@app.command("toolbelt-reload")
def toolbelt_reload_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    _echo_json(_toolbelt_live_call(toolbelt_nuclear_reload, repo_root))


@app.command("toolbelt-launch")
def toolbelt_launch_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    mode: str = typer.Option("qt", help="Launch mode: qt or fallback."),
    reload_live: bool = typer.Option(False, help="Perform a Toolbelt nuclear reload before launching."),
) -> None:
    _echo_json(_toolbelt_live_call(toolbelt_launch, repo_root, mode=mode, reload_modules=reload_live))


@app.command("toolbelt-run")
def toolbelt_run_command(
    tool_name: str = typer.Argument(..., help="Registered Toolbelt tool name."),
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    kwargs_json: str = typer.Option("{}", help="JSON object passed as keyword args to the Toolbelt tool."),
    reload_live: bool = typer.Option(False, help="Perform a Toolbelt nuclear reload before running the tool."),
    timeout_seconds: float = typer.Option(30.0, help="Timeout for the live editor call."),
    allow_invasive: bool = typer.Option(False, help="Required when invoking toolbelt_integration_test through this generic runner."),
) -> None:
    if tool_name == "toolbelt_integration_test" and not allow_invasive:
        raise typer.BadParameter("toolbelt_integration_test is invasive. Re-run with --allow-invasive or use toolbelt-integration-test --confirm-invasive.")
    kwargs = _parse_json_object(kwargs_json, field_name="kwargs_json")
    _echo_json(
        _toolbelt_live_call(
            toolbelt_run_tool,
            repo_root,
            tool_name=tool_name,
            kwargs=kwargs,
            reload_modules=reload_live,
            timeout=timeout_seconds,
        )
    )


@app.command("toolbelt-smoke-test")
def toolbelt_smoke_test_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    reload_live: bool = typer.Option(False, help="Perform a Toolbelt nuclear reload before running the smoke test."),
    timeout_seconds: float = typer.Option(60.0, help="Timeout for the live editor call."),
) -> None:
    _echo_json(
        _toolbelt_live_call(
            toolbelt_run_tool,
            repo_root,
            tool_name="toolbelt_smoke_test",
            kwargs={},
            reload_modules=reload_live,
            timeout=timeout_seconds,
        )
    )


@app.command("toolbelt-integration-test")
def toolbelt_integration_test_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    confirm_invasive: bool = typer.Option(False, "--confirm-invasive", help="Required because the Toolbelt integration test spawns and deletes actors in the live level."),
    reload_live: bool = typer.Option(False, help="Perform a Toolbelt nuclear reload before running the integration test."),
    timeout_seconds: float = typer.Option(300.0, help="Timeout for the live editor call."),
) -> None:
    if not confirm_invasive:
        raise typer.BadParameter("toolbelt-integration-test is invasive. Re-run with --confirm-invasive in a blank test level.")
    _echo_json(
        _toolbelt_live_call(
            toolbelt_run_tool,
            repo_root,
            tool_name="toolbelt_integration_test",
            kwargs={},
            reload_modules=reload_live,
            timeout=timeout_seconds,
        )
    )


@app.command("write-mcp-config")
def write_mcp_config_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    output_path: Path | None = typer.Option(None, help="Optional output path for the .mcp.json file."),
) -> None:
    path = write_client_config(repo_root, output_path=output_path)
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "platform": "uefn",
                "client_config_path": path.as_posix(),
            },
            indent=2,
        )
    )


@app.command("export-cycle")
def export_cycle_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Session id containing saved scene/action state."),
    cycle_number: int = typer.Option(1, help="Cycle number to export."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    if not session_path.exists():
        raise typer.BadParameter(f"Unknown session id: {session_id}")
    scene_state_path = session_path / "scene_state" / f"cycle_{cycle_number:04d}.json"
    if not scene_state_path.exists():
        raise typer.BadParameter(f"Missing scene state for cycle {cycle_number}: {scene_state_path}")
    scene_state = enrich_scene_state(_load_json(scene_state_path), repo_root)
    dirty_zone = DirtyZoneDetector().detect(scene_state=scene_state, cycle_number=cycle_number).to_dict()
    action_payload = _load_action_from_history(session_path, cycle_number) or {
        "action": "no_op",
        "target_zone": dirty_zone.get("zone_id", f"zone_{cycle_number:04d}"),
    }
    report = export_cycle_artifacts(
        repo_root=repo_root,
        session_path=session_path,
        cycle_number=cycle_number,
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        action_payload=action_payload,
        placement_summary=dict(scene_state.get("placement_context") or {}),
    )
    typer.echo(json.dumps(report, indent=2))


@app.command("export-publish-safe")
def export_publish_safe_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Session id containing saved scene/action state."),
    cycle_number: int = typer.Option(0, help="Cycle number to export. Defaults to the latest cycle in the session."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    if not session_path.exists():
        raise typer.BadParameter(f"Unknown session id: {session_id}")
    cycle_number = _latest_cycle_number(session_path, cycle_number)
    if cycle_number <= 0:
        raise typer.BadParameter("No cycle number was available to export.")
    scene_state_path = session_path / "scene_state" / f"cycle_{cycle_number:04d}.json"
    if not scene_state_path.exists():
        raise typer.BadParameter(f"Missing scene state for cycle {cycle_number}: {scene_state_path}")
    scene_state = enrich_scene_state(_load_json(scene_state_path), repo_root)
    dirty_zone = DirtyZoneDetector().detect(scene_state=scene_state, cycle_number=cycle_number).to_dict()
    action_payload = _load_action_from_history(session_path, cycle_number)
    if not action_payload:
        raise typer.BadParameter(f"No saved action was found for cycle {cycle_number}.")
    result = apply_action_via_verse_export(
        repo_root=repo_root,
        session_path=session_path,
        cycle_number=cycle_number,
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        action_payload=action_payload,
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("apply-action")
def apply_action_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Session id containing the saved action."),
    cycle_number: int = typer.Option(0, help="Cycle number to apply. Defaults to the latest cycle in the session."),
    auto_save: bool = typer.Option(False, help="Save the current level after applying the action."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    if not session_path.exists():
        raise typer.BadParameter(f"Unknown session id: {session_id}")
    session_payload = _load_session_json(session_path)
    if cycle_number <= 0:
        cycle_number = int(session_payload.get("last_cycle_number") or 0)
    if cycle_number <= 0:
        raise typer.BadParameter("No cycle number was available to apply.")
    action_payload = _load_action_from_history(session_path, cycle_number)
    if not action_payload:
        raise typer.BadParameter(f"No saved action was found for cycle {cycle_number}.")
    result = apply_action_via_mcp(
        repo_root,
        action_payload,
        session_path=session_path,
        cycle_number=cycle_number,
        auto_save=auto_save,
    )
    typer.echo(
        json.dumps(
            {
                "status": "ok" if result.get("status") == "ok" else "warning",
                "platform": "uefn",
                "session_id": session_id,
                "cycle_number": cycle_number,
                "result": result,
            },
            indent=2,
        )
    )


@app.command("release-managed")
def release_managed_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Session id containing the managed registry."),
    zone: str = typer.Option(..., help="Zone id to release."),
    slot: str = typer.Option("primary", help="Managed slot to release."),
    reason: str = typer.Option("manual_release", help="Reason stored in the registry."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    if not session_path.exists():
        raise typer.BadParameter(f"Unknown session id: {session_id}")
    released = release_slot(session_path, zone_id=zone, managed_slot=slot, reason=reason)
    typer.echo(
        json.dumps(
            {
                "status": "ok" if released else "warning",
                "session_id": session_id,
                "zone_id": zone,
                "managed_slot": slot,
                "released_record": released or {},
            },
            indent=2,
        )
    )


@app.command("reconcile-managed")
def reconcile_managed_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Session id containing the managed registry."),
    zone: str = typer.Option(..., help="Zone id to reconcile."),
    slot: str = typer.Option("primary", help="Managed slot to reconcile."),
    placement_phase: str = typer.Option("reanchor", help="Placement phase to use for reconciliation."),
    auto_save: bool = typer.Option(False, help="Save the current level after applying the correction."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    if not session_path.exists():
        raise typer.BadParameter(f"Unknown session id: {session_id}")
    record = get_slot_record(session_path, zone, slot)
    if not record:
        raise typer.BadParameter(f"No managed record exists for {zone}:{slot}.")
    latest_action = _load_latest_action_for_zone(session_path, zone)
    action_payload = _managed_action_from_record(
        zone_id=zone,
        record=record,
        latest_action=latest_action,
        placement_phase=placement_phase,
    )
    result = apply_action_via_mcp(
        repo_root,
        action_payload,
        session_path=session_path,
        auto_save=auto_save,
    )
    typer.echo(
        json.dumps(
            {
                "status": "ok" if result.get("status") == "ok" else "warning",
                "session_id": session_id,
                "zone_id": zone,
                "managed_slot": slot,
                "action": action_payload,
                "result": result,
            },
            indent=2,
        )
    )


@app.command("cleanup-managed")
def cleanup_managed_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Session id containing the managed registry."),
    zone: str = typer.Option(..., help="Zone id to clean."),
    delete_released: bool = typer.Option(True, help="Delete released managed actors for the target zone."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    if not session_path.exists():
        raise typer.BadParameter(f"Unknown session id: {session_id}")
    zone_records = managed_records_for_zone(session_path, zone)
    duplicate_summary = detect_duplicate_claims(session_path)
    delete_paths: list[str] = []
    warnings: list[str] = []
    if delete_released:
        for record in zone_records:
            ownership = dict(record.get("ownership") or {})
            actor_path = str(record.get("actor_path") or "").strip()
            if not actor_path:
                continue
            if str(record.get("registry_status") or "").strip().lower() == "released" or bool(ownership.get("released", False)):
                if bool(ownership.get("allow_cleanup", True)):
                    delete_paths.append(actor_path)
    duplicate_actor_paths = [
        entry
        for entry in list(duplicate_summary.get("actor_paths") or [])
        if any(str(record.get("zone_id") or "") == zone for record in list(entry.get("records") or []))
    ]
    stray_tool_generated_paths = _stray_tool_generated_paths_for_zone(repo_root, zone_records)
    for actor_path in stray_tool_generated_paths:
        if actor_path not in delete_paths:
            delete_paths.append(actor_path)
    if duplicate_actor_paths:
        warnings.append("Detected duplicate claimed actor paths in the registry; cleanup only removed explicitly released records.")
    if stray_tool_generated_paths:
        warnings.append("Removed stray tool-generated actors that matched managed labels but were not claimed by the registry.")
    cleanup_result = _delete_actors_by_paths(repo_root, delete_paths) if delete_paths else None
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "zone_id": zone,
                "deleted_paths": delete_paths,
                "stray_tool_generated_paths": stray_tool_generated_paths,
                "cleanup_result": cleanup_result or {"requested_count": 0, "deleted_count": 0, "deleted_paths": []},
                "registry_zone": zone_registry_snapshot(session_path, zone),
                "duplicate_summary": {
                    "actor_paths": duplicate_actor_paths,
                    "actor_labels": [
                        entry
                        for entry in list(duplicate_summary.get("actor_labels") or [])
                        if any(str(record.get("zone_id") or "") == zone for record in list(entry.get("records") or []))
                    ],
                },
                "warnings": warnings,
            },
            indent=2,
        )
    )


@app.command("inspect-support")
def inspect_support_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    actor: str = typer.Option(..., help="Actor path or label to inspect."),
) -> None:
    scene_state = enrich_scene_state(collect_scene_state(repo_root), repo_root)
    actor_payload = inspect_actor(repo_root, actor)
    fit = derive_support_surface_fit(scene_state=scene_state, active_actor=actor_payload) if actor_payload else {}
    observed_support = infer_support_contact(
        actor_payload,
        [dict(item) for item in list(scene_state.get("actors") or []) if isinstance(item, dict)],
        ignore_actor_paths={str(actor_payload.get("actor_path") or "")},
    ) if actor_payload else {}
    typer.echo(
        json.dumps(
            {
                "status": "ok" if actor_payload else "warning",
                "actor": actor_payload,
                "support_fit": fit,
                "observed_support": observed_support,
                "placement_targets": scene_state.get("placement_targets", {}),
                "support_graph": scene_state.get("support_graph", {}),
            },
            indent=2,
        )
    )


@app.command("inspect-interference")
def inspect_interference_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    actor: str = typer.Option(..., help="Actor path or label to inspect."),
    mount_type: str = typer.Option("", help="Optional expected mount type used to detect incompatible support surfaces."),
) -> None:
    scene_state = enrich_scene_state(collect_scene_state(repo_root), repo_root)
    actor_payload = inspect_actor(repo_root, actor)
    support_reference = {
        "support_surface_kind": str(scene_state.get("placement_targets", {}).get("support_surface_kind") or ""),
        "support_actor_label": str(scene_state.get("placement_targets", {}).get("support_actor_label") or ""),
        "support_actor_path": str(scene_state.get("placement_targets", {}).get("support_actor_path") or ""),
        "parent_support_actor": str(scene_state.get("placement_targets", {}).get("parent_support_actor") or ""),
    }
    conflicts = detect_actor_conflicts(
        actor_payload,
        [dict(item) for item in list(scene_state.get("actors") or []) if isinstance(item, dict)],
        ignore_actor_paths={str(actor_payload.get("actor_path") or "")},
        support_reference=support_reference,
        mount_type=mount_type or str(scene_state.get("expected_mount_type") or ""),
    ) if actor_payload else {}
    typer.echo(
        json.dumps(
            {
                "status": "ok" if actor_payload else "warning",
                "actor": actor_payload,
                "support_reference": support_reference,
                "interference_report": conflicts,
            },
            indent=2,
        )
    )


@app.command("diff-layout")
def diff_layout_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Session id containing the managed registry."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    if not session_path.exists():
        raise typer.BadParameter(f"Unknown session id: {session_id}")
    scene_state = enrich_scene_state(collect_scene_state(repo_root), repo_root)
    diffs: list[dict[str, Any]] = []
    registry = registry_layout_snapshot(session_path)
    for zone_id, zone_payload in sorted(dict(registry.get("zones") or {}).items()):
        for managed_slot, record in sorted(dict(zone_payload.get("slots") or {}).items()):
            actor_path = str(record.get("actor_path") or "").strip()
            live_actor = inspect_actor(repo_root, actor_path) if actor_path else {}
            diffs.append(
                {
                    "zone_id": zone_id,
                    "managed_slot": managed_slot,
                    "actor_path": actor_path,
                    "actor_label": record.get("actor_label"),
                    "registry_status": record.get("registry_status"),
                    "live_actor_found": bool(live_actor),
                    "fit_status": dict(record.get("fit_status") or {}),
                    "live_support_fit": (
                        derive_support_surface_fit(
                            scene_state=scene_state,
                            active_actor=live_actor,
                            mount_type=str(dict(record.get("fit_status") or {}).get("mount_type") or ""),
                        )
                        if live_actor
                        else {}
                    ),
                    "live_location": list(live_actor.get("location") or []),
                    "live_rotation": list(live_actor.get("rotation") or []),
                    "live_scale": list(live_actor.get("scale") or []),
                    "same_label_live_actors": len(find_actors_by_label(repo_root, str(record.get("actor_label") or "")))
                    if str(record.get("actor_label") or "").strip()
                    else 0,
                }
            )
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "layout_diff": diffs,
            },
            indent=2,
        )
    )


@app.command("build-box-room")
def build_box_room_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    zone: str = typer.Option("zone_box_room", help="Zone id used for the managed wall assembly."),
    session_id: str = typer.Option("manual_structures", help="Session id used to track the managed assembly."),
    center_x: float = typer.Option(..., help="World X center of the room footprint."),
    center_y: float = typer.Option(..., help="World Y center of the room footprint."),
    support_z: float = typer.Option(0.0, help="Support surface Z height."),
    inner_width_cm: float = typer.Option(400.0, help="Clear inside width of the room."),
    inner_depth_cm: float = typer.Option(400.0, help="Clear inside depth of the room."),
    wall_height_cm: float = typer.Option(300.0, help="Wall height in centimeters."),
    wall_thickness_cm: float = typer.Option(20.0, help="Wall thickness in centimeters."),
    door_width_cm: float = typer.Option(140.0, help="Door opening width in centimeters."),
    door_height_cm: float = typer.Option(220.0, help="Door opening height in centimeters."),
    grid_snap_cm: float = typer.Option(10.0, help="Grid snap used for the wall layout."),
    support_actor: str = typer.Option("", help="Support actor label or path used for the room."),
    material_path: str = typer.Option("", help="Optional material applied to every wall segment."),
    label_prefix: str = typer.Option("UCA_BoxRoom", help="Prefix used for generated wall labels."),
    corner_join_style: str = typer.Option(
        "butt_join",
        help="Corner strategy: butt_join avoids overlapping wall volumes, overlap keeps the old behavior.",
    ),
    grid_safe_joints: bool = typer.Option(
        True,
        help="Adjust doorway and front wall spans to grid-safe sizes so snapped actor positions do not create overlap.",
    ),
    auto_save: bool = typer.Option(False, help="Save the current level after placing the room."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    session_path.mkdir(parents=True, exist_ok=True)
    requested_spec = BoxRoomSpec(
        zone_id=zone,
        center_x=center_x,
        center_y=center_y,
        support_z=support_z,
        inner_width_cm=inner_width_cm,
        inner_depth_cm=inner_depth_cm,
        wall_height_cm=wall_height_cm,
        wall_thickness_cm=wall_thickness_cm,
        door_width_cm=door_width_cm,
        door_height_cm=door_height_cm,
        grid_snap_cm=grid_snap_cm,
        label_prefix=label_prefix,
        support_actor_label=support_actor,
        parent_support_actor=support_actor,
        corner_join_style=corner_join_style,
        grid_safe_joints=grid_safe_joints,
    )
    scene_state = enrich_scene_state(collect_scene_state(repo_root), repo_root)
    zone_records = managed_records_for_zone(session_path, zone)
    ignore_actor_paths = {
        str(record.get("actor_path") or "").strip()
        for record in zone_records
        if str(record.get("actor_path") or "").strip()
    }
    ignore_actor_labels = {
        str(record.get("actor_label") or "").strip()
        for record in zone_records
        if str(record.get("actor_label") or "").strip()
    }
    if support_actor:
        support_actor_payload = inspect_actor(repo_root, support_actor)
        if support_actor_payload:
            support_actor_path = str(support_actor_payload.get("actor_path") or "").strip()
            if support_actor_path:
                ignore_actor_paths.add(support_actor_path)
            ignore_actor_labels.add(str(support_actor_payload.get("label") or support_actor).strip())
    plan = plan_box_room_spec(
        requested_spec,
        [dict(item) for item in list(scene_state.get("actors") or []) if isinstance(item, dict)],
        ignore_actor_paths=ignore_actor_paths,
        ignore_actor_labels=ignore_actor_labels,
    )
    spec = plan["spec"]
    actions = build_box_room_actions(spec)
    results: list[dict[str, Any]] = []
    material_results: list[dict[str, Any]] = []
    for action in actions:
        result = apply_action_via_mcp(
            repo_root,
            action,
            session_path=session_path,
            auto_save=False,
        )
        results.append(result)
        actor_path = str(dict(result.get("actor") or {}).get("actor_path") or "").strip()
        if actor_path and material_path:
            material_results.append(
                set_actor_material(
                    repo_root,
                    actor_identifier=actor_path,
                    material_path=material_path,
                )
            )
    if auto_save:
        try:
            apply_action_via_mcp(
                repo_root,
                {"action": "no_op"},
                session_path=session_path,
                auto_save=True,
            )
        except Exception:
            pass
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "zone_id": zone,
                "segment_count": len(actions),
                "placement_plan": {
                    "requested_center": [requested_spec.center_x, requested_spec.center_y],
                    "final_center": [spec.center_x, spec.center_y],
                    "relocated": bool(plan.get("relocated", False)),
                    "offset_cm": list(plan.get("offset_cm") or [0.0, 0.0]),
                    "conflict_count": int(plan.get("conflict_count") or 0),
                    "blocking_conflicts": list(plan.get("blocking_conflicts") or []),
                },
                "results": results,
                "material_results": material_results,
            },
            indent=2,
        )
    )


@app.command("build-house")
def build_house_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    zone: str = typer.Option("zone_house", help="Zone id used for the managed house assembly."),
    session_id: str = typer.Option("manual_structures", help="Session id used to track the managed assembly."),
    center_x: float = typer.Option(..., help="World X center of the house footprint."),
    center_y: float = typer.Option(..., help="World Y center of the house footprint."),
    support_z: float = typer.Option(0.0, help="Support surface Z height."),
    inner_width_cm: float = typer.Option(700.0, help="Clear inside width of the house."),
    inner_depth_cm: float = typer.Option(600.0, help="Clear inside depth of the house."),
    story_height_cm: float = typer.Option(300.0, help="Story height in centimeters."),
    wall_thickness_cm: float = typer.Option(20.0, help="Wall thickness in centimeters."),
    floor_thickness_cm: float = typer.Option(20.0, help="Floor slab thickness in centimeters."),
    door_width_cm: float = typer.Option(160.0, help="Front door width in centimeters."),
    door_height_cm: float = typer.Option(230.0, help="Front door height in centimeters."),
    roof_pitch_deg: float = typer.Option(30.0, help="Roof pitch angle in degrees."),
    roof_thickness_cm: float = typer.Option(18.0, help="Roof panel thickness in centimeters."),
    roof_overhang_cm: float = typer.Option(25.0, help="Roof overhang on each side in centimeters."),
    roof_rise_cm: float = typer.Option(120.0, help="Rise from second-story wall top to roof ridge."),
    stair_width_cm: float = typer.Option(140.0, help="Interior stair width in centimeters."),
    stair_step_rise_cm: float = typer.Option(20.0, help="Rise of each stair step."),
    stair_step_run_cm: float = typer.Option(30.0, help="Run of each stair step."),
    stair_step_count: int = typer.Option(10, help="Number of stair steps."),
    grid_snap_cm: float = typer.Option(10.0, help="Grid snap used for the house layout."),
    support_actor: str = typer.Option("", help="Support actor label or path used for the house."),
    material_path: str = typer.Option("", help="Optional material applied to every generated segment."),
    label_prefix: str = typer.Option("UCA_House", help="Prefix used for generated house labels."),
    auto_save: bool = typer.Option(False, help="Save the current level after placing the house."),
) -> None:
    session_path = repo_root / "data" / "sessions" / session_id
    session_path.mkdir(parents=True, exist_ok=True)
    requested_spec = HouseSpec(
        zone_id=zone,
        center_x=center_x,
        center_y=center_y,
        support_z=support_z,
        inner_width_cm=inner_width_cm,
        inner_depth_cm=inner_depth_cm,
        story_height_cm=story_height_cm,
        wall_thickness_cm=wall_thickness_cm,
        floor_thickness_cm=floor_thickness_cm,
        door_width_cm=door_width_cm,
        door_height_cm=door_height_cm,
        roof_pitch_deg=roof_pitch_deg,
        roof_thickness_cm=roof_thickness_cm,
        roof_overhang_cm=roof_overhang_cm,
        roof_rise_cm=roof_rise_cm,
        stair_width_cm=stair_width_cm,
        stair_step_rise_cm=stair_step_rise_cm,
        stair_step_run_cm=stair_step_run_cm,
        stair_step_count=stair_step_count,
        grid_snap_cm=grid_snap_cm,
        label_prefix=label_prefix,
        support_actor_label=support_actor,
        parent_support_actor=support_actor,
    )
    scene_state = enrich_scene_state(collect_scene_state(repo_root), repo_root)
    zone_records = managed_records_for_zone(session_path, zone)
    ignore_actor_paths = {
        str(record.get("actor_path") or "").strip()
        for record in zone_records
        if str(record.get("actor_path") or "").strip()
    }
    ignore_actor_labels = {
        str(record.get("actor_label") or "").strip()
        for record in zone_records
        if str(record.get("actor_label") or "").strip()
    }
    if support_actor:
        support_actor_payload = inspect_actor(repo_root, support_actor)
        if support_actor_payload:
            support_actor_path = str(support_actor_payload.get("actor_path") or "").strip()
            if support_actor_path:
                ignore_actor_paths.add(support_actor_path)
            ignore_actor_labels.add(str(support_actor_payload.get("label") or support_actor).strip())
    plan = plan_house_spec(
        requested_spec,
        [dict(item) for item in list(scene_state.get("actors") or []) if isinstance(item, dict)],
        ignore_actor_paths=ignore_actor_paths,
        ignore_actor_labels=ignore_actor_labels,
    )
    spec = plan["spec"]
    structure_plan = build_house_structure_plan(spec)
    actions = build_house_actions(spec)
    desired_slots = {
        str(action.get("managed_slot") or "").strip()
        for action in actions
        if str(action.get("managed_slot") or "").strip()
    }
    cleanup_paths: list[str] = []
    released_slots: list[str] = []
    for record in zone_records:
        managed_slot = str(record.get("managed_slot") or "").strip()
        actor_path = str(record.get("actor_path") or "").strip()
        ownership = dict(record.get("ownership") or {})
        if not managed_slot or managed_slot in desired_slots:
            continue
        released = release_slot(
            session_path,
            zone_id=zone,
            managed_slot=managed_slot,
            reason="obsolete_structure_slot",
        )
        if released:
            released_slots.append(managed_slot)
        if actor_path and bool(ownership.get("allow_cleanup", True)):
            cleanup_paths.append(actor_path)
    cleanup_paths.extend(_stray_tool_generated_paths_for_zone(repo_root, zone_records))
    cleanup_result = (
        _delete_actors_by_paths(repo_root, sorted({path for path in cleanup_paths if str(path).strip()}))
        if cleanup_paths
        else {"success": True, "deleted_count": 0, "deleted_paths": []}
    )
    results: list[dict[str, Any]] = []
    material_results: list[dict[str, Any]] = []
    live_actors_by_slot: dict[str, dict[str, Any]] = {}
    for action in actions:
        result = apply_action_via_mcp(
            repo_root,
            action,
            session_path=session_path,
            auto_save=False,
        )
        results.append(result)
        actor_payload = dict(result.get("actor") or {})
        actor_path = str(actor_payload.get("actor_path") or "").strip()
        managed_slot = str(action.get("managed_slot") or "").strip()
        if managed_slot and actor_payload:
            actor_payload["managed_slot"] = managed_slot
            live_actors_by_slot[managed_slot] = actor_payload
        if actor_path and material_path:
            material_results.append(
                set_actor_material(
                    repo_root,
                    actor_identifier=actor_path,
                    material_path=material_path,
                )
            )
    structure_validation = validate_structure_plan(structure_plan, live_actors_by_slot=live_actors_by_slot)
    structure_plan_payload = dict(structure_plan)
    structure_spec = structure_plan_payload.get("spec")
    if hasattr(structure_spec, "__dict__"):
        structure_plan_payload["spec"] = dict(structure_spec.__dict__)
    structure_plan_path = session_path / "structure_plans" / f"{zone}.json"
    _write_atomic_text(
        structure_plan_path,
        json.dumps(
            {
                "structure_plan": structure_plan_payload,
                "structure_validation": structure_validation,
                "placement_plan": {
                    "requested_center": [requested_spec.center_x, requested_spec.center_y],
                    "final_center": [spec.center_x, spec.center_y],
                    "relocated": bool(plan.get("relocated", False)),
                    "offset_cm": list(plan.get("offset_cm") or [0.0, 0.0]),
                    "conflict_count": int(plan.get("conflict_count") or 0),
                    "blocking_conflicts": list(plan.get("blocking_conflicts") or []),
                },
            },
            indent=2,
        ),
    )
    if auto_save:
        try:
            apply_action_via_mcp(
                repo_root,
                {"action": "no_op"},
                session_path=session_path,
                auto_save=True,
            )
        except Exception:
            pass
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "zone_id": zone,
                "segment_count": len(actions),
                "structure_plan_path": structure_plan_path.as_posix(),
                "placement_plan": {
                    "requested_center": [requested_spec.center_x, requested_spec.center_y],
                    "final_center": [spec.center_x, spec.center_y],
                    "relocated": bool(plan.get("relocated", False)),
                    "offset_cm": list(plan.get("offset_cm") or [0.0, 0.0]),
                    "conflict_count": int(plan.get("conflict_count") or 0),
                    "blocking_conflicts": list(plan.get("blocking_conflicts") or []),
                },
                "cleanup": {
                    "released_slots": released_slots,
                    "cleanup_result": cleanup_result,
                },
                "structure_validation": structure_validation,
                "results": results,
                "material_results": material_results,
            },
            indent=2,
        )
    )


def uefn_tools() -> list[str]:
    return [
        "status",
        "scaffold-verse",
        "sync-verse",
        "mcp-status",
        "sync-mcp-listener",
        "sync-stack",
        "sync-toolbelt",
        "toolbelt-status",
        "toolbelt-source-tools",
        "toolbelt-live-tools",
        "toolbelt-reload",
        "toolbelt-launch",
        "toolbelt-run",
        "toolbelt-smoke-test",
        "toolbelt-integration-test",
        "write-mcp-config",
        "export-cycle",
        "export-publish-safe",
        "apply-action",
        "release-managed",
        "reconcile-managed",
        "cleanup-managed",
        "inspect-support",
        "inspect-interference",
        "diff-layout",
        "build-box-room",
        "build-house",
    ]


if __name__ == "__main__":
    app()
