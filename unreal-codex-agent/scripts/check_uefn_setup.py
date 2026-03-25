from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.integrations.uefn_backend import backend_summary

app = typer.Typer(help="Check UEFN + Verse workspace configuration for the local scaffold.")


@app.command()
def main(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    summary = backend_summary(repo_root)
    paths = dict(summary.get("paths") or {})
    checks = [
        {
            "name": "uefn_project_path_set",
            "ok": bool(paths.get("uefn_project_path")),
            "details": paths.get("uefn_project_path", ""),
        },
        {
            "name": "uefn_project_available",
            "ok": bool(summary.get("uefn_project_available", False)),
            "details": paths.get("uefn_project_path", ""),
        },
        {
            "name": "verse_workspace_available",
            "ok": bool(summary.get("verse_workspace_available", False)),
            "details": paths.get("verse_root", ""),
        },
        {
            "name": "uefn_content_root_available",
            "ok": bool(summary.get("uefn_content_root_available", False)),
            "details": paths.get("uefn_content_root", ""),
        },
        {
            "name": "uefn_mcp_enabled",
            "ok": bool((summary.get("uefn_mcp") or {}).get("enabled", False)),
            "details": "Vendored UEFN MCP bridge should stay enabled for live editor reads.",
        },
        {
            "name": "uefn_mcp_package_installed",
            "ok": bool((summary.get("uefn_mcp") or {}).get("package_installed", False)),
            "details": str(((summary.get("uefn_mcp") or {}).get("paths") or {}).get("server_path", "")),
        },
        {
            "name": "uefn_mcp_listener_deployed",
            "ok": bool((summary.get("uefn_mcp") or {}).get("listener_deployed", False)),
            "details": str(((summary.get("uefn_mcp") or {}).get("paths") or {}).get("content_python_root", "")),
        },
        {
            "name": "uefn_toolbelt_enabled",
            "ok": bool((summary.get("uefn_toolbelt") or {}).get("enabled", False)),
            "details": "Vendored UEFN Toolbelt support is enabled for direct editor tooling.",
        },
        {
            "name": "uefn_toolbelt_vendored",
            "ok": bool((summary.get("uefn_toolbelt") or {}).get("vendor_ready", False)),
            "details": str(((summary.get("uefn_toolbelt") or {}).get("paths") or {}).get("repo_root", "")),
        },
        {
            "name": "uefn_toolbelt_deployed",
            "ok": bool((summary.get("uefn_toolbelt") or {}).get("deployed", False)),
            "details": str(((summary.get("uefn_toolbelt") or {}).get("paths") or {}).get("content_python_root", "")),
        },
        {
            "name": "scene_graph_enabled",
            "ok": bool(summary.get("scene_graph_enabled", True)),
            "details": "Scene Graph should stay enabled if you plan to use entity/component workflows.",
        },
        {
            "name": "fortnite_devices_enabled",
            "ok": bool(summary.get("fortnite_devices_enabled", True)),
            "details": "Fortnite devices remain the supported authored-device workflow in UEFN.",
        },
    ]
    typer.echo(
        json.dumps(
            {
                "platform": "uefn",
                "passed": all(check["ok"] for check in checks if check["name"] != "uefn_project_path_set"),
                "checks": checks,
                "summary": summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
