from __future__ import annotations

from typing import Any


REQUIRED_METADATA_KEYS = {"category", "function", "room_types", "mount_type", "scale_policy"}


def evaluate_quarantine(record: dict[str, Any], min_trust: int = 50) -> dict[str, Any]:
    reasons: list[str] = []
    if record.get("trust_score", 0) < min_trust:
        reasons.append("trust_score_below_threshold")
    dimensions = record.get("dimensions_cm", {})
    if not dimensions or min(float(dimensions.get("width", 0)), float(dimensions.get("depth", 0)), float(dimensions.get("height", 0))) <= 0:
        reasons.append("missing_or_invalid_dimensions")
    tags = record.get("tags", {})
    missing = [key for key in REQUIRED_METADATA_KEYS if not tags.get(key)]
    if missing:
        reasons.append(f"missing_required_tags:{','.join(sorted(missing))}")
    quality_flags = record.get("quality_flags", {})
    if quality_flags.get("pivot_suspect"):
        reasons.append("pivot_suspect")
    if quality_flags.get("scale_suspect"):
        reasons.append("scale_suspect")
    if record.get("scores", {}).get("validator_score", 100) < 50:
        reasons.append("validator_score_low")
    is_quarantined = len(reasons) > 0 and record.get("status") == "quarantined"
    if reasons and record.get("trust_score", 0) < min_trust:
        is_quarantined = True
    updated = dict(record)
    updated["quarantine"] = {"is_quarantined": is_quarantined, "reasons": reasons}
    if is_quarantined:
        updated["status"] = "quarantined"
        updated["trust_level"] = "low"
    return updated


def is_quarantined(asset: dict[str, Any]) -> bool:
    quarantine = asset.get("quarantine")
    if isinstance(quarantine, dict):
        return bool(quarantine.get("is_quarantined", False))
    return bool(asset.get("quarantined", False))
