from __future__ import annotations

import re
from typing import Any

LANDSCAPE_KEYWORDS = {"landscape", "landscapestreamingproxy", "terrain"}
UPPER_SLAB_KEYWORDS = {"upper", "slab", "story", "storey", "mezzanine", "deck"}
BALCONY_KEYWORDS = {"balcony", "terrace", "porch"}
ROOF_SURFACE_KEYWORDS = {"roof", "rooftop", "eave", "shingle", "gable"}
WALL_SURFACE_KEYWORDS = {"wall", "facade", "panel"}
CEILING_SURFACE_KEYWORDS = {"ceiling"}
SUPPORT_SURFACE_KEYWORDS = {
    "ground",
    "land",
    "landscape",
    "terrain",
    "grid",
    "gridplane",
    "asphalt",
    "floor",
    "foundation",
    "platform",
    "plaza",
    "road",
    "path",
    "sidewalk",
}

SUPPORT_FAMILIES = {
    "terrain": {"landscape"},
    "surface": {"support_surface", "upper_slab", "balcony"},
    "roof": {"roof_surface"},
    "wall": {"wall_surface"},
    "ceiling": {"ceiling_surface"},
}

MOUNT_SUPPORT_COMPATIBILITY = {
    "floor": {"landscape", "support_surface", "upper_slab", "balcony"},
    "surface": {"landscape", "support_surface", "upper_slab", "balcony"},
    "exterior_ground": {"landscape"},
    "wall": {"wall_surface"},
    "opening": {"wall_surface"},
    "corner": {"wall_surface", "support_surface", "upper_slab", "balcony"},
    "roof": {"roof_surface"},
    "ceiling": {"ceiling_surface"},
}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_triplet(value: Any, default: list[float] | None = None) -> list[float]:
    fallback = list(default or [0.0, 0.0, 0.0])
    if isinstance(value, dict):
        return [
            safe_float(value.get("x"), fallback[0]),
            safe_float(value.get("y"), fallback[1]),
            safe_float(value.get("z"), fallback[2]),
        ]
    if isinstance(value, (list, tuple)):
        padded = list(value[:3]) + fallback[len(value[:3]) :]
        return [
            safe_float(padded[0], fallback[0]),
            safe_float(padded[1], fallback[1]),
            safe_float(padded[2], fallback[2]),
        ]
    return fallback


def actor_text(actor: dict[str, Any]) -> str:
    return " ".join(
        str(actor.get(key) or "")
        for key in ("label", "asset_path", "actor_name", "class_name", "category", "room_type")
    ).lower()


def actor_tokens(actor: dict[str, Any]) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", actor_text(actor)) if token}


def _matches_keyword(token: str, keyword: str) -> bool:
    normalized_token = str(token or "").strip().lower()
    normalized_keyword = str(keyword or "").strip().lower()
    if not normalized_token or not normalized_keyword:
        return False
    if normalized_token == normalized_keyword:
        return True
    if normalized_keyword in {"ground", "land", "floor", "grid", "wall", "roof", "ceiling"}:
        return normalized_token.startswith(normalized_keyword) or normalized_token.endswith(normalized_keyword)
    return normalized_token.startswith(normalized_keyword) or normalized_keyword in normalized_token


def _keyword_matches_actor(actor: dict[str, Any], keywords: set[str]) -> bool:
    tokens = actor_tokens(actor)
    return any(_matches_keyword(token, keyword) for token in tokens for keyword in keywords)


def actor_origin_and_extent(actor: dict[str, Any]) -> tuple[list[float], list[float]]:
    bounds = actor.get("bounds_cm", {}) if isinstance(actor.get("bounds_cm"), dict) else {}
    origin = safe_triplet(bounds.get("origin"), safe_triplet(actor.get("location"), [0.0, 0.0, 0.0]))
    extent = safe_triplet(bounds.get("box_extent"), [0.0, 0.0, 0.0])
    if extent == [0.0, 0.0, 0.0]:
        dims = actor.get("dimensions_cm", {}) if isinstance(actor.get("dimensions_cm"), dict) else {}
        if dims:
            extent = [
                safe_float(dims.get("width"), 0.0) / 2.0,
                safe_float(dims.get("depth"), 0.0) / 2.0,
                safe_float(dims.get("height"), 0.0) / 2.0,
            ]
    return origin, extent


def support_kind_for_actor(actor: dict[str, Any]) -> str | None:
    explicit = str(actor.get("support_surface_kind") or "").strip().lower()
    if explicit:
        return explicit
    if _keyword_matches_actor(actor, LANDSCAPE_KEYWORDS):
        return "landscape"
    if _keyword_matches_actor(actor, BALCONY_KEYWORDS):
        return "balcony"
    if _keyword_matches_actor(actor, ROOF_SURFACE_KEYWORDS):
        return "roof_surface"
    if _keyword_matches_actor(actor, CEILING_SURFACE_KEYWORDS):
        return "ceiling_surface"
    if _keyword_matches_actor(actor, WALL_SURFACE_KEYWORDS):
        return "wall_surface"
    if _keyword_matches_actor(actor, UPPER_SLAB_KEYWORDS):
        return "upper_slab"
    if _keyword_matches_actor(actor, SUPPORT_SURFACE_KEYWORDS):
        return "support_surface"
    return None


def support_level_for_actor(actor: dict[str, Any]) -> int:
    explicit = actor.get("support_level")
    if explicit is not None:
        try:
            return int(explicit)
        except (TypeError, ValueError):
            pass
    origin, extent = actor_origin_and_extent(actor)
    top_z = float(origin[2]) + float(extent[2])
    kind = support_kind_for_actor(actor) or ""
    if kind == "landscape":
        return 0
    if top_z >= 300.0:
        return max(1, int(round(top_z / 300.0)))
    if kind in {"upper_slab", "balcony", "roof_surface", "ceiling_surface"}:
        return 1
    return 0


def support_anchor_for_actor(actor: dict[str, Any]) -> list[float]:
    origin, extent = actor_origin_and_extent(actor)
    return [
        round(origin[0], 3),
        round(origin[1], 3),
        round(origin[2] + extent[2], 3),
    ]


def support_family_for_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    for family, kinds in SUPPORT_FAMILIES.items():
        if normalized in kinds:
            return family
    return normalized or "unknown"


def compatible_support_kinds(mount_type: str) -> set[str]:
    normalized = str(mount_type or "").strip().lower()
    return set(MOUNT_SUPPORT_COMPATIBILITY.get(normalized, {"support_surface"}))


def is_support_kind_compatible(mount_type: str, support_kind: str) -> bool:
    normalized_mount_type = str(mount_type or "").strip().lower()
    normalized_support_kind = str(support_kind or "").strip().lower()
    if not normalized_mount_type or not normalized_support_kind:
        return False
    allowed = compatible_support_kinds(normalized_mount_type)
    if normalized_support_kind in allowed:
        return True
    allowed_families = {support_family_for_kind(kind) for kind in allowed}
    return support_family_for_kind(normalized_support_kind) in allowed_families


def support_kind_priority(mount_type: str, support_kind: str) -> int:
    normalized_mount_type = str(mount_type or "").strip().lower()
    normalized_support_kind = str(support_kind or "").strip().lower()
    if normalized_mount_type == "exterior_ground":
        return 0 if normalized_support_kind == "landscape" else 2
    if normalized_mount_type in {"floor", "surface"}:
        if normalized_support_kind in {"support_surface", "upper_slab", "balcony"}:
            return 0
        if normalized_support_kind == "landscape":
            return 1
        return 2
    if normalized_mount_type in {"wall", "opening"}:
        return 0 if normalized_support_kind == "wall_surface" else 2
    if normalized_mount_type == "corner":
        if normalized_support_kind == "wall_surface":
            return 0
        if normalized_support_kind in {"support_surface", "upper_slab", "balcony"}:
            return 1
        return 2
    if normalized_mount_type == "roof":
        return 0 if normalized_support_kind == "roof_surface" else 2
    if normalized_mount_type == "ceiling":
        return 0 if normalized_support_kind == "ceiling_surface" else 2
    return 1
