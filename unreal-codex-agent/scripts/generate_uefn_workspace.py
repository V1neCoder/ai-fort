from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.integrations.uefn_backend import backend_summary, verse_generated_root
from apps.mcp_extensions.uefn_tools import _write_scaffold_readme

app = typer.Typer(help="Generate local UEFN Verse scaffold folders and starter files.")


@app.command()
def main(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    readme_path = _write_scaffold_readme(repo_root)
    generated_root = verse_generated_root(repo_root)
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / ".gitkeep").write_text("", encoding="utf-8")
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "platform": "uefn",
                "summary": backend_summary(repo_root),
                "artifacts": {
                    "readme_path": readme_path.as_posix(),
                    "generated_root": generated_root.as_posix(),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
