from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer


DEFAULT_PLACEABLE_CLASSES = {
    "StaticMesh",
    "Blueprint",
    "SkeletalMesh",
    "Actor",
    "StaticMeshActor",
    "BlueprintGeneratedClass",
}

app = typer.Typer(help="Scan raw asset inventory exports and return normalized candidate assets.")


def load_json(path: Path) -> Any:
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


def load_raw_inventory(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    payload = load_json(path)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("assets"), list):
        return payload["assets"]
    return []


def derive_package_path(asset_path: str) -> str:
    if "/" not in asset_path:
        return ""
    return "/".join(asset_path.split("/")[:-1])


def derive_asset_name(asset_path: str, fallback: str | None = None) -> str:
    if asset_path:
        return asset_path.split("/")[-1]
    return fallback or "UnknownAsset"


def normalize_raw_asset(raw: dict[str, Any]) -> dict[str, Any]:
    asset_path = raw.get("asset_path") or raw.get("path") or ""
    asset_name = raw.get("asset_name") or derive_asset_name(asset_path, fallback=raw.get("name"))
    package_path = raw.get("package_path") or derive_package_path(asset_path)
    asset_class = raw.get("asset_class") or raw.get("class") or raw.get("class_name") or raw.get("native_class") or "Unknown"
    tags = raw.get("tags") or {}
    metadata_tags = raw.get("metadata_tags") or {}
    preview_set = raw.get("preview_set") or {}
    return {
        "asset_path": asset_path,
        "package_path": package_path,
        "asset_name": asset_name,
        "asset_class": asset_class,
        "native_class": raw.get("native_class", asset_class),
        "tags": tags if isinstance(tags, dict) else {},
        "metadata_tags": metadata_tags if isinstance(metadata_tags, dict) else {},
        "dimensions_cm": raw.get("dimensions_cm") or {},
        "bounds_cm": raw.get("bounds_cm") or {},
        "collision_verified": raw.get("collision_verified"),
        "validator_passed": raw.get("validator_passed"),
        "pivot_suspect": raw.get("pivot_suspect", False),
        "preview_set": preview_set if isinstance(preview_set, dict) else {},
        "source_payload": raw,
    }


def is_placeable_candidate(raw: dict[str, Any], allowed_classes: set[str] | None = None) -> bool:
    allowed = allowed_classes or DEFAULT_PLACEABLE_CLASSES
    asset_class = str(raw.get("asset_class") or raw.get("class") or raw.get("class_name") or "")
    if asset_class in allowed:
        return True
    asset_path = str(raw.get("asset_path") or raw.get("path") or "").lower()
    if asset_path.startswith("/game/") and asset_class not in {"Material", "Texture", "SoundWave", "AnimationSequence"}:
        return True
    return False


def filter_candidates(raw_assets: list[dict[str, Any]], allowed_classes: set[str] | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for raw in raw_assets:
        if is_placeable_candidate(raw, allowed_classes=allowed_classes):
            results.append(normalize_raw_asset(raw))
    return results


def scan_inventory(raw_input_path: Path, allowed_classes: set[str] | None = None) -> list[dict[str, Any]]:
    return filter_candidates(load_raw_inventory(raw_input_path), allowed_classes=allowed_classes)


def registry_scan() -> list[dict[str, Any]]:
    return []


@app.command()
def main(
    raw_input: Path = typer.Option(..., help="Path to raw asset inventory JSON or JSONL."),
    output: Path | None = typer.Option(None, help="Optional output JSONL path."),
) -> None:
    candidates = scan_inventory(raw_input)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for row in candidates:
                handle.write(json.dumps(row) + "\n")
    else:
        typer.echo(json.dumps(candidates, indent=2))


if __name__ == "__main__":
    app()
