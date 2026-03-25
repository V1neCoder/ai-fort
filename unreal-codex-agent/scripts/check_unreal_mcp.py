from __future__ import annotations

import json
from pathlib import Path

import typer

from apps.integrations.uefn_backend import backend_summary

app = typer.Typer(help="Legacy wrapper. The repo is now UEFN-first; use check_uefn_setup instead.")


def run_health_check(repo_root: Path, verify_npx_package: bool = False) -> dict[str, object]:
    return {
        "deprecated": True,
        "message": "This repo no longer treats runreal/unreal-mcp as the primary supported workflow. Use scripts/check_uefn_setup.py instead.",
        "verify_npx_package_ignored": verify_npx_package,
        "summary": backend_summary(repo_root),
    }


@app.command()
def main(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    verify_npx_package: bool = typer.Option(False, help="Attempt to invoke the npx package with --help."),
) -> None:
    typer.echo(json.dumps(run_health_check(repo_root=repo_root, verify_npx_package=verify_npx_package), indent=2))


if __name__ == "__main__":
    app()
