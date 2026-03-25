from __future__ import annotations

from copy import deepcopy
from typing import Any


ASSET_AI_METADATA_KEYS = [
    "asset_ai.category",
    "asset_ai.function",
    "asset_ai.room_types",
    "asset_ai.mount_type",
    "asset_ai.scale_policy",
    "asset_ai.styles",
    "asset_ai.shell_sensitive",
    "asset_ai.clearance_profile",
    "asset_ai.trust_level",
    "asset_ai.trust_score",
]


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _dedupe_keep_order(values: list[Any]) -> list[Any]:
    seen = set()
    out: list[Any] = []
    for value in values:
        key = str(value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def extract_existing_metadata_tags(raw: dict[str, Any]) -> dict[str, Any]:
    metadata = deepcopy(raw.get("metadata_tags") or {})
    tags = raw.get("tags") or {}
    if not metadata and isinstance(tags, dict):
        for key in ASSET_AI_METADATA_KEYS:
            if key in tags:
                metadata[key] = tags[key]
    return metadata


def merge_inferred_tags_with_existing(inferred_tags: dict[str, Any], existing_metadata: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(inferred_tags)
    if existing_metadata.get("asset_ai.category") and not merged.get("category"):
        merged["category"] = existing_metadata["asset_ai.category"]
    if existing_metadata.get("asset_ai.function"):
        merged["function"] = _dedupe_keep_order(_ensure_list(existing_metadata["asset_ai.function"]) + _ensure_list(merged.get("function")))
    if existing_metadata.get("asset_ai.room_types"):
        merged["room_types"] = _dedupe_keep_order(_ensure_list(existing_metadata["asset_ai.room_types"]) + _ensure_list(merged.get("room_types")))
    if existing_metadata.get("asset_ai.mount_type") and not merged.get("mount_type"):
        merged["mount_type"] = existing_metadata["asset_ai.mount_type"]
    if existing_metadata.get("asset_ai.scale_policy") and not merged.get("scale_policy"):
        merged["scale_policy"] = existing_metadata["asset_ai.scale_policy"]
    if existing_metadata.get("asset_ai.styles"):
        merged["styles"] = _dedupe_keep_order(_ensure_list(existing_metadata["asset_ai.styles"]) + _ensure_list(merged.get("styles")))
    if "asset_ai.shell_sensitive" in existing_metadata:
        merged["shell_sensitive"] = bool(existing_metadata["asset_ai.shell_sensitive"])
    if existing_metadata.get("asset_ai.clearance_profile") and not merged.get("clearance_profile"):
        merged["clearance_profile"] = existing_metadata["asset_ai.clearance_profile"]
    return merged


def build_writeback_metadata(record: dict[str, Any]) -> dict[str, Any]:
    tags = record.get("tags", {})
    return {
        "asset_ai.category": tags.get("category"),
        "asset_ai.function": tags.get("function", []),
        "asset_ai.room_types": tags.get("room_types", []),
        "asset_ai.mount_type": tags.get("mount_type"),
        "asset_ai.scale_policy": tags.get("scale_policy"),
        "asset_ai.styles": tags.get("styles", []),
        "asset_ai.shell_sensitive": bool(tags.get("shell_sensitive", False)),
        "asset_ai.clearance_profile": tags.get("clearance_profile"),
        "asset_ai.trust_level": record.get("trust_level"),
        "asset_ai.trust_score": record.get("trust_score"),
    }


def apply_writeback_metadata_to_record(record: dict[str, Any]) -> dict[str, Any]:
    updated = dict(record)
    updated["writeback_metadata"] = build_writeback_metadata(record)
    return updated


def load_metadata(asset_id: str) -> dict[str, Any]:
    return {"asset_id": asset_id}
