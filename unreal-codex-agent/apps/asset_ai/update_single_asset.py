from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from apps.asset_ai.build_full_index import load_config, load_jsonl, load_raw_assets, save_outputs
from apps.asset_ai.quarantine import evaluate_quarantine
from apps.asset_ai.trust_score import enrich_record

app = typer.Typer(help="Update one asset record inside the local catalog.")


def read_catalog_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_jsonl(path)


def replace_record(records: list[dict[str, Any]], updated_record: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    updated_path = updated_record.get("asset_path")
    found = False
    for record in records:
        if record.get("asset_path") == updated_path:
            out.append(updated_record)
            found = True
        else:
            out.append(record)
    if not found:
        out.append(updated_record)
    return out


@app.command()
def main(
    asset_path: str = typer.Option(..., help="Exact asset path to update."),
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    raw_input: Path | None = typer.Option(None, help="Optional raw inventory override."),
) -> None:
    config = load_config(repo_root)
    raw_assets = load_raw_assets(repo_root, override=raw_input)
    raw_record = next((row for row in raw_assets if row.get("asset_path") == asset_path), None)
    if raw_record is None:
        raise typer.BadParameter(f"Asset path not found in raw inventory: {asset_path}")
    record = enrich_record(
        raw=raw_record,
        room_taxonomy=config["room_taxonomy"],
        placement_profiles=config["placement_profiles"],
        category_baselines=config["category_baselines"],
    )
    record = evaluate_quarantine(record, min_trust=int(config["project"]["asset_ai"]["quarantine_below_trust"]))
    catalog_jsonl = repo_root / config["project"]["paths"]["catalog_jsonl"]
    existing = read_catalog_jsonl(catalog_jsonl)
    updated_records = replace_record(existing, record)
    quarantined = [row for row in updated_records if row.get("quarantine", {}).get("is_quarantined")]
    save_outputs(repo_root, config, updated_records, quarantined)
    typer.echo(json.dumps({"updated_asset_path": asset_path, "new_status": record.get("status"), "trust_score": record.get("trust_score")}, indent=2))


def update_single_asset(asset_id: str) -> dict[str, Any]:
    return {"asset_id": asset_id, "updated": False, "status": "use_cli"}


if __name__ == "__main__":
    app()
