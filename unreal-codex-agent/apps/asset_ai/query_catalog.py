from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import typer

from apps.placement.placement_solver import compatible_mount_types

app = typer.Typer(help="Query the local asset catalog.")


def query_rows(
    catalog_db: Path,
    room_type: str | None = None,
    function_name: str | None = None,
    style: str | None = None,
    mount_type: str | None = None,
    min_trust_score: int = 0,
    status: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    if not catalog_db.exists():
        return []
    try:
        conn = sqlite3.connect(catalog_db)
    except sqlite3.DatabaseError:
        return []
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT payload_json
                FROM asset_catalog
                WHERE trust_score >= ?
                ORDER BY trust_score DESC, asset_id ASC
                """,
                (min_trust_score,),
            )
            rows: list[dict[str, Any]] = []
            for row in cur.fetchall():
                try:
                    payload = json.loads(row["payload_json"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
        except sqlite3.DatabaseError:
            return []
    finally:
        conn.close()
    filtered: list[dict[str, Any]] = []
    compatible_mounts = compatible_mount_types(mount_type) if mount_type else set()
    for row in rows:
        tags = row.get("tags", {})
        if status and row.get("status") != status:
            continue
        if room_type and room_type not in (tags.get("room_types") or []):
            continue
        if function_name and function_name not in (tags.get("function") or []):
            continue
        if style and style not in (tags.get("styles") or []):
            continue
        if mount_type and tags.get("mount_type") not in compatible_mounts:
            continue
        filtered.append(row)
    return filtered[:limit]


@app.command()
def main(
    catalog_db: Path = typer.Option(Path("./data/catalog/asset_catalog.sqlite")),
    room_type: str | None = typer.Option(None),
    function_name: str | None = typer.Option(None),
    style: str | None = typer.Option(None),
    mount_type: str | None = typer.Option(None),
    min_trust_score: int = typer.Option(0),
    status: str | None = typer.Option(None),
    limit: int = typer.Option(25),
) -> None:
    typer.echo(
        json.dumps(
            query_rows(
                catalog_db=catalog_db,
                room_type=room_type,
                function_name=function_name,
                style=style,
                mount_type=mount_type,
                min_trust_score=min_trust_score,
                status=status,
                limit=limit,
            ),
            indent=2,
        )
    )


def query_catalog(query: str) -> list[dict[str, Any]]:
    query_text = (query or "").strip().lower()
    if not query_text:
        return []
    catalog_db = Path("./data/catalog/asset_catalog.sqlite")
    rows = query_rows(catalog_db=catalog_db, limit=200)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        haystack_parts = [
            row.get("asset_id", ""),
            row.get("asset_name", ""),
            row.get("asset_path", ""),
            row.get("trust_level", ""),
            row.get("status", ""),
        ]
        tags = row.get("tags", {})
        for key in ("category", "mount_type", "scale_policy"):
            haystack_parts.append(tags.get(key, ""))
        for key in ("prefab_family",):
            haystack_parts.append(tags.get(key, ""))
        for key in ("function", "room_types", "styles", "placement_behavior"):
            values = tags.get(key, []) or []
            if isinstance(values, str):
                values = [values]
            haystack_parts.extend(str(value) for value in values)
        if tags.get("is_prefab") is True:
            haystack_parts.append("prefab")
        haystack = " ".join(str(part) for part in haystack_parts if part).lower()
        if query_text not in haystack:
            continue
        score = haystack.count(query_text) + int(row.get("trust_score", 0))
        ranked.append((score, row))
    ranked.sort(key=lambda item: (-item[0], item[1].get("asset_id", "")))
    return [row for _, row in ranked[:25]]


if __name__ == "__main__":
    app()
