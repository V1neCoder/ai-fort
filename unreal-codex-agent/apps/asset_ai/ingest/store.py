from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def save_catalog_sqlite(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size == 0:
        path.unlink()
    conn = sqlite3.connect(path)
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
            if path.exists():
                path.unlink()
            conn = sqlite3.connect(path)
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


def store_asset_record(record: dict) -> dict:
    return record
