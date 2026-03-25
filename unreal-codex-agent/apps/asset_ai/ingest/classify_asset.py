from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.asset_ai.ingest.metadata_io import (
    apply_writeback_metadata_to_record,
    extract_existing_metadata_tags,
    merge_inferred_tags_with_existing,
)
from apps.asset_ai.ingest.measure_asset import measure_record
from apps.asset_ai.ingest.preview_capture import build_preview_set, preview_quality_flags
from apps.asset_ai.trust_score import (
    classification_score_from_tags,
    collision_score_from_raw,
    compute_trust_score,
    infer_tags,
    metadata_score_from_tags,
    naming_score_from_tokens,
    placement_score_from_tags,
    trust_band,
)


def classify_raw_asset(
    raw: dict[str, Any],
    room_taxonomy: dict[str, Any],
    placement_profiles: dict[str, Any],
    category_baselines: dict[str, Any],
    preview_root: Path,
) -> dict[str, Any]:
    asset_path = raw.get("asset_path", "")
    asset_name = raw.get("asset_name") or asset_path.split("/")[-1]
    package_path = raw.get("package_path") or "/".join(asset_path.split("/")[:-1])
    asset_class = raw.get("asset_class", "Unknown")
    inferred_tags = infer_tags(raw, room_taxonomy)
    existing_metadata = extract_existing_metadata_tags(raw)
    tags = merge_inferred_tags_with_existing(inferred_tags, existing_metadata)
    measured = measure_record(raw, tags, category_baselines)
    dimensions_cm = measured["dimensions_cm"]
    asset_id = raw.get("asset_id") or asset_name.lower().replace("/", "_")
    preview_set = build_preview_set(raw=raw, asset_id=asset_id, preview_root=preview_root)
    preview_flags = preview_quality_flags(preview_set)
    scores = {
        "metadata_score": metadata_score_from_tags(tags),
        "dimension_score": measured["dimension_score"],
        "classification_score": classification_score_from_tags(tags),
        "naming_score": naming_score_from_tokens(asset_name),
        "collision_score": collision_score_from_raw(raw),
        "placement_score": placement_score_from_tags(tags, dimensions_cm),
        "validator_score": 100 if raw.get("validator_passed") is True else 35 if raw.get("validator_passed") is False else 80,
    }
    trust_score = compute_trust_score(scores)
    trust_level, status = trust_band(trust_score)
    record = {
        "asset_id": asset_id,
        "asset_path": asset_path,
        "package_path": package_path,
        "asset_name": asset_name,
        "asset_class": asset_class,
        "status": status,
        "trust_score": trust_score,
        "trust_level": trust_level,
        "tags": tags,
        "dimensions_cm": measured["dimensions_cm"],
        "bounds_cm": measured["bounds_cm"],
        "scale_limits": measured["scale_limits"],
        "placement_rules": raw.get("placement_rules") or {},
        "quality_flags": {
            "metadata_complete": scores["metadata_score"] == 100,
            "bounds_verified": min(dimensions_cm.values()) > 0,
            "collision_verified": raw.get("collision_verified"),
            "preview_verified": preview_flags["preview_verified"],
            "pivot_suspect": bool(raw.get("pivot_suspect", False)),
            "scale_suspect": scores["dimension_score"] < 60,
        },
        "scores": scores,
        "preview_set": preview_set,
        "quarantine": {"is_quarantined": status == "quarantined", "reasons": []},
        "baseline_key": measured["baseline_key"],
        "last_indexed_utc": raw.get("last_indexed_utc"),
    }
    return apply_writeback_metadata_to_record(record)


def classify_asset(asset_id: str) -> dict[str, Any]:
    return {"asset_id": asset_id, "category": "unknown"}
