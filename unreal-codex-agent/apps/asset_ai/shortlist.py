from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from apps.integrations.prefabricator import structural_prefab_bonus
from apps.placement.placement_solver import compatible_mount_types


TRUST_RANK = {"low": 1, "medium": 2, "high": 3}
STATUS_BLOCKLIST = {"quarantined", "review_only"}
app = typer.Typer(help="Query runtime shortlists from the local asset catalog.")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def normalized_style_match(record: dict[str, Any], style: str | None) -> float:
    if not style:
        return 1.0
    styles = set(record.get("tags", {}).get("styles", []) or [])
    return 1.0 if style in styles else (0.6 if styles else 0.4)


def dimension_fit_score(record: dict[str, Any], room_dimensions: dict[str, float] | None) -> float:
    if not room_dimensions:
        return 0.8
    dims = record.get("dimensions_cm", {})
    width = float(dims.get("width", 0))
    depth = float(dims.get("depth", 0))
    room_width = float(room_dimensions.get("width", 0))
    room_depth = float(room_dimensions.get("depth", 0))
    if min(width, depth, room_width, room_depth) <= 0:
        return 0.4
    width_ratio = width / room_width
    depth_ratio = depth / room_depth
    if width_ratio > 0.9 or depth_ratio > 0.9:
        return 0.1
    if width_ratio > 0.75 or depth_ratio > 0.75:
        return 0.45
    if width_ratio < 0.08 and depth_ratio < 0.08:
        return 0.35
    return 0.95


def trust_filter(record: dict[str, Any], min_trust: str) -> bool:
    record_rank = TRUST_RANK.get(record.get("trust_level", "low"), 1)
    min_rank = TRUST_RANK.get(min_trust, 3)
    return record_rank >= min_rank


def room_match(record: dict[str, Any], room_type: str | None) -> bool:
    if not room_type:
        return True
    room_types = set(record.get("tags", {}).get("room_types", []) or [])
    return room_type in room_types


def function_match(record: dict[str, Any], function_name: str | None) -> bool:
    if not function_name:
        return True
    functions = set(record.get("tags", {}).get("function", []) or [])
    return function_name in functions


def mount_match(record: dict[str, Any], mount_type: str | None) -> bool:
    if not mount_type:
        return True
    compatible = compatible_mount_types(mount_type)
    return record.get("tags", {}).get("mount_type") in compatible


def shortlist_assets(
    catalog: list[dict[str, Any]],
    room_type: str | None = None,
    function_name: str | None = None,
    mount_type: str | None = None,
    style: str | None = None,
    min_trust: str = "high",
    room_dimensions: dict[str, float] | None = None,
    limit: int = 10,
    prefer_structural_prefabs: bool = False,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in catalog:
        if record.get("status") in STATUS_BLOCKLIST:
            continue
        if record.get("tags") and not trust_filter(record, min_trust=min_trust):
            continue
        if record.get("tags") and not room_match(record, room_type=room_type):
            continue
        if record.get("tags") and not function_match(record, function_name=function_name):
            continue
        if record.get("tags") and not mount_match(record, mount_type=mount_type):
            continue
        if "tags" not in record:
            candidates.append(record)
            continue
        style_fit = normalized_style_match(record, style)
        dim_fit = dimension_fit_score(record, room_dimensions)
        trust_norm = float(record.get("trust_score", 0)) / 100.0
        placement_rank = (
            0.30 * 1.0
            + 0.25 * dim_fit
            + 0.15 * style_fit
            + 0.10 * 1.0
            + 0.10 * trust_norm
            + 0.10 * 1.0
        )
        if prefer_structural_prefabs:
            placement_rank += structural_prefab_bonus(record, mount_type)
        enriched = dict(record)
        enriched["placement_rank"] = round(placement_rank, 4)
        candidates.append(enriched)
    candidates.sort(
        key=lambda record: (
            -float(record.get("placement_rank", 0)),
            -int(record.get("trust_score", 0)) if "trust_score" in record else 0,
            record.get("asset_id", ""),
        )
    )
    return candidates[:limit]


@app.command()
def main(
    catalog_path: Path = typer.Option(Path("./data/catalog/asset_catalog.jsonl")),
    room_type: str | None = typer.Option(None),
    function_name: str | None = typer.Option(None),
    mount_type: str | None = typer.Option(None),
    style: str | None = typer.Option(None),
    min_trust: str = typer.Option("high"),
    room_width: float = typer.Option(0.0),
    room_depth: float = typer.Option(0.0),
    limit: int = typer.Option(10),
) -> None:
    catalog = load_jsonl(catalog_path)
    room_dimensions = {"width": room_width, "depth": room_depth} if room_width > 0 and room_depth > 0 else None
    results = shortlist_assets(
        catalog=catalog,
        room_type=room_type,
        function_name=function_name,
        mount_type=mount_type,
        style=style,
        min_trust=min_trust,
        room_dimensions=room_dimensions,
        limit=limit,
    )
    typer.echo(json.dumps(results, indent=2))


if __name__ == "__main__":
    app()
