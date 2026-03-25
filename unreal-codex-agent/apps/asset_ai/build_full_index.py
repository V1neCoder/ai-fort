from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from apps.asset_ai.quarantine import evaluate_quarantine
from apps.asset_ai.similarity import find_similar_records
from apps.asset_ai.trust_score import enrich_record

app = typer.Typer(help="Build the full asset catalog from a raw inventory export.")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def load_config(repo_root: Path) -> dict[str, Any]:
    config_dir = repo_root / "config"
    project = load_json(config_dir / "project.json")
    project.setdefault("paths", {})
    project["paths"].setdefault("catalog_db", "data/catalog/asset_catalog.sqlite")
    project["paths"].setdefault("catalog_jsonl", "data/catalog/asset_catalog.jsonl")
    project["paths"].setdefault("quarantine_jsonl", "data/catalog/quarantine.jsonl")
    project.setdefault("asset_ai", {})
    project["asset_ai"].setdefault("quarantine_below_trust", 50)
    return {
        "project": project,
        "room_taxonomy": load_json(config_dir / "room_taxonomy.json"),
        "tag_dictionary": load_json(config_dir / "tag_dictionary.json"),
        "placement_profiles": load_json(config_dir / "placement_profiles.json"),
        "category_baselines": load_json(config_dir / "category_baselines.json"),
    }


def raw_inventory_path(repo_root: Path, override: Path | None = None) -> Path:
    if override is not None:
        return override
    jsonl_path = repo_root / "data" / "catalog" / "raw_assets.jsonl"
    if jsonl_path.exists():
        return jsonl_path
    return repo_root / "data" / "catalog" / "raw_assets.json"


def load_raw_assets(repo_root: Path, override: Path | None = None) -> list[dict[str, Any]]:
    path = raw_inventory_path(repo_root, override)
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "assets" in payload:
        return list(payload["assets"])
    return []


def build_records(raw_assets: list[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    min_trust = int(config["project"]["asset_ai"]["quarantine_below_trust"])
    for raw in raw_assets:
        record = enrich_record(
            raw=raw,
            room_taxonomy=config["room_taxonomy"],
            placement_profiles=config["placement_profiles"],
            category_baselines=config["category_baselines"],
        )
        record["last_indexed_utc"] = utc_now_iso()
        record = evaluate_quarantine(record, min_trust=min_trust)
        records.append(record)
        if record.get("quarantine", {}).get("is_quarantined"):
            quarantined.append(record)
    by_category: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        category = record.get("tags", {}).get("category", "unknown")
        by_category.setdefault(category, []).append(record)
    with_similarity: list[dict[str, Any]] = []
    for record in records:
        category = record.get("tags", {}).get("category", "unknown")
        updated = dict(record)
        updated["similar_assets"] = find_similar_records(by_category.get(category, []), record, limit=3)
        with_similarity.append(updated)
    return with_similarity, quarantined


def save_sqlite(catalog_db: Path, records: list[dict[str, Any]]) -> None:
    catalog_db.parent.mkdir(parents=True, exist_ok=True)
    if catalog_db.exists() and catalog_db.stat().st_size == 0:
        catalog_db.unlink()
    conn = sqlite3.connect(catalog_db)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_catalog (
                    asset_id TEXT PRIMARY KEY,
                    asset_path TEXT NOT NULL,
                    package_path TEXT,
                    asset_name TEXT,
                    asset_class TEXT,
                    status TEXT,
                    trust_score INTEGER,
                    trust_level TEXT,
                    category TEXT,
                    function_json TEXT,
                    room_types_json TEXT,
                    styles_json TEXT,
                    mount_type TEXT,
                    scale_policy TEXT,
                    width_cm REAL,
                    depth_cm REAL,
                    height_cm REAL,
                    payload_json TEXT NOT NULL
                )
                """
            )
        except sqlite3.DatabaseError:
            conn.close()
            if catalog_db.exists():
                catalog_db.unlink()
            conn = sqlite3.connect(catalog_db)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_catalog (
                    asset_id TEXT PRIMARY KEY,
                    asset_path TEXT NOT NULL,
                    package_path TEXT,
                    asset_name TEXT,
                    asset_class TEXT,
                    status TEXT,
                    trust_score INTEGER,
                    trust_level TEXT,
                    category TEXT,
                    function_json TEXT,
                    room_types_json TEXT,
                    styles_json TEXT,
                    mount_type TEXT,
                    scale_policy TEXT,
                    width_cm REAL,
                    depth_cm REAL,
                    height_cm REAL,
                    payload_json TEXT NOT NULL
                )
                """
            )
        cur.execute("DELETE FROM asset_catalog")
        for record in records:
            tags = record.get("tags", {})
            dims = record.get("dimensions_cm", {})
            cur.execute(
                """
                INSERT OR REPLACE INTO asset_catalog (
                    asset_id, asset_path, package_path, asset_name, asset_class,
                    status, trust_score, trust_level, category,
                    function_json, room_types_json, styles_json,
                    mount_type, scale_policy, width_cm, depth_cm, height_cm, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("asset_id"),
                    record.get("asset_path"),
                    record.get("package_path"),
                    record.get("asset_name"),
                    record.get("asset_class"),
                    record.get("status"),
                    int(record.get("trust_score", 0)),
                    record.get("trust_level"),
                    tags.get("category"),
                    json.dumps(tags.get("function", [])),
                    json.dumps(tags.get("room_types", [])),
                    json.dumps(tags.get("styles", [])),
                    tags.get("mount_type"),
                    tags.get("scale_policy"),
                    float(dims.get("width", 0)),
                    float(dims.get("depth", 0)),
                    float(dims.get("height", 0)),
                    json.dumps(record),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def save_outputs(repo_root: Path, config: dict[str, Any], records: list[dict[str, Any]], quarantined: list[dict[str, Any]]) -> None:
    project_cfg = config["project"]
    catalog_jsonl = repo_root / project_cfg["paths"]["catalog_jsonl"]
    quarantine_jsonl = repo_root / project_cfg["paths"]["quarantine_jsonl"]
    catalog_db = repo_root / project_cfg["paths"]["catalog_db"]
    write_jsonl(catalog_jsonl, records)
    write_jsonl(quarantine_jsonl, quarantined)
    save_sqlite(catalog_db, records)


@app.command()
def main(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    raw_input: Path | None = typer.Option(None, help="Optional override path to raw inventory JSON or JSONL."),
) -> None:
    config = load_config(repo_root)
    raw_assets = load_raw_assets(repo_root, override=raw_input)
    records, quarantined = build_records(raw_assets, config)
    save_outputs(repo_root, config, records, quarantined)
    summary = {
        "total_raw_assets": len(raw_assets),
        "catalog_records": len(records),
        "quarantined_records": len(quarantined),
        "output_catalog": str(repo_root / config["project"]["paths"]["catalog_jsonl"]),
        "output_db": str(repo_root / config["project"]["paths"]["catalog_db"]),
    }
    typer.echo(json.dumps(summary, indent=2))


def build_full_index() -> dict[str, Any]:
    return {"indexed": 0, "status": "use_cli_or_build_records"}


if __name__ == "__main__":
    app()
