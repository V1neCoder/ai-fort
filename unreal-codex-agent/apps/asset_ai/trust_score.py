from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from apps.integrations.prefabricator import PREFAB_PREFIXES


GENERIC_NAME_TOKENS = {
    "sm",
    "bp",
    "mesh",
    "prop",
    "asset",
    "final",
    "new",
    "temp",
    "test",
    "geo",
    "model",
    "obj",
    "static",
}

CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "furniture": {"sofa", "chair", "bed", "desk", "table", "stool", "bench", "dresser", "cabinet", "nightstand"},
    "architecture": {"wall", "floor", "ceiling", "trim", "molding", "stair", "column", "beam", "panel"},
    "decor": {"rug", "plant", "vase", "frame", "painting", "art", "clock", "curtain", "pillow", "blanket"},
    "lighting": {"lamp", "light", "sconce", "pendant", "chandelier", "lantern"},
    "plumbing": {"sink", "toilet", "bathtub", "shower", "faucet"},
    "appliance": {"fridge", "refrigerator", "oven", "microwave", "dishwasher", "washer", "dryer", "tv", "monitor"},
    "structural": {"railing", "support", "foundation", "roof", "truss", "frame"},
    "opening": {"door", "window", "gate"},
    "surface": {"counter", "countertop", "shelf", "worktop", "island", "coffee_table", "tabletop"},
    "foliage": {"tree", "bush", "grass", "flower", "shrub"},
}

FUNCTION_KEYWORDS: dict[str, set[str]] = {
    "seating": {"sofa", "chair", "bench", "stool", "seat"},
    "sleeping": {"bed", "mattress", "bunk"},
    "storage": {"cabinet", "drawer", "dresser", "shelf", "closet", "locker", "wardrobe", "nightstand"},
    "cooking": {"oven", "stove", "cooktop", "range", "fridge", "refrigerator", "counter", "island"},
    "bathing": {"sink", "toilet", "bathtub", "shower", "faucet"},
    "lighting": {"lamp", "light", "sconce", "pendant", "chandelier", "lantern"},
    "divider": {"wall", "partition", "panel", "screen"},
    "access": {"door", "window", "stairs", "stair", "gate", "railing"},
    "surface": {"table", "counter", "desk", "shelf", "island"},
    "decoration": {"rug", "plant", "vase", "painting", "art", "curtain", "pillow"},
    "appliance": {"tv", "monitor", "microwave", "washer", "dryer", "dishwasher"},
    "structure": {"roof", "beam", "column", "frame", "foundation"},
}

MOUNT_KEYWORDS: dict[str, set[str]] = {
    "floor": {"sofa", "chair", "bed", "table", "rug", "cabinet", "desk", "bench", "dresser", "plant"},
    "wall": {"sconce", "shelf", "frame", "painting", "mirror", "cabinet", "window_trim"},
    "ceiling": {"pendant", "chandelier", "ceiling", "fan"},
    "surface": {"vase", "book", "plate", "cup", "small_prop", "clutter"},
    "opening": {"door", "window", "gate"},
    "corner": {"corner"},
    "roof": {"roof", "chimney"},
    "exterior_ground": {"tree", "bush", "grass", "flower", "mailbox"},
}

STYLE_KEYWORDS: dict[str, set[str]] = {
    "modern": {"modern", "minimal", "clean"},
    "industrial": {"industrial", "factory", "metal"},
    "classic": {"classic", "ornate", "victorian", "traditional"},
    "rustic": {"rustic", "farmhouse", "wooden"},
    "scandinavian": {"scandinavian", "nordic"},
    "luxury": {"luxury", "premium", "marble"},
    "sci_fi": {"scifi", "sci", "fi", "futuristic", "future"},
    "cyberpunk": {"cyberpunk", "neon"},
    "coastal": {"coastal", "beach", "nautical"},
}

ROOM_KEYWORDS: dict[str, set[str]] = {
    "living_room": {"living", "lounge", "family"},
    "bedroom": {"bedroom", "bed", "guest_room", "guest"},
    "bathroom": {"bath", "bathroom", "powder", "toilet", "shower"},
    "kitchen": {"kitchen", "pantry", "counter", "island"},
    "dining_room": {"dining", "breakfast", "nook"},
    "hallway": {"hall", "hallway", "corridor", "entry", "foyer"},
    "office": {"office", "study", "workspace"},
    "garage": {"garage"},
    "facade": {"facade", "exterior", "outdoor", "outside"},
    "balcony": {"balcony"},
    "patio": {"patio"},
    "rooftop": {"rooftop", "roof"},
}

LOCKED_FUNCTIONS = {"access"}
LOCKED_CATEGORIES = {"opening"}
TIGHT_FUNCTIONS = {"seating", "sleeping", "lighting", "surface", "storage"}
WIDE_CATEGORIES = {"decor", "foliage"}


def slugify_asset_id(value: str) -> str:
    value = value.strip().lower().replace("\\", "/")
    value = value.split("/")[-1]
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "asset"


def tokenize_text(*parts: str) -> list[str]:
    text = " ".join(part for part in parts if part).lower()
    text = text.replace("/", " ").replace("\\", " ").replace("-", " ").replace(".", " ")
    raw = re.split(r"[^a-z0-9_]+", text)
    tokens: list[str] = []
    for token in raw:
        if not token:
            continue
        for chunk in token.split("_"):
            if chunk:
                tokens.append(chunk)
    return tokens


def first_best_match(tokens: set[str], mapping: dict[str, set[str]], fallback: str) -> str:
    best_key = fallback
    best_score = 0
    for key, keywords in mapping.items():
        score = len(tokens & keywords)
        if score > best_score:
            best_key = key
            best_score = score
    return best_key


def multi_matches(tokens: set[str], mapping: dict[str, set[str]]) -> list[str]:
    scored: list[tuple[str, int]] = []
    for key, keywords in mapping.items():
        score = len(tokens & keywords)
        if score > 0:
            scored.append((key, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [key for key, _ in scored]


def infer_scale_policy(category: str, function_names: list[str]) -> str:
    fn = set(function_names)
    if category in LOCKED_CATEGORIES or fn & LOCKED_FUNCTIONS:
        return "locked"
    if category in WIDE_CATEGORIES:
        return "wide"
    if fn & TIGHT_FUNCTIONS:
        return "tight"
    return "medium"


def raw_dimensions_from_record(raw: dict[str, Any]) -> dict[str, float]:
    dims = raw.get("dimensions_cm", {}) or {}
    if {"width", "depth", "height"} <= set(dims.keys()):
        return {
            "width": float(dims["width"]),
            "depth": float(dims["depth"]),
            "height": float(dims["height"]),
        }
    bounds = raw.get("bounds_cm", {}) or {}
    ext = bounds.get("box_extent")
    if isinstance(ext, (list, tuple)) and len(ext) == 3:
        return {"width": float(ext[0]) * 2.0, "depth": float(ext[1]) * 2.0, "height": float(ext[2]) * 2.0}
    width = raw.get("width_cm")
    depth = raw.get("depth_cm")
    height = raw.get("height_cm")
    if width is not None and depth is not None and height is not None:
        return {"width": float(width), "depth": float(depth), "height": float(height)}
    return {"width": 0.0, "depth": 0.0, "height": 0.0}


def find_baseline_key(
    category: str,
    function_names: list[str],
    category_baselines: dict[str, Any],
    clearance_profile: str | None = None,
) -> str | None:
    baselines = category_baselines.get("baselines", {})
    if clearance_profile and clearance_profile in baselines:
        return clearance_profile
    for key, baseline in baselines.items():
        if baseline.get("category") == category and baseline.get("function") in function_names:
            return key
    for function_name in function_names:
        if function_name in baselines:
            return function_name
    if category in baselines:
        return category
    return None


def get_expected_dimensions(baseline: dict[str, Any]) -> dict[str, float]:
    dims = baseline.get("expected_dimensions_cm", {}) or {}
    if not dims and {"min_width_cm", "max_width_cm"} <= set(baseline.keys()):
        dims = {
            "width_min": baseline.get("min_width_cm", 0),
            "width_max": baseline.get("max_width_cm", 10_000),
            "depth_min": baseline.get("min_depth_cm", 0),
            "depth_max": baseline.get("max_depth_cm", 10_000),
            "height_min": baseline.get("min_height_cm", 0),
            "height_max": baseline.get("max_height_cm", 10_000),
        }
    return {
        "width_min": float(dims.get("width_min", 0)),
        "width_max": float(dims.get("width_max", 10_000)),
        "depth_min": float(dims.get("depth_min", 0)),
        "depth_max": float(dims.get("depth_max", 10_000)),
        "height_min": float(dims.get("height_min", 0)),
        "height_max": float(dims.get("height_max", 10_000)),
    }


def is_dimension_reasonable(dimensions_cm: dict[str, float], expected: dict[str, float]) -> bool:
    width = dimensions_cm["width"]
    depth = dimensions_cm["depth"]
    height = dimensions_cm["height"]
    if min(width, depth, height) <= 0:
        return False
    return (
        expected["width_min"] <= width <= expected["width_max"]
        and expected["depth_min"] <= depth <= expected["depth_max"]
        and expected["height_min"] <= height <= expected["height_max"]
    )


def naming_score_from_tokens(asset_name: str) -> int:
    tokens = tokenize_text(asset_name)
    if not tokens:
        return 20
    meaningful = [token for token in tokens if token not in GENERIC_NAME_TOKENS and not token.isdigit()]
    if len(meaningful) >= 3:
        return 90
    if len(meaningful) == 2:
        return 72
    if len(meaningful) == 1:
        return 55
    return 30


def metadata_score_from_tags(tags: dict[str, Any]) -> int:
    score = 0
    if tags.get("category"):
        score += 20
    if tags.get("function"):
        score += 20
    if tags.get("room_types"):
        score += 20
    if tags.get("mount_type"):
        score += 20
    if tags.get("scale_policy"):
        score += 20
    return score


def classification_score_from_tags(tags: dict[str, Any]) -> int:
    score = 40
    if tags.get("styles"):
        score += 15
    if tags.get("placement_behavior"):
        score += 10
    if tags.get("clearance_profile"):
        score += 10
    if tags.get("room_types"):
        score += 15
    if tags.get("function"):
        score += 10
    return min(score, 100)


def placement_score_from_tags(tags: dict[str, Any], dimensions_cm: dict[str, float]) -> int:
    score = 35
    if tags.get("mount_type"):
        score += 20
    if tags.get("room_types"):
        score += 20
    if tags.get("clearance_profile"):
        score += 10
    if min(dimensions_cm.values()) > 0:
        score += 15
    return min(score, 100)


def collision_score_from_raw(raw: dict[str, Any]) -> int:
    has_collision = raw.get("collision_verified")
    if has_collision is True:
        return 95
    if has_collision is False:
        return 45
    return 70


def validator_score_from_raw(raw: dict[str, Any]) -> int:
    if raw.get("validator_passed") is True:
        return 100
    if raw.get("validator_passed") is False:
        return 35
    return 80


def compute_trust_score(scores: dict[str, int]) -> int:
    value = (
        0.22 * scores["metadata_score"]
        + 0.24 * scores["dimension_score"]
        + 0.18 * scores["classification_score"]
        + 0.08 * scores["naming_score"]
        + 0.10 * scores["collision_score"]
        + 0.08 * scores["placement_score"]
        + 0.10 * scores["validator_score"]
    )
    return round(max(0, min(100, value)))


def trust_band(score: int) -> tuple[str, str]:
    if score >= 85:
        return "high", "approved"
    if score >= 70:
        return "medium", "limited"
    if score >= 50:
        return "low", "review_only"
    return "low", "quarantined"


def infer_styles(tokens: set[str]) -> list[str]:
    return multi_matches(tokens, STYLE_KEYWORDS)[:3]


def infer_room_types(tokens: set[str], room_taxonomy: dict[str, Any]) -> list[str]:
    matches = multi_matches(tokens, ROOM_KEYWORDS)
    aliases = room_taxonomy.get("aliases", {})
    alias_hits: list[str] = []
    for token in tokens:
        if token in aliases:
            alias_hits.append(aliases[token])
    combined: list[str] = []
    seen: set[str] = set()
    for room in matches + alias_hits:
        if room not in seen:
            seen.add(room)
            combined.append(room)
    return combined[:4]


def infer_tags(raw: dict[str, Any], room_taxonomy: dict[str, Any]) -> dict[str, Any]:
    asset_path = raw.get("asset_path", "")
    asset_name = raw.get("asset_name", "") or asset_path.split("/")[-1]
    package_path = raw.get("package_path", "")
    tokens = set(tokenize_text(asset_path, asset_name, package_path))
    category = raw.get("category") or first_best_match(tokens, CATEGORY_KEYWORDS, "decor")
    functions = raw.get("function") or multi_matches(tokens, FUNCTION_KEYWORDS)
    if isinstance(functions, str):
        functions = [functions]
    if not functions:
        functions = ["decoration"] if category == "decor" else ["structure" if category in {"architecture", "structural"} else "surface"]
    room_types = raw.get("room_types") or infer_room_types(tokens, room_taxonomy)
    if isinstance(room_types, str):
        room_types = [room_types]
    if not room_types:
        room_types = ["facade"] if category in {"opening", "structural", "architecture"} else ["living_room"]
    mount_type = raw.get("mount_type") or first_best_match(tokens, MOUNT_KEYWORDS, "floor")
    styles = raw.get("styles") or infer_styles(tokens)
    if isinstance(styles, str):
        styles = [styles]
    scale_policy = raw.get("scale_policy") or infer_scale_policy(category, functions)
    placement_behavior: list[str] = []
    is_prefab = bool(raw.get("is_prefab", False)) or asset_name.upper().startswith(PREFAB_PREFIXES) or "Prefab" in str(raw.get("asset_class", ""))
    if mount_type == "wall":
        placement_behavior.append("wall_aligned")
    if mount_type == "ceiling":
        placement_behavior.append("hangs_from_ceiling")
    if mount_type == "corner":
        placement_behavior.extend(["corner_friendly", "snap_to_corner"])
    if mount_type == "roof":
        placement_behavior.extend(["roof_aligned", "snap_to_shell"])
    if category == "opening":
        placement_behavior.extend(["shell_boundary", "snap_to_shell"])
    if mount_type == "floor":
        placement_behavior.append("against_wall")
    if is_prefab:
        placement_behavior.append("prefab_anchor_driven")
    shell_sensitive = bool(raw.get("shell_sensitive", category == "opening" or "facade" in room_types or "balcony" in room_types))
    return {
        "category": category,
        "function": functions,
        "room_types": room_types,
        "styles": styles,
        "mount_type": mount_type,
        "scale_policy": scale_policy,
        "shell_sensitive": shell_sensitive,
        "clearance_profile": raw.get("clearance_profile"),
        "placement_behavior": placement_behavior,
        "is_prefab": is_prefab,
        "prefab_family": raw.get("prefab_family") or (mount_type if is_prefab else None),
    }


def build_scale_limits(scale_policy: str, baseline: dict[str, Any] | None) -> dict[str, float]:
    if baseline and baseline.get("default_scale_limits"):
        limits = baseline["default_scale_limits"]
        return {
            "min": float(limits.get("min", 1.0)),
            "max": float(limits.get("max", 1.0)),
            "preferred": float(limits.get("preferred", 1.0)),
        }
    if scale_policy == "locked":
        return {"min": 1.0, "max": 1.0, "preferred": 1.0}
    if scale_policy == "tight":
        return {"min": 0.95, "max": 1.05, "preferred": 1.0}
    if scale_policy == "medium":
        return {"min": 0.9, "max": 1.1, "preferred": 1.0}
    return {"min": 0.8, "max": 1.2, "preferred": 1.0}


def build_placement_rules(tags: dict[str, Any], placement_profiles: dict[str, Any]) -> dict[str, Any]:
    profile_name = tags.get("clearance_profile")
    profiles = placement_profiles.get("profiles", {})
    if profile_name and profile_name in profiles:
        return deepcopy(profiles[profile_name])
    if profile_name and profile_name in placement_profiles:
        return deepcopy(placement_profiles[profile_name])
    mount_type = tags.get("mount_type", "floor")
    scale_policy = tags.get("scale_policy", "medium")
    rules: dict[str, Any] = {"allowed_surfaces": [mount_type], "default_scale_policy": scale_policy}
    if mount_type == "floor":
        rules.update(
            {
                "min_front_clearance_cm": placement_profiles.get("default", {}).get("preferred_clearance_cm", 45),
                "min_side_clearance_cm": 8,
                "min_back_clearance_cm": 3,
                "against_wall_ok": True,
                "corner_ok": True,
                "preferred_yaw_step_deg": 90,
            }
        )
    elif mount_type == "wall":
        rules.update({"min_mount_height_cm": 120, "max_mount_height_cm": 240, "preferred_yaw_step_deg": 90, "snap_grid_cm": 5})
    elif mount_type == "opening":
        rules.update(
            {
                "shell_sensitive": True,
                "preferred_yaw_step_deg": 90,
                "snap_grid_cm": 10,
                "requires_planar_alignment": True,
                "allow_nonuniform_scale": False,
            }
        )
    elif mount_type == "corner":
        rules.update(
            {
                "corner_ok": True,
                "preferred_yaw_step_deg": 90,
                "snap_grid_cm": 10,
                "requires_corner_anchor": True,
                "allow_nonuniform_scale": False,
            }
        )
    elif mount_type == "roof":
        rules.update(
            {
                "preferred_yaw_step_deg": 45,
                "preferred_pitch_step_deg": 15,
                "snap_grid_cm": 10,
                "requires_planar_alignment": True,
                "allow_nonuniform_scale": False,
            }
        )
    return rules


def enrich_record(
    raw: dict[str, Any],
    room_taxonomy: dict[str, Any],
    placement_profiles: dict[str, Any],
    category_baselines: dict[str, Any],
) -> dict[str, Any]:
    asset_path = raw.get("asset_path") or raw.get("path") or ""
    asset_name = raw.get("asset_name") or asset_path.split("/")[-1]
    package_path = raw.get("package_path") or "/".join(asset_path.split("/")[:-1])
    asset_class = raw.get("asset_class", "Unknown")
    tags = infer_tags(raw, room_taxonomy)
    baseline_key = find_baseline_key(
        category=tags["category"],
        function_names=tags["function"],
        category_baselines=category_baselines,
        clearance_profile=tags.get("clearance_profile"),
    )
    baselines = category_baselines.get("baselines", {}) or category_baselines
    baseline = baselines.get(baseline_key, {}) if baseline_key else {}
    if not tags.get("clearance_profile") and baseline_key:
        tags["clearance_profile"] = baseline_key
    dimensions_cm = raw_dimensions_from_record(raw)
    expected = get_expected_dimensions(baseline) if baseline else {
        "width_min": 0,
        "width_max": 10_000,
        "depth_min": 0,
        "depth_max": 10_000,
        "height_min": 0,
        "height_max": 10_000,
    }
    dimension_score = 95 if is_dimension_reasonable(dimensions_cm, expected) else 45 if min(dimensions_cm.values()) > 0 else 20
    quality_flags = {
        "metadata_complete": metadata_score_from_tags(tags) == 100,
        "bounds_verified": min(dimensions_cm.values()) > 0,
        "collision_verified": raw.get("collision_verified", None),
        "preview_verified": bool(raw.get("preview_set")),
        "pivot_suspect": bool(raw.get("pivot_suspect", False)),
        "scale_suspect": dimension_score < 60,
        "prefab_ready": bool(tags.get("is_prefab", False)),
    }
    scores = {
        "metadata_score": metadata_score_from_tags(tags),
        "dimension_score": dimension_score,
        "classification_score": classification_score_from_tags(tags),
        "naming_score": naming_score_from_tokens(asset_name),
        "collision_score": collision_score_from_raw(raw),
        "placement_score": placement_score_from_tags(tags, dimensions_cm),
        "validator_score": validator_score_from_raw(raw),
    }
    trust = compute_trust_score(scores)
    trust_level, status = trust_band(trust)
    bounds_cm = raw.get("bounds_cm") or {
        "origin": [0.0, 0.0, round(dimensions_cm["height"] / 2.0, 2)],
        "box_extent": [
            round(dimensions_cm["width"] / 2.0, 2),
            round(dimensions_cm["depth"] / 2.0, 2),
            round(dimensions_cm["height"] / 2.0, 2),
        ],
    }
    return {
        "asset_id": raw.get("asset_id") or slugify_asset_id(asset_path or asset_name),
        "asset_path": asset_path,
        "package_path": package_path,
        "asset_name": asset_name,
        "asset_class": asset_class,
        "status": status,
        "trust_score": trust,
        "trust_level": trust_level,
        "tags": tags,
        "dimensions_cm": dimensions_cm,
        "bounds_cm": bounds_cm,
        "scale_limits": raw.get("scale_limits") or build_scale_limits(tags["scale_policy"], baseline),
        "placement_rules": raw.get("placement_rules") or build_placement_rules(tags, placement_profiles),
        "quality_flags": quality_flags,
        "scores": scores,
        "preview_set": raw.get("preview_set", {}),
        "quarantine": {"is_quarantined": status == "quarantined", "reasons": []},
        "last_indexed_utc": raw.get("last_indexed_utc"),
        "baseline_key": baseline_key,
    }


def trust_score(asset: dict[str, Any]) -> float:
    if "trust_score" in asset:
        return float(asset.get("trust_score", 0))
    if "trust" in asset:
        return float(asset.get("trust", 0.5))
    return 0.5
