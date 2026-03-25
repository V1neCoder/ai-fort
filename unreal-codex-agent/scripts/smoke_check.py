from __future__ import annotations

import argparse
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _run(name: str, command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{name} failed with exit code {completed.returncode}\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )
    return completed


def _print_check(name: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"[ok] {name}{suffix}")


def _parse_json(path: Path) -> None:
    json.loads(path.read_text(encoding="utf-8"))


def _parse_json_stdout(output: str) -> Any:
    return json.loads(output)


def _compile_all_python(repo_root: Path) -> int:
    count = 0
    for path in repo_root.rglob("*.py"):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        py_compile.compile(str(path), doraise=True)
        count += 1
    return count


def _latest_session_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Created session:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"Could not parse session id from output:\n{output}")


def _powershell() -> list[str] | None:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return None
    return [exe, "-ExecutionPolicy", "Bypass", "-File"]


def run_smoke_checks(repo_root: Path) -> None:
    config_jsons = sorted((repo_root / "config").glob("*.json"))
    example_jsons = sorted((repo_root / "examples").glob("*.json"))
    for path in config_jsons + example_jsons:
        _parse_json(path)
    _print_check("json config/examples", str(len(config_jsons) + len(example_jsons)))

    plugin_manifest = repo_root / "unreal" / "plugin" / "UCADeveloperTools" / "UCADeveloperTools.uplugin"
    _parse_json(plugin_manifest)
    _print_check("developer plugin manifest", plugin_manifest.name)

    compiled = _compile_all_python(repo_root)
    _print_check("python compile", str(compiled))

    scene_state_output = _run(
        "scene_tools scene-state",
        [sys.executable, "-m", "apps.mcp_extensions.scene_tools", "scene-state", "--repo-root", "."],
        cwd=repo_root,
    ).stdout
    scene_state = json.loads(scene_state_output)
    _print_check("scene_tools scene-state", scene_state.get("scene_state_backend", "unknown"))

    _run(
        "catalog_tools search query",
        [sys.executable, "-m", "apps.mcp_extensions.catalog_tools", "search", "--repo-root", ".", "--query", "sofa"],
        cwd=repo_root,
    )
    _print_check("catalog_tools search")

    build_index = _run(
        "catalog_tools build-index",
        [sys.executable, "-m", "apps.mcp_extensions.catalog_tools", "build-index", "--repo-root", "."],
        cwd=repo_root,
    )
    build_index_payload = _parse_json_stdout(build_index.stdout)
    _print_check("catalog_tools build-index", str(build_index_payload.get("catalog_records", 0)))

    _run(
        "catalog_tools shortlist",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.catalog_tools",
            "shortlist",
            "--repo-root",
            ".",
            "--room-type",
            "living_room",
            "--min-trust",
            "medium",
            "--limit",
            "3",
        ],
        cwd=repo_root,
    )
    _print_check("catalog_tools shortlist")

    catalog_records = _parse_json_stdout(
        _run(
            "catalog_tools search all",
            [sys.executable, "-m", "apps.mcp_extensions.catalog_tools", "search", "--repo-root", ".", "--limit", "10"],
            cwd=repo_root,
        ).stdout
    )
    if not catalog_records:
        raise RuntimeError("Catalog smoke check could not find any records.")
    sample_record = catalog_records[0]
    sample_asset_id = str(sample_record["asset_id"])
    sample_asset_path = str(sample_record["asset_path"])

    _run(
        "catalog_tools get-asset",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.catalog_tools",
            "get-asset",
            "--repo-root",
            ".",
            "--asset-id",
            sample_asset_id,
        ],
        cwd=repo_root,
    )
    _print_check("catalog_tools get-asset", sample_asset_id)

    _run(
        "catalog_tools safe-scale existing",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.catalog_tools",
            "safe-scale",
            "--repo-root",
            ".",
            "--asset-id",
            sample_asset_id,
        ],
        cwd=repo_root,
    )
    _print_check("catalog_tools safe-scale existing")

    _run(
        "catalog_tools safe-scale inferred",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.catalog_tools",
            "safe-scale",
            "--repo-root",
            ".",
            "--category",
            "opening",
            "--function-name",
            "access",
        ],
        cwd=repo_root,
    )
    _print_check("catalog_tools safe-scale inferred")

    quarantine_payload = _parse_json_stdout(
        _run(
            "catalog_tools mark-quarantine",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.catalog_tools",
                "mark-quarantine",
                "--repo-root",
                ".",
                "--asset-id",
                sample_asset_id,
                "--reason",
                "smoke_check_quarantine",
            ],
            cwd=repo_root,
        ).stdout
    )
    if quarantine_payload.get("status") == "approved":
        raise RuntimeError("catalog_tools mark-quarantine did not update asset status.")
    _print_check("catalog_tools mark-quarantine", sample_asset_id)

    _run(
        "catalog_tools update-asset",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.catalog_tools",
            "update-asset",
            "--repo-root",
            ".",
            "--asset-path",
            sample_asset_path,
        ],
        cwd=repo_root,
    )
    _print_check("catalog_tools update-asset restore", sample_asset_id)

    _run(
        "capture_tools scene",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.capture_tools",
            "scene",
            "--repo-root",
            ".",
            "--session-path",
            ".\\data\\sessions\\smoke_capture_scene",
            "--cycle-number",
            "1",
        ],
        cwd=repo_root,
    )
    _print_check("capture_tools scene")

    developer_status = _parse_json_stdout(
        _run(
            "developer_tools status",
            [sys.executable, "-m", "apps.mcp_extensions.developer_tools", "status", "--repo-root", "."],
            cwd=repo_root,
        ).stdout
    )
    if "scene_xray" not in developer_status:
        raise RuntimeError("developer_tools status did not return scene_xray settings.")
    _print_check("developer_tools status")

    defaults_hidden = _parse_json_stdout(
        _run(
            "developer_tools set-defaults hidden tool list",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.developer_tools",
                "set-defaults",
                "--repo-root",
                ".",
                "--xray-on",
                "true",
                "--show-identified",
                "true",
                "--show-undefined",
                "true",
                "--show-labels",
                "true",
                "--show-tool-list",
                "false",
            ],
            cwd=repo_root,
        ).stdout
    )
    if bool(defaults_hidden.get("scene_xray", {}).get("default_show_tool_list", True)):
        raise RuntimeError("developer_tools set-defaults did not disable the default tool list.")
    _print_check("developer_tools default tool list off")

    defaults_shown = _parse_json_stdout(
        _run(
            "developer_tools toggle-scene-xray-tool-list",
            [sys.executable, "-m", "apps.mcp_extensions.developer_tools", "toggle-scene-xray-tool-list", "--repo-root", "."],
            cwd=repo_root,
        ).stdout
    )
    if not bool(defaults_shown.get("scene_xray", {}).get("default_show_tool_list", False)):
        raise RuntimeError("developer_tools toggle-scene-xray-tool-list did not restore the tool list.")
    _print_check("developer_tools default tool list on")

    current_developer_tools = _parse_json_stdout(
        _run(
            "developer_tools status pre-toggle",
            [sys.executable, "-m", "apps.mcp_extensions.developer_tools", "status", "--repo-root", "."],
            cwd=repo_root,
        ).stdout
    )
    if not bool(dict(current_developer_tools.get("scene_xray") or {}).get("auto_generate_per_cycle", True)):
        _run(
            "developer_tools normalize-scene-xray-auto on",
            [sys.executable, "-m", "apps.mcp_extensions.developer_tools", "toggle-scene-xray-auto", "--repo-root", "."],
            cwd=repo_root,
        )
    toggle_off = _parse_json_stdout(
        _run(
            "developer_tools toggle-scene-xray-auto off",
            [sys.executable, "-m", "apps.mcp_extensions.developer_tools", "toggle-scene-xray-auto", "--repo-root", "."],
            cwd=repo_root,
        ).stdout
    )
    if bool(toggle_off.get("scene_xray", {}).get("auto_generate_per_cycle", True)):
        raise RuntimeError("developer_tools toggle-scene-xray-auto did not disable auto generation.")
    off_create = _run(
        "orchestrator create-session xray-off",
        [
            sys.executable,
            "-m",
            "apps.orchestrator.main",
            "create-session",
            "--repo-root",
            ".",
            "--goal",
            "Smoke xray off",
            "--session-name",
            "smoke_xray_off",
        ],
        cwd=repo_root,
    )
    off_session_id = _latest_session_id(off_create.stdout)
    _run(
        "orchestrator run-once xray-off",
        [
            sys.executable,
            "-m",
            "apps.orchestrator.main",
            "run-once",
            "--repo-root",
            ".",
            "--session-id",
            off_session_id,
        ],
        cwd=repo_root,
    )
    off_xray_html = repo_root / "data" / "sessions" / off_session_id / "developer_xray" / "cycle_0001.html"
    if off_xray_html.exists():
        raise RuntimeError("Scene xray auto-generate was disabled, but an xray artifact was still written.")
    shutil.rmtree(repo_root / "data" / "sessions" / off_session_id, ignore_errors=True)
    _print_check("developer_tools auto xray off")

    toggle_on = _parse_json_stdout(
        _run(
            "developer_tools toggle-scene-xray-auto on",
            [sys.executable, "-m", "apps.mcp_extensions.developer_tools", "toggle-scene-xray-auto", "--repo-root", "."],
            cwd=repo_root,
        ).stdout
    )
    if not bool(toggle_on.get("scene_xray", {}).get("auto_generate_per_cycle", False)):
        raise RuntimeError("developer_tools toggle-scene-xray-auto did not re-enable auto generation.")
    _print_check("developer_tools auto xray on")

    create = _run(
        "orchestrator create-session",
        [
            sys.executable,
            "-m",
            "apps.orchestrator.main",
            "create-session",
            "--repo-root",
            ".",
            "--goal",
            "Smoke lifecycle",
            "--session-name",
            "smoke_check",
        ],
        cwd=repo_root,
    )
    session_id = _latest_session_id(create.stdout)
    _print_check("orchestrator create-session", session_id)

    _run(
        "orchestrator run-once",
        [
            sys.executable,
            "-m",
            "apps.orchestrator.main",
            "run-once",
            "--repo-root",
            ".",
            "--session-id",
            session_id,
        ],
        cwd=repo_root,
    )
    _print_check("orchestrator run-once")
    auto_xray_html = repo_root / "data" / "sessions" / session_id / "developer_xray" / "cycle_0001.html"
    if not auto_xray_html.exists():
        raise RuntimeError(f"Automatic developer xray artifact missing: {auto_xray_html}")
    _print_check("automatic developer xray", auto_xray_html.name)

    _run(
        "scene_tools dirty-zone",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.scene_tools",
            "dirty-zone",
            "--repo-root",
            ".",
            "--scene-state-json",
            f".\\data\\sessions\\{session_id}\\scene_state\\cycle_0001.json",
            "--cycle-number",
            "1",
        ],
        cwd=repo_root,
    )
    _print_check("scene_tools dirty-zone")

    missing_scene_payload = _parse_json_stdout(
        _run(
            "scene_tools dirty-zone degraded",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.scene_tools",
                "dirty-zone",
                "--repo-root",
                ".",
                "--scene-state-json",
                str(repo_root / "data" / "sessions" / "missing_scene_smoke" / "scene_state" / "cycle_0001.json"),
                "--cycle-number",
                "1",
            ],
            cwd=repo_root,
        ).stdout
    )
    if missing_scene_payload.get("status") != "ok":
        raise RuntimeError("scene_tools degraded dirty-zone did not fail open.")
    _print_check("scene_tools degraded dirty-zone")

    _run(
        "capture_tools zone",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.capture_tools",
            "zone",
            "--repo-root",
            ".",
            "--session-path",
            f".\\data\\sessions\\{session_id}",
            "--session-id",
            session_id,
            "--cycle-number",
            "1",
        ],
        cwd=repo_root,
    )
    _print_check("capture_tools zone")

    degraded_capture_session = repo_root / "data" / "sessions" / "capture_degraded_smoke"
    degraded_capture_session.mkdir(parents=True, exist_ok=True)
    degraded_capture = _parse_json_stdout(
        _run(
            "capture_tools zone degraded",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.capture_tools",
                "zone",
                "--repo-root",
                ".",
                "--session-id",
                "capture_degraded_smoke",
                "--cycle-number",
                "1",
            ],
            cwd=repo_root,
        ).stdout
    )
    if not any("missing scene state" in note for note in degraded_capture.get("notes", [])):
        raise RuntimeError("capture_tools degraded zone did not surface fallback notes.")
    _print_check("capture_tools degraded zone")

    developer_xray = _parse_json_stdout(
        _run(
            "developer_tools scene-xray",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.developer_tools",
                "scene-xray",
                "--repo-root",
                ".",
                "--session-id",
                session_id,
                "--cycle-number",
                "1",
            ],
            cwd=repo_root,
        ).stdout
    )
    artifacts = developer_xray.get("artifacts", {})
    if not artifacts or not Path(str(artifacts.get("html_path", ""))).exists():
        raise RuntimeError("developer_tools scene-xray did not produce an HTML artifact.")
    html_text = Path(str(artifacts.get("html_path"))).read_text(encoding="utf-8")
    if "toggleToolList" not in html_text or "Developer Tool List" not in html_text:
        raise RuntimeError("developer_tools scene-xray HTML is missing the tool list toggle UI.")
    _print_check("developer_tools scene-xray")

    invalid_scene_path = Path(tempfile.gettempdir()) / "unreal_codex_agent_invalid_scene_state.json"
    invalid_scene_path.write_text("{ invalid json", encoding="utf-8")
    degraded_output_dir = repo_root / "data" / "cache" / "developer_xray_smoke"
    degraded_payload = _parse_json_stdout(
        _run(
            "developer_tools scene-xray degraded",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.developer_tools",
                "scene-xray",
                "--repo-root",
                ".",
                "--scene-state-json",
                str(invalid_scene_path),
                "--output-dir",
                str(degraded_output_dir),
                "--force",
            ],
            cwd=repo_root,
        ).stdout
    )
    degraded_html = Path(str(degraded_payload.get("artifacts", {}).get("html_path", "")))
    if not degraded_html.exists():
        raise RuntimeError("developer_tools degraded scene-xray did not write an HTML artifact.")
    degraded_text = degraded_html.read_text(encoding="utf-8")
    if "Failsafe Notes" not in degraded_text:
        raise RuntimeError("developer_tools degraded scene-xray did not surface failsafe warnings.")
    _print_check("developer_tools degraded scene-xray")

    _run(
        "orchestrator status",
        [
            sys.executable,
            "-m",
            "apps.orchestrator.main",
            "status",
            "--repo-root",
            ".",
            "--session-id",
            session_id,
        ],
        cwd=repo_root,
    )
    _print_check("orchestrator status")

    _run(
        "validator_tools run",
        [
            sys.executable,
            "-m",
            "apps.mcp_extensions.validator_tools",
            "run",
            "--repo-root",
            ".",
            "--session-id",
            session_id,
            "--cycle-number",
            "1",
        ],
        cwd=repo_root,
    )
    _print_check("validator_tools run")

    degraded_validator_session = repo_root / "data" / "sessions" / "validator_degraded_smoke"
    degraded_validator_session.mkdir(parents=True, exist_ok=True)
    degraded_validator = _parse_json_stdout(
        _run(
            "validator_tools run degraded",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.validator_tools",
                "run",
                "--repo-root",
                ".",
                "--session-id",
                "validator_degraded_smoke",
                "--cycle-number",
                "1",
            ],
            cwd=repo_root,
        ).stdout
    )
    if "helper_warnings" not in degraded_validator:
        raise RuntimeError("validator_tools degraded run did not return helper warnings.")
    _print_check("validator_tools degraded run")

    _run(
        "start orchestrator directly",
        [
            sys.executable,
            "-m",
            "apps.orchestrator.main",
            "start",
            "--repo-root",
            ".",
            "--goal",
            "Smoke direct start",
            "--cycles",
            "1",
        ],
        cwd=repo_root,
    )
    _print_check("orchestrator start")

    _run(
        "generate_uefn_workspace",
        [sys.executable, ".\\scripts\\generate_uefn_workspace.py", "--repo-root", "."],
        cwd=repo_root,
    )
    _print_check("generate_uefn_workspace")

    _run(
        "check_uefn_setup",
        [sys.executable, ".\\scripts\\check_uefn_setup.py", "--repo-root", "."],
        cwd=repo_root,
    )
    _print_check("check_uefn_setup")

    _run(
        "uefn_tools status",
        [sys.executable, "-m", "apps.mcp_extensions.uefn_tools", "status", "--repo-root", "."],
        cwd=repo_root,
    )
    _print_check("uefn_tools status")

    mcp_status = _parse_json_stdout(
        _run(
            "uefn_tools mcp-status",
            [sys.executable, "-m", "apps.mcp_extensions.uefn_tools", "mcp-status", "--repo-root", "."],
            cwd=repo_root,
        ).stdout
    )
    if "package_installed" not in mcp_status:
        raise RuntimeError("uefn_tools mcp-status did not return MCP status fields.")
    _print_check("uefn_tools mcp-status")

    export_cycle = _parse_json_stdout(
        _run(
            "uefn_tools export-cycle",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.uefn_tools",
                "export-cycle",
                "--repo-root",
                ".",
                "--session-id",
                session_id,
                "--cycle-number",
                "1",
            ],
            cwd=repo_root,
        ).stdout
    )
    if export_cycle.get("status") != "ok":
        raise RuntimeError("uefn_tools export-cycle did not succeed.")
    artifacts = dict(export_cycle.get("artifacts") or {})
    if not Path(str(artifacts.get("placement_verse_path", ""))).exists():
        raise RuntimeError("uefn_tools export-cycle did not write the generated Verse scaffold.")
    if not Path(str(artifacts.get("debug_overlay_path", ""))).exists():
        raise RuntimeError("uefn_tools export-cycle did not write the debug overlay payload.")
    placement_verse_text = Path(str(artifacts.get("placement_verse_path", ""))).read_text(encoding="utf-8")
    if "Enable Verse Debug Draw" not in placement_verse_text and "No exported placement overlay is available yet." not in placement_verse_text:
        raise RuntimeError("Generated placement Verse scaffold did not include the expected debug bridge messaging.")
    _print_check("uefn_tools export-cycle")

    export_publish_safe = _parse_json_stdout(
        _run(
            "uefn_tools export-publish-safe",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.uefn_tools",
                "export-publish-safe",
                "--repo-root",
                ".",
                "--session-id",
                session_id,
                "--cycle-number",
                "1",
            ],
            cwd=repo_root,
        ).stdout
    )
    if export_publish_safe.get("backend") != "uefn_verse_apply":
        raise RuntimeError("uefn_tools export-publish-safe did not route through the publish-safe Verse backend.")
    export_artifacts = dict(export_publish_safe.get("artifacts") or {})
    if not Path(str(export_artifacts.get("apply_path", ""))).exists():
        raise RuntimeError("uefn_tools export-publish-safe did not write the managed apply queue payload.")
    _print_check("uefn_tools export-publish-safe")

    sync_destination = repo_root / "data" / "cache" / "uefn_sync_smoke"
    sync_payload = _parse_json_stdout(
        _run(
            "uefn_tools sync-verse",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.uefn_tools",
                "sync-verse",
                "--repo-root",
                ".",
                "--destination",
                str(sync_destination),
            ],
            cwd=repo_root,
        ).stdout
    )
    synced_files = list(sync_payload.get("files") or [])
    if not synced_files:
        raise RuntimeError("uefn_tools sync-verse did not report any synced files.")
    if not any(Path(str(file_record.get("destination", ""))).exists() for file_record in synced_files):
        raise RuntimeError("uefn_tools sync-verse did not write any Verse files to the destination.")
    _print_check("uefn_tools sync-verse")

    diff_layout = _parse_json_stdout(
        _run(
            "uefn_tools diff-layout",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.uefn_tools",
                "diff-layout",
                "--repo-root",
                ".",
                "--session-id",
                session_id,
            ],
            cwd=repo_root,
        ).stdout
    )
    if "layout_diff" not in diff_layout:
        raise RuntimeError("uefn_tools diff-layout did not return a layout diff payload.")
    _print_check("uefn_tools diff-layout")

    inspect_support = _parse_json_stdout(
        _run(
            "uefn_tools inspect-support",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.uefn_tools",
                "inspect-support",
                "--repo-root",
                ".",
                "--actor",
                str(scene_state.get("placement_targets", {}).get("support_actor_label") or "GridPlane4"),
            ],
            cwd=repo_root,
        ).stdout
    )
    if "support_fit" not in inspect_support:
        raise RuntimeError("uefn_tools inspect-support did not return support fit details.")
    _print_check("uefn_tools inspect-support")

    release_managed = _parse_json_stdout(
        _run(
            "uefn_tools release-managed",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.uefn_tools",
                "release-managed",
                "--repo-root",
                ".",
                "--session-id",
                session_id,
                "--zone",
                "zone_0001",
                "--slot",
                "primary",
                "--reason",
                "smoke_check_release",
            ],
            cwd=repo_root,
        ).stdout
    )
    if release_managed.get("status") not in {"ok", "warning"}:
        raise RuntimeError("uefn_tools release-managed did not return a valid result.")
    _print_check("uefn_tools release-managed")

    mcp_sync_root = repo_root / "data" / "cache" / "uefn_mcp_smoke"
    mcp_sync_payload = _parse_json_stdout(
        _run(
            "uefn_tools sync-mcp-listener",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.uefn_tools",
                "sync-mcp-listener",
                "--repo-root",
                ".",
                "--destination",
                str(mcp_sync_root),
            ],
            cwd=repo_root,
        ).stdout
    )
    if not Path(str(mcp_sync_payload.get("listener_path", ""))).exists():
        raise RuntimeError("uefn_tools sync-mcp-listener did not write the listener file.")
    if not Path(str(mcp_sync_payload.get("init_path", ""))).exists():
        raise RuntimeError("uefn_tools sync-mcp-listener did not write init_unreal.py.")
    _print_check("uefn_tools sync-mcp-listener")

    mcp_config_path = mcp_sync_root / ".mcp.json"
    mcp_config_payload = _parse_json_stdout(
        _run(
            "uefn_tools write-mcp-config",
            [
                sys.executable,
                "-m",
                "apps.mcp_extensions.uefn_tools",
                "write-mcp-config",
                "--repo-root",
                ".",
                "--output-path",
                str(mcp_config_path),
            ],
            cwd=repo_root,
        ).stdout
    )
    resolved_config_path = Path(str(mcp_config_payload.get("client_config_path", "")))
    if not resolved_config_path.exists():
        raise RuntimeError("uefn_tools write-mcp-config did not create an MCP config file.")
    _parse_json(resolved_config_path)
    _print_check("uefn_tools write-mcp-config")

    packet_path = Path(tempfile.gettempdir()) / "unreal_codex_agent_smoke_capture_packet.json"
    packet_path.write_text(
        json.dumps(
            {
                "packet_id": "smoke_packet",
                "zone_id": "zone_smoke",
                "profile": "default_room",
                "shell_crosscheck": False,
                "images": [
                    {
                        "label": "local_object",
                        "path": str(repo_root / "data" / "previews" / "smoke_local_object.png"),
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _run(
        "ue_capture_views placeholder",
        [sys.executable, str(repo_root / "unreal" / "python" / "ue_capture_views.py"), str(packet_path)],
        cwd=repo_root,
    )
    _print_check("ue_capture_views placeholder")

    _run(
        "ue_scene_state.py",
        [sys.executable, str(repo_root / "unreal" / "python" / "ue_scene_state.py")],
        cwd=repo_root,
    )
    _print_check("ue_scene_state.py")

    _run(
        "ue_measure_asset.py",
        [sys.executable, str(repo_root / "unreal" / "python" / "ue_measure_asset.py"), "/Game/Fake/Asset"],
        cwd=repo_root,
    )
    _print_check("ue_measure_asset.py")

    _run(
        "validator_clearance.py",
        [
            sys.executable,
            str(repo_root / "unreal" / "validators" / "validator_clearance.py"),
            '{"front_cm": 90, "side_cm": 28, "back_cm": 8}',
            '{"front_cm": 60, "side_cm": 10, "back_cm": 3}',
        ],
        cwd=repo_root,
    )
    _print_check("validator_clearance.py")

    _run(
        "validator_shell.py",
        [
            sys.executable,
            str(repo_root / "unreal" / "validators" / "validator_shell.py"),
            "false",
            '{"inside_checked": false, "outside_checked": false, "is_consistent": null}',
        ],
        cwd=repo_root,
    )
    _print_check("validator_shell.py")

    _run(
        "validator_asset_trust.py",
        [
            sys.executable,
            str(repo_root / "unreal" / "validators" / "validator_asset_trust.py"),
            '{"asset_id": "smoke_asset", "asset_path": "/Game/Fake/Asset", "trust_score": 90, "status": "approved"}',
            "70",
        ],
        cwd=repo_root,
    )
    _print_check("validator_asset_trust.py")

    _run(
        "validator_scale.py",
        [
            sys.executable,
            str(repo_root / "unreal" / "validators" / "validator_scale.py"),
            "/Game/Fake/Asset",
            '{"width_min": 1, "width_max": 10, "depth_min": 1, "depth_max": 10, "height_min": 1, "height_max": 10}',
        ],
        cwd=repo_root,
    )
    _print_check("validator_scale.py")

    _run(
        "validator_metadata.py",
        [
            sys.executable,
            str(repo_root / "unreal" / "validators" / "validator_metadata.py"),
            "/Game/Fake/Asset",
            '["asset_ai.category"]',
        ],
        cwd=repo_root,
    )
    _print_check("validator_metadata.py")

    from apps.asset_ai.shortlist import shortlist_assets
    from apps.codex_bridge.codex_session import CodexSession
    from apps.codex_bridge.prompt_builder import PromptBuilder
    from apps.codex_bridge.response_parser import parse_action_response
    from apps.capture_service.capture_manager import CaptureManager
    from apps.capture_service.image_cache import ImageCache
    from apps.capture_service.scene_packet import build_scene_packet
    from apps.integrations.prefabricator import should_prefer_prefabs
    from apps.mcp_extensions.scene_tools import enrich_scene_state
    from apps.codex_bridge.retry_policy import RetryConfig, RetryPolicy
    from apps.orchestrator.action_queue import Action
    from apps.orchestrator.completion_gate import CompletionGate
    from apps.orchestrator.dirty_zone import DirtyZone
    from apps.orchestrator.scoring import ScoreCalculator
    from apps.orchestrator.session_manager import SessionManager
    from apps.orchestrator.state_store import SessionStateStore
    from apps.placement.profile_store import load_pose_profile, save_pose_profile
    from apps.placement.placement_solver import infer_expected_mount_type, normalize_action_payload
    from apps.validation.report_builder import build_rule_result, build_validation_report
    from apps.validation.rules.orientation_fit import validate_orientation_fit
    from apps.validation.rules.room_fit import validate_room_fit
    from apps.validation.rules.support_surface_fit import validate_support_surface_fit

    codex = CodexSession(repo_root=repo_root)
    dirty_zone = DirtyZone(
        zone_id="zone_smoke",
        actor_ids=[],
        room_type="living_room",
        zone_type="room_local",
        shell_sensitive=False,
        capture_profile="default_room",
        bounds={},
    )
    capture_packet = {
        "packet_id": "smoke_packet",
        "zone_id": "zone_smoke",
        "profile": "default_room",
        "shell_crosscheck": False,
        "images": [],
        "notes": [],
        "capture_backend": "placeholder",
    }
    shortlist = [
        {
            "asset_id": "smoke_asset",
            "asset_path": "/Game/Props/Furniture/SM_Modern_Sofa_A",
            "trust_score": 95,
        }
    ]
    action_payload = codex.choose_action(
        build_goal="Smoke Codex decision",
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        capture_packet=capture_packet,
        shortlist=shortlist,
    )
    review_payload = codex.review_edit(
        build_goal="Smoke Codex review",
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        capture_packet=capture_packet,
        action=Action.from_dict(action_payload),
        validation_report={"blocking_failures": [], "warnings": []},
    )
    completion_payload = codex.completion_check(
        build_goal="Smoke Codex completion",
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        capture_packet=capture_packet,
        validation_report={"blocking_failures": [], "warnings": []},
        unresolved_issues=[],
    )
    if not action_payload or not review_payload or not completion_payload:
        raise RuntimeError("Codex mock flow returned empty payloads.")
    _print_check("codex bridge mock flow")

    parsed_action = parse_action_response(
        """```json
        {
          "action": "place_asset",
          "target_zone": "zone_parser",
          "reason": "Recovered relaxed JSON",
          "confidence": 0.8,
          "asset_path": "/Game/Props/SM_Test",
          "transform": {
            "location": [0, 0, 0,],
            "rotation": [0, 0, 90,],
            "scale": [1, 1, 1,],
          },
          "expected_outcome": "Parser smoke",
          "alternatives": [],
        }
        ```"""
    )
    if parsed_action.action != "place_asset" or parsed_action.transform.rotation != [0.0, 0.0, 90.0]:
        raise RuntimeError("Response parser did not recover a relaxed JSON action response.")
    _print_check("response parser relaxed json")

    prompt_builder = PromptBuilder(repo_root=repo_root)
    prompt_payload = prompt_builder.build_action_payload(
        build_goal="Smoke prompt payload",
        scene_state={
            "expected_mount_type": "corner",
            "placement_context": {"mount_type": "corner"},
            "placement_targets": {"corner_anchor": [10.0, 20.0, 30.0]},
            "placement_reference_quality": "derived_actor_reference",
        },
        dirty_zone={"zone_id": "zone_prompt"},
        capture_packet=capture_packet,
        shortlist=[],
    )
    placement_summary = prompt_payload.get("scene_packet", {}).get("placement_summary", {})
    if placement_summary.get("prefabricator_enabled") is not False:
        raise RuntimeError("PromptBuilder did not reflect the default disabled Prefabricator state.")
    if placement_summary.get("prefer_prefab_for_structural_mounts") is not False:
        raise RuntimeError("PromptBuilder incorrectly preferred prefabs while Prefabricator is disabled.")
    _print_check("prompt builder prefab gating")

    capture_tmp_root = repo_root / "data" / "sessions" / "capture_profile_smoke"
    capture_tmp_root.mkdir(parents=True, exist_ok=True)
    capture_context = type("CaptureContext", (), {"repo_root": repo_root, "session_path": capture_tmp_root})()
    capture_manager = CaptureManager(repo_root=repo_root)
    capture_packet_missing_profile = capture_manager.build_capture_packet(
        context=capture_context,
        dirty_zone=DirtyZone(
            zone_id="zone_capture_missing",
            actor_ids=[],
            room_type="living_room",
            zone_type="room_local",
            shell_sensitive=False,
            capture_profile="definitely_missing_profile",
            bounds={},
        ),
    )
    if capture_packet_missing_profile.get("profile") != "default_room":
        raise RuntimeError("CaptureManager did not fall back to default_room for a missing profile.")
    if not any("missing or invalid" in str(note) for note in capture_packet_missing_profile.get("notes", [])):
        raise RuntimeError("CaptureManager did not record a note for the missing profile fallback.")
    _print_check("capture manager profile fallback")

    scene_packet_summary = build_scene_packet(
        build_goal="Smoke scene packet",
        scene_state={"room_type": "living_room", "expected_mount_type": "corner", "placement_context": {"placement_family": "corner"}},
        dirty_zone={"zone_id": "zone_packet", "shell_sensitive": True},
        capture_packet={"profile": "shell_sensitive", "capture_backend": "placeholder", "images": [{"label": "a"}, {"label": "b"}]},
        shortlist=[{"asset_id": "one"}, {"asset_id": "two"}],
    )
    summary = scene_packet_summary.get("summary", {})
    if summary.get("image_count") != 2 or summary.get("shortlist_count") != 2 or summary.get("placement_family") != "corner":
        raise RuntimeError(f"Scene packet summary did not reflect capture/shortlist context: {scene_packet_summary}")
    _print_check("scene packet summary")

    image_cache = ImageCache(max_entries=2)
    live_cache_file = repo_root / "data" / "cache" / "live_cache_smoke.txt"
    live_cache_file.parent.mkdir(parents=True, exist_ok=True)
    live_cache_file.write_text("ok", encoding="utf-8")
    image_cache.put("zone:a", str(live_cache_file))
    image_cache.put("zone:b", str(live_cache_file))
    image_cache.put("zone:c", str(live_cache_file))
    if image_cache.size() != 2 or image_cache.get("zone:a") is not None:
        raise RuntimeError("ImageCache did not evict older entries as expected.")
    dead_cache_file = repo_root / "data" / "cache" / "dead_cache_smoke.txt"
    image_cache.put("zone:dead", str(dead_cache_file))
    if image_cache.get("zone:dead") is not None:
        raise RuntimeError("ImageCache did not drop a missing file entry.")
    image_cache.invalidate_prefix("zone:")
    if image_cache.size() != 0:
        raise RuntimeError("ImageCache did not invalidate entries by prefix.")
    _print_check("image cache hygiene")

    retry_policy = RetryPolicy(RetryConfig(max_attempts=0, base_delay_seconds=-1, backoff_multiplier=0))
    retry_result = retry_policy.run(lambda: "ok")
    if retry_result != "ok":
        raise RuntimeError("RetryPolicy normalization broke a simple call.")
    _print_check("retry policy normalization")

    roof_scene_state = {
        "map_name": "House_Rooftop_Test",
        "room_type": "rooftop",
        "dirty_bounds": {"origin": [103.0, 207.0, 309.0], "box_extent": [50.0, 50.0, 20.0]},
        "actors": [],
    }
    if infer_expected_mount_type(roof_scene_state) != "roof":
        raise RuntimeError("Placement solver did not infer a roof mount type for rooftop scene state.")
    roof_record = {
        "tags": {"mount_type": "roof", "placement_behavior": ["roof_aligned"]},
        "placement_rules": {"preferred_yaw_step_deg": 45, "preferred_pitch_step_deg": 15, "snap_grid_cm": 10, "allow_nonuniform_scale": False},
        "scale_limits": {"min": 1.0, "max": 1.0, "preferred": 1.0},
    }
    normalized_roof_action = normalize_action_payload(
        action_payload={
            "action": "place_asset",
            "asset_path": "/Game/Structures/SM_Roof_Module",
            "transform": {
                "location": [103.0, 207.0, 309.0],
                "rotation": [7.0, 14.0, 92.0],
                "scale": [1.1, 0.9, 1.0],
            },
        },
        scene_state=roof_scene_state,
        dirty_zone={"zone_id": "zone_0001", "room_type": "rooftop", "shell_sensitive": True, "bounds": roof_scene_state["dirty_bounds"]},
        asset_record=roof_record,
    )
    roof_transform = normalized_roof_action["transform"]
    if roof_transform["location"] != [100.0, 210.0, 310.0]:
        raise RuntimeError(f"Roof placement location did not snap as expected: {roof_transform['location']}")
    if roof_transform["rotation"] != [0.0, 15.0, 90.0]:
        raise RuntimeError(f"Roof placement rotation did not snap as expected: {roof_transform['rotation']}")
    if roof_transform["scale"] != [1.0, 1.0, 1.0]:
        raise RuntimeError(f"Roof placement scale did not normalize as expected: {roof_transform['scale']}")
    _print_check("placement solver roof snapping")

    corner_scene_state = {
        "map_name": "House_Corner_Test",
        "room_type": "living_room",
        "dirty_bounds": {"origin": [55.0, 65.0, 35.0], "box_extent": [40.0, 30.0, 35.0]},
        "actors": [{"label": "SM_Wall_Corner_A", "asset_path": "/Game/Structures/SM_Wall_Corner_A"}],
    }
    if infer_expected_mount_type(corner_scene_state) != "corner":
        raise RuntimeError("Placement solver did not infer a corner mount type from corner scene state.")
    _print_check("placement solver corner inference")

    landscape_scene_state = enrich_scene_state(
        {
            "map_name": "MyProject_Landscape_Test",
            "room_type": "living_room",
            "actors": [
                {
                    "label": "LandscapeStreamingProxy_2_5_0",
                    "actor_name": "LandscapeStreamingProxy_2_5_0",
                    "class_name": "LandscapeStreamingProxy",
                    "location": [640.0, 320.0, 64.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "bounds_cm": {"origin": [640.0, 320.0, 64.0], "box_extent": [512.0, 512.0, 32.0]},
                },
                {
                    "label": "SM_Tree_A",
                    "actor_name": "StaticMeshActor_21",
                    "class_name": "StaticMeshActor",
                    "location": [700.0, 350.0, 96.0],
                    "rotation": [0.0, 0.0, 45.0],
                    "bounds_cm": {"origin": [700.0, 350.0, 96.0], "box_extent": [25.0, 25.0, 96.0]},
                },
            ],
            "dirty_bounds": {},
        },
        repo_root,
    )
    landscape_targets = dict(landscape_scene_state.get("placement_targets") or {})
    if landscape_targets.get("support_actor_label") != "LandscapeStreamingProxy_2_5_0":
        raise RuntimeError(f"Landscape support actor was not preferred: {landscape_targets}")
    if landscape_targets.get("support_surface_kind") != "landscape":
        raise RuntimeError(f"Landscape support surface kind was not detected: {landscape_targets}")
    if landscape_targets.get("ground_anchor") != [640.0, 320.0, 96.0]:
        raise RuntimeError(f"Landscape ground anchor was not derived from the top surface: {landscape_targets}")
    normalized_landscape_action = normalize_action_payload(
        action_payload={
            "action": "place_asset",
            "asset_path": "/Game/Props/SM_Rock_A",
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        },
        scene_state=landscape_scene_state,
        dirty_zone={
            "zone_id": "zone_landscape",
            "room_type": "living_room",
            "shell_sensitive": False,
            "bounds": landscape_scene_state["dirty_bounds"],
        },
        asset_record={
            "tags": {"mount_type": "floor"},
            "placement_rules": {"snap_grid_cm": 0, "allow_nonuniform_scale": True},
            "scale_limits": {"min": 0.8, "max": 1.2, "preferred": 1.0},
        },
    )
    if normalized_landscape_action.get("transform", {}).get("location") != [640.0, 320.0, 96.0]:
        raise RuntimeError(f"Landscape placement did not lock to the terrain top surface: {normalized_landscape_action}")
    _print_check("placement solver landscape support anchor")

    slab_scene_state = enrich_scene_state(
        {
            "map_name": "MyProject_Slab_Test",
            "room_type": "living_room",
            "actors": [
                {
                    "label": "UpperSlab_Selected",
                    "actor_name": "UpperSlab_Selected",
                    "class_name": "GridPlane_C",
                    "selected": True,
                    "location": [500.0, 500.0, 100.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "bounds_cm": {"origin": [500.0, 500.0, 100.0], "box_extent": [500.0, 500.0, 10.0]},
                },
                {
                    "label": "Landscape_Main",
                    "actor_name": "Landscape_Main",
                    "class_name": "LandscapeStreamingProxy",
                    "location": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "bounds_cm": {"origin": [0.0, 0.0, 0.0], "box_extent": [5000.0, 5000.0, 5.0]},
                },
            ],
        },
        repo_root,
    )
    slab_targets = dict(slab_scene_state.get("placement_targets") or {})
    if slab_targets.get("support_actor_label") != "UpperSlab_Selected":
        raise RuntimeError(f"Selected slab was not preferred as the support surface: {slab_targets}")
    if slab_targets.get("surface_anchor") != [500.0, 500.0, 110.0] or slab_targets.get("ground_anchor") is not None:
        raise RuntimeError(f"Upper slab support anchors were derived incorrectly: {slab_targets}")
    _print_check("placement solver selected slab preference")

    reposition_action = normalize_action_payload(
        action_payload={
            "action": "move_actor",
            "asset_path": "/Game/Props/Furniture/SM_Test",
            "transform": {
                "location": [900.0, 900.0, 450.0],
                "rotation": [12.0, 20.0, 30.0],
                "scale": [1.1, 0.9, 1.0],
            },
        },
        scene_state=slab_scene_state,
        dirty_zone={"zone_id": "zone_slab", "room_type": "living_room", "shell_sensitive": False, "bounds": slab_scene_state["dirty_bounds"]},
        asset_record={"tags": {"mount_type": "floor"}, "scale_limits": {"min": 0.8, "max": 1.2, "preferred": 1.0}},
    )
    if reposition_action.get("placement_hint", {}).get("placement_phase") != "reposition":
        raise RuntimeError(f"Move action did not default to reposition semantics: {reposition_action}")
    if reposition_action.get("transform", {}).get("location") != [900.0, 900.0, 450.0]:
        raise RuntimeError(f"Reposition transform was unexpectedly resnapped: {reposition_action}")
    _print_check("placement solver reposition preserve transform")

    reanchor_action = normalize_action_payload(
        action_payload={
            "action": "move_actor",
            "asset_path": "/Game/Props/Furniture/SM_Test",
            "placement_hint": {"placement_phase": "reanchor"},
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        },
        scene_state=slab_scene_state,
        dirty_zone={"zone_id": "zone_slab", "room_type": "living_room", "shell_sensitive": False, "bounds": slab_scene_state["dirty_bounds"]},
        asset_record={"tags": {"mount_type": "floor"}, "scale_limits": {"min": 0.8, "max": 1.2, "preferred": 1.0}},
    )
    if reanchor_action.get("placement_hint", {}).get("snap_policy") != "force":
        raise RuntimeError(f"Reanchor action did not force snapping semantics: {reanchor_action}")
    if reanchor_action.get("transform", {}).get("location") != [500.0, 500.0, 110.0]:
        raise RuntimeError(f"Reanchor action did not snap back to the selected slab anchor: {reanchor_action}")
    _print_check("placement solver reanchor support snap")

    wall_scene_state = enrich_scene_state(
        {
            "map_name": "House_Wall_Test",
            "room_type": "living_room",
            "actors": [
                {
                    "label": "SM_Wall_Panel_A",
                    "asset_path": "/Game/Structures/SM_Wall_Panel_A",
                    "location": [123.0, 208.0, 140.0],
                    "rotation": [0.0, 0.0, 88.0],
                    "bounds_cm": {"origin": [123.0, 208.0, 140.0], "box_extent": [50.0, 5.0, 140.0]},
                }
            ],
            "dirty_bounds": {},
        },
        repo_root,
    )
    normalized_wall_action = normalize_action_payload(
        action_payload={
            "action": "place_asset",
            "asset_path": "/Game/Structures/SM_Door_Frame_A",
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [0.0, 0.0, 0.0],
            },
        },
        scene_state=wall_scene_state,
        dirty_zone={
            "zone_id": "zone_0002",
            "room_type": "living_room",
            "shell_sensitive": True,
            "bounds": wall_scene_state["dirty_bounds"],
        },
        asset_record={
            "tags": {"mount_type": "opening"},
            "placement_rules": {"preferred_yaw_step_deg": 90, "snap_grid_cm": 10, "allow_nonuniform_scale": False},
            "scale_limits": {"min": 1.0, "max": 1.0, "preferred": 1.0},
        },
    )
    wall_transform = normalized_wall_action["transform"]
    if wall_transform["location"] != [123.0, 208.0, 140.0]:
        raise RuntimeError(f"Wall placement did not lock to the derived plane anchor: {wall_transform['location']}")
    if wall_transform["rotation"] != [0.0, 0.0, 88.0]:
        raise RuntimeError(f"Wall placement did not align to the derived wall yaw: {wall_transform['rotation']}")
    if wall_transform["scale"] != [1.0, 1.0, 1.0]:
        raise RuntimeError(f"Wall placement did not normalize zero scale: {wall_transform['scale']}")
    _print_check("placement solver wall anchor alignment")

    structural_action = codex.choose_action(
        build_goal="Smoke structural codex decision",
        scene_state=wall_scene_state,
        dirty_zone=DirtyZone(
            zone_id="zone_structural",
            actor_ids=["SM_Wall_Panel_A"],
            room_type="living_room",
            zone_type="shell_boundary",
            shell_sensitive=True,
            capture_profile="shell_sensitive",
            bounds=wall_scene_state["dirty_bounds"],
        ),
        capture_packet=capture_packet,
        shortlist=[
            {
                "asset_id": "door_frame",
                "asset_name": "SM_Door_Frame_A",
                "asset_path": "/Game/Structures/SM_Door_Frame_A",
                "trust_score": 90,
                "tags": {"mount_type": "opening"},
                "scale_limits": {"min": 1.0, "max": 1.0, "preferred": 1.0},
            }
        ],
    )
    if structural_action.get("transform", {}).get("location") != [123.0, 208.0, 140.0]:
        raise RuntimeError(f"Codex mock action did not use the derived structural anchor: {structural_action}")
    if structural_action.get("spawn_label") != "SM_Door_Frame_A_SM_Wall_Panel_A":
        raise RuntimeError(f"Codex mock action did not generate a stable spawn label: {structural_action}")
    if structural_action.get("placement_strategy") != "asset_anchor_snap":
        raise RuntimeError(f"Codex mock action did not expose the placement strategy: {structural_action}")
    _print_check("codex bridge structural anchor action")

    anchored_score = ScoreCalculator().calculate(
        validation_report={"blocking_failures": [], "warnings": []},
        review={"decision": "keep"},
        action=Action.from_dict(structural_action),
        dirty_zone=DirtyZone(
            zone_id="zone_score",
            actor_ids=[],
            room_type="living_room",
            zone_type="room_local",
            shell_sensitive=False,
            capture_profile="default_room",
            bounds={},
        ),
    )
    if int(anchored_score.get("action_score", 0)) < 80:
        raise RuntimeError(f"Anchored structural action did not receive an upgraded action score: {anchored_score}")
    _print_check("scoring anchored action quality")

    validation_report = build_validation_report(
        zone_id="zone_report",
        rule_results=[
            build_rule_result(
                name="rule_a",
                passed=False,
                blocking=True,
                issues=["duplicate issue", "duplicate issue"],
                warnings=["duplicate warning"],
            ),
            build_rule_result(
                name="rule_b",
                passed=False,
                blocking=False,
                issues=["soft issue"],
                warnings=["duplicate warning"],
            ),
        ],
    )
    if validation_report.get("blocking_failures") != ["duplicate issue"]:
        raise RuntimeError(f"Validation report did not dedupe blocking failures: {validation_report}")
    if validation_report.get("warnings") != ["duplicate warning", "soft issue"]:
        raise RuntimeError(f"Validation report did not dedupe warnings: {validation_report}")
    _print_check("validation report dedupe")

    completion_result = CompletionGate().evaluate(
        validator_rules={"completion_gate": {"require_validator_pass": True, "require_visual_review_pass": True}},
        validation_report={"blocking_failures": [], "warnings": ["needs another look"]},
        review={"decision": "keep"},
        score={"overall_score": 92},
        dirty_zone=DirtyZone(
            zone_id="zone_complete",
            actor_ids=[],
            room_type="living_room",
            zone_type="room_local",
            shell_sensitive=False,
            capture_profile="default_room",
            bounds={},
        ),
    )
    if completion_result.get("decision") != "needs_more_review":
        raise RuntimeError(f"CompletionGate marked a warned zone complete too early: {completion_result}")
    _print_check("completion gate warning hold")

    compatible_mount_shortlist = shortlist_assets(
        catalog=[
            {
                "asset_id": "wall_piece",
                "asset_path": "/Game/Structures/SM_Wall_Panel_A",
                "status": "approved",
                "trust_score": 90,
                "trust_level": "high",
                "tags": {
                    "room_types": ["living_room"],
                    "function": ["structure"],
                    "mount_type": "wall",
                    "styles": ["modern"],
                },
                "dimensions_cm": {"width": 100.0, "depth": 10.0, "height": 250.0},
            }
        ],
        room_type="living_room",
        function_name="structure",
        mount_type="opening",
        style="modern",
        min_trust="high",
        room_dimensions={"width": 500.0, "depth": 500.0},
        limit=5,
    )
    if not compatible_mount_shortlist or compatible_mount_shortlist[0].get("asset_id") != "wall_piece":
        raise RuntimeError("Shortlist compatibility did not allow a wall piece for an opening-family placement.")
    _print_check("placement shortlist mount compatibility")

    prefab_structural_shortlist = shortlist_assets(
        catalog=[
            {
                "asset_id": "corner_prefab",
                "asset_path": "/Game/Prefabs/PA_Corner_Assembly_A",
                "asset_name": "PA_Corner_Assembly_A",
                "asset_class": "PrefabAsset",
                "status": "approved",
                "trust_score": 88,
                "trust_level": "high",
                "tags": {
                    "room_types": ["living_room"],
                    "function": ["structure"],
                    "mount_type": "corner",
                    "styles": ["modern"],
                    "is_prefab": True,
                    "prefab_family": "corner",
                    "placement_behavior": ["snap_to_corner", "prefab_anchor_driven"],
                },
                "dimensions_cm": {"width": 120.0, "depth": 120.0, "height": 250.0},
            },
            {
                "asset_id": "corner_mesh",
                "asset_path": "/Game/Structures/SM_Corner_Piece_A",
                "asset_name": "SM_Corner_Piece_A",
                "asset_class": "StaticMesh",
                "status": "approved",
                "trust_score": 92,
                "trust_level": "high",
                "tags": {
                    "room_types": ["living_room"],
                    "function": ["structure"],
                    "mount_type": "corner",
                    "styles": ["modern"],
                    "placement_behavior": ["snap_to_corner"],
                },
                "dimensions_cm": {"width": 120.0, "depth": 120.0, "height": 250.0},
            },
        ],
        room_type="living_room",
        function_name="structure",
        mount_type="corner",
        style="modern",
        min_trust="high",
        room_dimensions={"width": 500.0, "depth": 500.0},
        limit=5,
        prefer_structural_prefabs=True,
    )
    if not prefab_structural_shortlist or prefab_structural_shortlist[0].get("asset_id") != "corner_prefab":
        raise RuntimeError("Shortlist did not prefer prefab structural placement for a corner mount.")
    _print_check("placement shortlist prefab preference")

    plain_structural_shortlist = shortlist_assets(
        catalog=[
            {
                "asset_id": "corner_prefab",
                "asset_path": "/Game/Prefabs/PA_Corner_Assembly_A",
                "asset_name": "PA_Corner_Assembly_A",
                "asset_class": "PrefabAsset",
                "status": "approved",
                "trust_score": 88,
                "trust_level": "high",
                "tags": {
                    "room_types": ["living_room"],
                    "function": ["structure"],
                    "mount_type": "corner",
                    "styles": ["modern"],
                    "is_prefab": True,
                    "prefab_family": "corner",
                    "placement_behavior": ["snap_to_corner", "prefab_anchor_driven"],
                },
                "dimensions_cm": {"width": 120.0, "depth": 120.0, "height": 250.0},
            },
            {
                "asset_id": "corner_mesh",
                "asset_path": "/Game/Structures/SM_Corner_Piece_A",
                "asset_name": "SM_Corner_Piece_A",
                "asset_class": "StaticMesh",
                "status": "approved",
                "trust_score": 92,
                "trust_level": "high",
                "tags": {
                    "room_types": ["living_room"],
                    "function": ["structure"],
                    "mount_type": "corner",
                    "styles": ["modern"],
                    "placement_behavior": ["snap_to_corner"],
                },
                "dimensions_cm": {"width": 120.0, "depth": 120.0, "height": 250.0},
            },
        ],
        room_type="living_room",
        function_name="structure",
        mount_type="corner",
        style="modern",
        min_trust="high",
        room_dimensions={"width": 500.0, "depth": 500.0},
        limit=5,
        prefer_structural_prefabs=False,
    )
    if not plain_structural_shortlist or plain_structural_shortlist[0].get("asset_id") != "corner_mesh":
        raise RuntimeError("Shortlist still preferred a prefab when structural prefab preference was disabled.")
    _print_check("placement shortlist prefab toggle")

    if not should_prefer_prefabs(
        {
            "integrations": {
                "prefabricator": {
                    "enabled": True,
                    "prefer_prefabs_for_mount_types": ["opening", "corner", "roof"],
                }
            }
        },
        "corner",
    ):
        raise RuntimeError("Prefabricator settings did not enable corner prefab preference.")
    if should_prefer_prefabs({"integrations": {"prefabricator": {"enabled": False}}}, "corner"):
        raise RuntimeError("Prefabricator settings enabled prefab preference even though integration was disabled.")
    _print_check("prefabricator settings gating")

    prefab_room_fit = validate_room_fit(
        scene_state={"room_type": "living_room", "expected_mount_type": "corner"},
        dirty_zone={"room_type": "living_room"},
        asset_record={
            "tags": {
                "room_types": ["living_room"],
                "mount_type": "wall",
                "prefab_family": "corner",
                "is_prefab": True,
            }
        },
        enabled=True,
        fail_hard=True,
        require_room_type_match=True,
        require_mount_type_match=True,
    )
    if not bool(prefab_room_fit.get("passed", False)):
        raise RuntimeError(f"Prefab room-fit compatibility failed unexpectedly: {prefab_room_fit}")
    _print_check("prefab room-fit compatibility")

    smoke_profile = save_pose_profile(
        repo_root,
        asset_path="/Game/Smoke/SM_ProfilePose",
        rest_rotation_internal=[-90.0, 0.0, 0.0],
        orientation_candidate="roll_neg_90",
        height_cm=32.0,
        support_surface_kind="support_surface",
        support_fit_state="on_surface",
    )
    if load_pose_profile(repo_root, "/Game/Smoke/SM_ProfilePose") != smoke_profile:
        raise RuntimeError("Placement pose profile store did not round-trip the saved profile.")
    _print_check("placement pose profile cache")

    support_fit_scene_state = {
        "placement_targets": {"surface_anchor": [0.0, 0.0, 100.0], "support_surface_kind": "support_surface"},
        "dirty_bounds": {"surface_anchor": [0.0, 0.0, 100.0], "support_surface_kind": "support_surface"},
        "active_actor": {"bounds_cm": {"origin": [0.0, 0.0, 110.0], "box_extent": [10.0, 10.0, 10.0]}},
    }
    support_fit_action = {"placement_hint": {"placement_phase": "initial_place", "snap_policy": "initial_only"}}
    on_surface_fit = validate_support_surface_fit(
        scene_state=support_fit_scene_state,
        action=support_fit_action,
        enabled=True,
        fail_hard=True,
    )
    if not bool(on_surface_fit.get("passed", False)) or on_surface_fit.get("details", {}).get("support_surface_fit_state") != "on_surface":
        raise RuntimeError(f"Support-surface fit validator flagged a correct slab placement unexpectedly: {on_surface_fit}")
    support_fit_scene_state["active_actor"]["bounds_cm"]["origin"] = [0.0, 0.0, 130.0]
    floating_fit = validate_support_surface_fit(
        scene_state=support_fit_scene_state,
        action=support_fit_action,
        enabled=True,
        fail_hard=True,
    )
    if bool(floating_fit.get("passed", False)) or floating_fit.get("details", {}).get("support_surface_fit_state") != "floating":
        raise RuntimeError(f"Support-surface fit validator did not report a floating actor: {floating_fit}")
    _print_check("support surface fit states")

    orientation_fit = validate_orientation_fit(
        repo_root=repo_root,
        scene_state={
            "expected_mount_type": "floor",
            "active_actor": {"rotation": [-90.0, 0.0, 0.0], "orientation_height_cm": 32.0},
        },
        action={
            "asset_path": "/Game/Smoke/SM_ProfilePose",
            "placement_hint": {"placement_phase": "initial_place", "snap_policy": "initial_only", "mount_type": "floor"},
        },
        enabled=True,
        fail_hard=True,
    )
    if not bool(orientation_fit.get("passed", False)):
        raise RuntimeError(f"Orientation-fit validator rejected a cached rest pose unexpectedly: {orientation_fit}")
    _print_check("orientation fit cached pose")

    original_mode = os.environ.get("CODEX_BRIDGE_MODE")
    original_command = os.environ.get("CODEX_BRIDGE_COMMAND")
    try:
        os.environ["CODEX_BRIDGE_MODE"] = "external"
        os.environ["CODEX_BRIDGE_COMMAND"] = "python -c \"import sys; sys.exit(9)\""
        failing_codex = CodexSession(repo_root=repo_root)
        fallback_action = failing_codex.choose_action(
            build_goal="Smoke Codex failure fallback",
            scene_state=scene_state,
            dirty_zone=dirty_zone,
            capture_packet=capture_packet,
            shortlist=shortlist,
        )
        if not fallback_action.get("bridge_fallback"):
            raise RuntimeError("Codex external failure did not fall back to a mock-safe action.")
    finally:
        if original_mode is None:
            os.environ.pop("CODEX_BRIDGE_MODE", None)
        else:
            os.environ["CODEX_BRIDGE_MODE"] = original_mode
        if original_command is None:
            os.environ.pop("CODEX_BRIDGE_COMMAND", None)
        else:
            os.environ["CODEX_BRIDGE_COMMAND"] = original_command
    _print_check("codex bridge external fallback")

    broken_session_id = "broken_session_smoke"
    broken_session_path = repo_root / "data" / "sessions" / broken_session_id
    broken_session_path.mkdir(parents=True, exist_ok=True)
    (broken_session_path / "session.json").write_text("{ bad json", encoding="utf-8")
    recovered_session = SessionManager(
        session_root=repo_root / "data" / "sessions",
        state_store=SessionStateStore(repo_root=repo_root),
    ).get_session(broken_session_id)
    if recovered_session is None or recovered_session.session_id != broken_session_id:
        raise RuntimeError("SessionManager did not recover a malformed session file.")
    _print_check("session manager recovery")

    powershell = _powershell()
    if powershell is not None:
        _run(
            "run_index_once.ps1",
            powershell + [str(repo_root / "scripts" / "run_index_once.ps1")],
            cwd=repo_root,
        )
        _print_check("run_index_once.ps1")

        _run(
            "run_validation_pass.ps1",
            powershell
            + [
                str(repo_root / "scripts" / "run_validation_pass.ps1"),
                "-SessionId",
                session_id,
            ],
            cwd=repo_root,
        )
        _print_check("run_validation_pass.ps1")

        _run(
            "start_agent.ps1",
            powershell
            + [
                str(repo_root / "scripts" / "start_agent.ps1"),
                "-Goal",
                "Smoke agent launcher",
                "-Cycles",
                "1",
            ],
            cwd=repo_root,
        )
        _print_check("start_agent.ps1")

        _run(
            "setup_free_stack.ps1",
            powershell + [str(repo_root / "scripts" / "setup_free_stack.ps1")],
            cwd=repo_root,
        )
        _print_check("setup_free_stack.ps1")

        _run(
            "clean_session.ps1",
            powershell
            + [
                str(repo_root / "scripts" / "clean_session.ps1"),
                "-SessionId",
                session_id,
            ],
            cwd=repo_root,
        )
        _print_check("clean_session.ps1", session_id)
    else:
        print("[skip] PowerShell scripts: powershell/pwsh not available")

    try:
        packet_path.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        invalid_scene_path.unlink(missing_ok=True)
    except Exception:
        pass
    shutil.rmtree(repo_root / "data" / "sessions" / broken_session_id, ignore_errors=True)
    shutil.rmtree(repo_root / "data" / "sessions" / "capture_degraded_smoke", ignore_errors=True)
    shutil.rmtree(repo_root / "data" / "sessions" / "validator_degraded_smoke", ignore_errors=True)
    shutil.rmtree(repo_root / "data" / "cache" / "uefn_sync_smoke", ignore_errors=True)
    shutil.rmtree(repo_root / "data" / "cache" / "uefn_mcp_smoke", ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run end-to-end smoke checks for unreal-codex-agent.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repo root path.")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    original_cwd = Path.cwd()
    try:
        os.chdir(repo_root)
        repo_root_str = str(repo_root)
        if repo_root_str not in sys.path:
            sys.path.insert(0, repo_root_str)
        run_smoke_checks(repo_root)
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    main()
