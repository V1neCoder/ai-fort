from __future__ import annotations

from math import sqrt
from typing import Any


def _set_from_asset(record: dict[str, Any]) -> set[str]:
    tags = record.get("tags", {})
    values: set[str] = set()
    values.add(tags.get("category", ""))
    values.add(tags.get("mount_type", ""))
    values.add(tags.get("scale_policy", ""))
    for field in ("function", "room_types", "styles", "placement_behavior"):
        raw = tags.get(field, [])
        if isinstance(raw, str):
            raw = [raw]
        values.update(str(item) for item in raw if item)
    return {value for value in values if value}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _dimension_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    da = a.get("dimensions_cm", {})
    db = b.get("dimensions_cm", {})
    aw, ad, ah = float(da.get("width", 0)), float(da.get("depth", 0)), float(da.get("height", 0))
    bw, bd, bh = float(db.get("width", 0)), float(db.get("depth", 0)), float(db.get("height", 0))
    if min(aw, ad, ah, bw, bd, bh) <= 0:
        return 0.0
    dist = sqrt(((aw - bw) / max(aw, bw)) ** 2 + ((ad - bd) / max(ad, bd)) ** 2 + ((ah - bh) / max(ah, bh)) ** 2)
    return max(0.0, 1.0 - dist)


def similarity_score(source: dict[str, Any], candidate: dict[str, Any]) -> float:
    tag_score = _jaccard(_set_from_asset(source), _set_from_asset(candidate))
    dim_score = _dimension_similarity(source, candidate)
    trust_score = min(float(candidate.get("trust_score", 0)) / 100.0, 1.0)
    return round((tag_score * 0.55) + (dim_score * 0.30) + (trust_score * 0.15), 4)


def find_similar_records(records: list[dict[str, Any]], source: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    source_id = source.get("asset_id")
    for record in records:
        if record.get("asset_id") == source_id:
            continue
        ranked.append((similarity_score(source, record), record))
    ranked.sort(key=lambda item: (-item[0], item[1].get("asset_id", "")))
    return [
        {
            "asset_id": record.get("asset_id"),
            "asset_path": record.get("asset_path"),
            "similarity_score": score,
        }
        for score, record in ranked[:limit]
    ]


def similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    return similarity_score(a, b)
