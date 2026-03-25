from __future__ import annotations

import json
from pathlib import Path

import typer

from apps.integrations.uefn_backend import backend_summary

app = typer.Typer(help="Legacy wrapper. The repo is now UEFN-first; use generate_uefn_workspace instead.")

def build_config(repo_root: Path, server_name: str = "uefn") -> dict[str, object]:
    summary = backend_summary(repo_root)
    return {
        "deprecated": True,
        "message": "This repo no longer uses runreal/unreal-mcp as the primary architecture. Use scripts/generate_uefn_workspace.py and UEFN Verse/device wiring instead.",
        "recommended_server_name": server_name,
        "summary": summary,
    }


@app.command()
def main(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    server_name: str = typer.Option("uefn", help="Client-visible runtime name."),
    output: Path | None = typer.Option(None, help="Optional output path for the JSON snippet."),
) -> None:
    config = build_config(repo_root=repo_root, server_name=server_name)
    rendered = json.dumps(config, indent=2)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        typer.echo(f"Wrote MCP config snippet to {output}")
    else:
        typer.echo(rendered)


if __name__ == "__main__":
    app()
