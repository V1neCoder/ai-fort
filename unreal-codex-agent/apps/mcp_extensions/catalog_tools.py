from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from apps.asset_ai.build_full_index import (
    build_records,
    load_config as load_catalog_config,
    load_raw_assets,
    save_outputs,
)
from apps.integrations.prefabricator import should_prefer_prefabs
from apps.asset_ai.ingest.scale_policy import infer_scale_policy, resolve_scale_limits
from apps.asset_ai.query_catalog import query_catalog, query_rows
from apps.asset_ai.quarantine import evaluate_quarantine
from apps.asset_ai.shortlist import shortlist_assets
from apps.asset_ai.trust_score import enrich_record
from apps.asset_ai.update_single_asset import read_catalog_jsonl, replace_record

app = typer.Typer(help="Catalog helper tools for local MCP-style workflows.")


def _load_project(repo_root: Path) -> dict[str, Any]:
    project_path = repo_root / "config" / "project.json"
    if not project_path.exists():
        return {"paths": {}}
    try:
        payload = json.loads(project_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"paths": {}}
    return payload if isinstance(payload, dict) else {"paths": {}}


def _project_catalog_db(repo_root: Path) -> Path:
    project = _load_project(repo_root)
    return repo_root / project.get("paths", {}).get("catalog_db", "data/catalog/asset_catalog.sqlite")


def _project_catalog_jsonl(repo_root: Path) -> Path:
    project = _load_project(repo_root)
    return repo_root / project.get("paths", {}).get("catalog_jsonl", "data/catalog/asset_catalog.jsonl")


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _all_catalog_records(repo_root: Path) -> list[dict[str, Any]]:
    catalog_jsonl = _project_catalog_jsonl(repo_root)
    if catalog_jsonl.exists():
        try:
            return read_catalog_jsonl(catalog_jsonl)
        except Exception:
            return []
    try:
        return search_catalog(repo_root=repo_root, min_trust_score=0, limit=100000)
    except Exception:
        return []


def _find_record(
    *,
    repo_root: Path,
    asset_path: str | None = None,
    asset_id: str | None = None,
) -> dict[str, Any] | None:
    for row in _all_catalog_records(repo_root):
        if asset_path and row.get("asset_path") == asset_path:
            return row
        if asset_id and row.get("asset_id") == asset_id:
            return row
    return None


def _require_record(repo_root: Path, asset_path: str | None, asset_id: str | None) -> dict[str, Any]:
    record = get_asset(repo_root=repo_root, asset_path=asset_path, asset_id=asset_id)
    if record is None:
        identifier = asset_path or asset_id or "<unknown>"
        raise typer.BadParameter(f"Asset record not found: {identifier}")
    return record


def _baseline_for(category_baselines: dict[str, Any], category: str, function_names: list[str]) -> tuple[str | None, dict[str, Any] | None]:
    baselines = category_baselines.get("baselines", {})
    functions = set(function_names)
    for baseline_key, baseline in baselines.items():
        baseline_category = str(baseline.get("category", ""))
        baseline_function = str(baseline.get("function", ""))
        if baseline_category == category and (not baseline_function or baseline_function in functions):
            return baseline_key, baseline
    return None, None


def search_catalog(
    *,
    repo_root: Path,
    room_type: str | None = None,
    function_name: str | None = None,
    style: str | None = None,
    mount_type: str | None = None,
    min_trust_score: int = 0,
    status: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    return query_rows(
        catalog_db=_project_catalog_db(repo_root),
        room_type=room_type,
        function_name=function_name,
        style=style,
        mount_type=mount_type,
        min_trust_score=min_trust_score,
        status=status,
        limit=limit,
    )


def get_asset(
    *,
    repo_root: Path,
    asset_path: str | None = None,
    asset_id: str | None = None,
) -> dict[str, Any] | None:
    if not asset_path and not asset_id:
        return None
    return _find_record(repo_root=repo_root, asset_path=asset_path, asset_id=asset_id)


def _save_catalog_records(repo_root: Path, config: dict[str, Any], records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    quarantined = [row for row in records if row.get("quarantine", {}).get("is_quarantined")]
    save_outputs(repo_root, config, records, quarantined)
    return records, quarantined


def _update_one_asset(repo_root: Path, asset_path: str, raw_input: Path | None = None) -> dict[str, Any]:
    config = load_catalog_config(repo_root)
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
    record["last_indexed_utc"] = _utc_now_iso()
    record = evaluate_quarantine(record, min_trust=int(config["project"]["asset_ai"]["quarantine_below_trust"]))

    existing = _all_catalog_records(repo_root)
    updated_records = replace_record(existing, record)
    _, quarantined = _save_catalog_records(repo_root, config, updated_records)
    return {
        "updated_asset_path": asset_path,
        "new_status": record.get("status"),
        "trust_score": record.get("trust_score"),
        "quarantined_records": len(quarantined),
    }


def _quarantine_record(record: dict[str, Any], reason: str) -> dict[str, Any]:
    updated = dict(record)
    quarantine = dict(updated.get("quarantine") or {})
    reasons = list(quarantine.get("reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    quarantine["is_quarantined"] = True
    quarantine["reasons"] = reasons
    updated["quarantine"] = quarantine
    updated["status"] = "quarantined"
    updated["trust_level"] = "low"
    quality_flags = dict(updated.get("quality_flags") or {})
    quality_flags["manual_quarantine"] = True
    updated["quality_flags"] = quality_flags
    updated["last_indexed_utc"] = _utc_now_iso()
    return updated


@app.command("build-index")
def build_index_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    raw_input: Path | None = typer.Option(None, help="Optional override path to raw inventory JSON or JSONL."),
) -> None:
    config = load_catalog_config(repo_root)
    raw_assets = load_raw_assets(repo_root, override=raw_input)
    records, quarantined = build_records(raw_assets, config)
    save_outputs(repo_root, config, records, quarantined)
    typer.echo(
        json.dumps(
            {
                "total_raw_assets": len(raw_assets),
                "catalog_records": len(records),
                "quarantined_records": len(quarantined),
                "catalog_jsonl": str(_project_catalog_jsonl(repo_root)),
                "catalog_db": str(_project_catalog_db(repo_root)),
            },
            indent=2,
        )
    )


@app.command("update-asset")
def update_asset_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    asset_path: str = typer.Option(..., help="Exact asset path to update from raw inventory."),
    raw_input: Path | None = typer.Option(None, help="Optional override path to raw inventory JSON or JSONL."),
) -> None:
    typer.echo(json.dumps(_update_one_asset(repo_root, asset_path, raw_input), indent=2))


@app.command("search")
def search_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    query: str | None = typer.Option(None, help="Free-text query against local catalog metadata."),
    room_type: str | None = typer.Option(None),
    function_name: str | None = typer.Option(None),
    style: str | None = typer.Option(None),
    mount_type: str | None = typer.Option(None),
    min_trust_score: int = typer.Option(0),
    status: str | None = typer.Option(None),
    limit: int = typer.Option(25),
) -> None:
    if query:
        previous_cwd = Path.cwd()
        try:
            os.chdir(repo_root)
            results = query_catalog(query=query)
        finally:
            os.chdir(previous_cwd)
        typer.echo(json.dumps(results, indent=2))
        return
    typer.echo(
        json.dumps(
            search_catalog(
                repo_root=repo_root,
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


@app.command("get-asset")
def get_asset_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    asset_path: str | None = typer.Option(None, help="Exact asset path to fetch."),
    asset_id: str | None = typer.Option(None, help="Exact asset id to fetch."),
) -> None:
    if not asset_path and not asset_id:
        raise typer.BadParameter("Provide --asset-path or --asset-id.")
    typer.echo(json.dumps(_require_record(repo_root, asset_path, asset_id), indent=2))


@app.command("shortlist")
def shortlist_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    room_type: str | None = typer.Option(None),
    function_name: str | None = typer.Option(None),
    style: str | None = typer.Option(None),
    mount_type: str | None = typer.Option(None),
    min_trust: str = typer.Option("high"),
    room_width: float = typer.Option(0.0),
    room_depth: float = typer.Option(0.0),
    limit: int = typer.Option(10),
) -> None:
    catalog = _all_catalog_records(repo_root)
    project = _load_project(repo_root)
    room_dimensions = {"width": room_width, "depth": room_depth} if room_width > 0 and room_depth > 0 else None
    typer.echo(
        json.dumps(
            shortlist_assets(
                catalog=catalog,
                room_type=room_type,
                function_name=function_name,
                mount_type=mount_type,
                style=style,
                min_trust=min_trust,
                room_dimensions=room_dimensions,
                limit=limit,
                prefer_structural_prefabs=should_prefer_prefabs(project, mount_type),
            ),
            indent=2,
        )
    )


@app.command("mark-quarantine")
def mark_quarantine_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    asset_path: str | None = typer.Option(None, help="Exact asset path to mark quarantined."),
    asset_id: str | None = typer.Option(None, help="Exact asset id to mark quarantined."),
    reason: str = typer.Option("manual_quarantine", help="Reason to append to the quarantine record."),
) -> None:
    if not asset_path and not asset_id:
        raise typer.BadParameter("Provide --asset-path or --asset-id.")

    config = load_catalog_config(repo_root)
    target_record = _require_record(repo_root, asset_path, asset_id)
    updated_record = _quarantine_record(target_record, reason)
    updated_records = replace_record(_all_catalog_records(repo_root), updated_record)
    _, quarantined = _save_catalog_records(repo_root, config, updated_records)
    typer.echo(
        json.dumps(
            {
                "asset_id": updated_record.get("asset_id"),
                "asset_path": updated_record.get("asset_path"),
                "status": updated_record.get("status"),
                "quarantine": updated_record.get("quarantine"),
                "quarantined_records": len(quarantined),
            },
            indent=2,
        )
    )


@app.command("safe-scale")
def safe_scale_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    asset_path: str | None = typer.Option(None, help="Exact asset path to inspect."),
    asset_id: str | None = typer.Option(None, help="Exact asset id to inspect."),
    category: str | None = typer.Option(None, help="Fallback category when no existing asset record is provided."),
    function_name: str | None = typer.Option(None, help="Fallback function name when no existing asset record is provided."),
) -> None:
    config = load_catalog_config(repo_root)
    record = get_asset(repo_root=repo_root, asset_path=asset_path, asset_id=asset_id)
    if record is not None:
        tags = record.get("tags", {})
        scale_policy = str(tags.get("scale_policy") or "medium")
        function_names = list(tags.get("function") or [])
        baseline_key = record.get("baseline_key")
        baselines = config["category_baselines"].get("baselines", {})
        baseline = baselines.get(baseline_key) if baseline_key else None
        limits = dict(record.get("scale_limits") or resolve_scale_limits(scale_policy, baseline))
        typer.echo(
            json.dumps(
                {
                    "asset_id": record.get("asset_id"),
                    "asset_path": record.get("asset_path"),
                    "category": tags.get("category"),
                    "function_names": function_names,
                    "scale_policy": scale_policy,
                    "scale_limits": limits,
                    "baseline_key": baseline_key,
                },
                indent=2,
            )
        )
        return

    if not category:
        raise typer.BadParameter("Provide an existing asset via --asset-path/--asset-id or a --category.")

    function_names = [function_name] if function_name else []
    baseline_key, baseline = _baseline_for(config["category_baselines"], category, function_names)
    scale_policy = infer_scale_policy(category, function_names)
    typer.echo(
        json.dumps(
            {
                "asset_id": None,
                "asset_path": None,
                "category": category,
                "function_names": function_names,
                "scale_policy": scale_policy,
                "scale_limits": resolve_scale_limits(scale_policy, baseline),
                "baseline_key": baseline_key,
            },
            indent=2,
        )
    )


def catalog_tools() -> list[str]:
    return [
        "build-index",
        "update-asset",
        "search",
        "get-asset",
        "shortlist",
        "mark-quarantine",
        "safe-scale",
    ]


if __name__ == "__main__":
    app()
