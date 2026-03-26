"""Parse natural language prompts into structured AssetSpec."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AssetSpec
from .ai_client import chat_json


# Load tag dictionary for classification
_TAG_DICT_PATH = Path(__file__).resolve().parents[2] / "config" / "tag_dictionary.json"


def _load_tag_dictionary() -> dict[str, Any]:
    if _TAG_DICT_PATH.exists():
        with open(_TAG_DICT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# Category mapping from tag_dictionary categories to pipeline categories
CATEGORY_MAP = {
    "furniture": "furniture",
    "architecture": "architecture",
    "decor": "prop",
    "lighting": "prop",
    "plumbing": "prop",
    "appliance": "prop",
    "structural": "architecture",
    "opening": "architecture",
    "surface": "terrain",
}

# Keywords for quick classification without AI
KEYWORD_CATEGORIES = {
    "architecture": [
        "house", "building", "castle", "tower", "wall", "bridge", "gate",
        "fortress", "cabin", "barn", "church", "temple", "warehouse",
        "skyscraper", "apartment", "shed", "garage", "bunker",
    ],
    "furniture": [
        "chair", "table", "desk", "bed", "sofa", "couch", "shelf",
        "bookcase", "cabinet", "dresser", "bench", "stool", "wardrobe",
        "nightstand", "ottoman",
    ],
    "terrain": [
        "terrain", "hill", "mountain", "cliff", "valley", "plateau",
        "crater", "island", "rock", "boulder", "landscape", "ground",
    ],
    "vegetation": [
        "tree", "bush", "flower", "grass", "plant", "vine", "hedge",
        "mushroom", "cactus", "fern",
    ],
    "vehicle": [
        "car", "truck", "boat", "ship", "airplane", "helicopter",
        "tank", "bike", "motorcycle", "train",
    ],
    "prop": [
        "barrel", "crate", "box", "sign", "lamp", "torch", "flag",
        "statue", "pillar", "column", "fence", "well", "chest",
        "pot", "vase", "rug", "carpet", "mirror", "clock",
    ],
}


def _quick_classify(prompt: str) -> str:
    """Fast keyword-based category detection."""
    words = prompt.lower().split()
    for category, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            if kw in words or any(kw in w for w in words):
                return category
    return "prop"


def parse_intent(prompt: str, project: str = "default") -> AssetSpec:
    """Parse a user prompt into a structured AssetSpec using free AI."""
    tag_dict = _load_tag_dictionary()
    categories = tag_dict.get("required_tags", {}).get("category", [])
    styles = tag_dict.get("recommended_tags", {}).get("styles", [])

    # Quick classification as fallback
    quick_cat = _quick_classify(prompt)

    system_msg = f"""You are an asset specification parser for a 3D game asset pipeline.
Given a user prompt requesting a 3D asset, extract a structured specification.

Available categories: {', '.join(KEYWORD_CATEGORIES.keys())}
Available styles: {', '.join(styles) if styles else 'modern, medieval, futuristic, rustic, industrial, fantasy, sci-fi'}

Respond with ONLY a JSON object (no markdown, no explanation):
{{
  "asset_name": "snake_case_name (e.g. modern_house, wooden_chair)",
  "category": "one of the categories above",
  "purpose": "brief description of intended use",
  "required_components": ["list", "of", "structural", "parts"],
  "expected_silhouette": "brief shape description",
  "scale_range_cm": {{"min_width": 0, "max_width": 0, "min_height": 0, "max_height": 0, "min_depth": 0, "max_depth": 0}},
  "interior_required": false,
  "failure_conditions": ["list of things that would make this asset wrong"],
  "style": "visual style",
  "color_palette": ["hex colors or color names"]
}}

For scale, use realistic centimeter dimensions:
- Chair: ~50w x 50d x 85h
- Table: ~120w x 80d x 75h
- House: ~800w x 600d x 500h
- Tree: ~200w x 200d x 500h
- Barrel: ~60w x 60d x 90h"""

    try:
        result = chat_json(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Create specification for: {prompt}"},
            ],
            temperature=0.3,
        )

        if "error" in result:
            # AI failed — use keyword-based fallback
            return _fallback_spec(prompt, quick_cat)

        return AssetSpec(
            prompt=prompt,
            asset_name=result.get("asset_name", ""),
            category=result.get("category", quick_cat),
            purpose=result.get("purpose", prompt),
            required_components=result.get("required_components", []),
            expected_silhouette=result.get("expected_silhouette", ""),
            scale_range_cm=result.get("scale_range_cm", {}),
            interior_required=result.get("interior_required", False),
            failure_conditions=result.get("failure_conditions", []),
            style=result.get("style", ""),
            color_palette=result.get("color_palette", []),
        )

    except Exception:
        return _fallback_spec(prompt, quick_cat)


def _fallback_spec(prompt: str, category: str) -> AssetSpec:
    """Generate a basic spec without AI when providers are unavailable."""
    # Default scales by category
    scales = {
        "furniture": {"min_width": 40, "max_width": 200, "min_height": 40, "max_height": 200, "min_depth": 40, "max_depth": 200},
        "architecture": {"min_width": 300, "max_width": 1500, "min_height": 200, "max_height": 800, "min_depth": 300, "max_depth": 1500},
        "terrain": {"min_width": 500, "max_width": 5000, "min_height": 100, "max_height": 2000, "min_depth": 500, "max_depth": 5000},
        "prop": {"min_width": 20, "max_width": 150, "min_height": 20, "max_height": 200, "min_depth": 20, "max_depth": 150},
        "vegetation": {"min_width": 50, "max_width": 400, "min_height": 100, "max_height": 800, "min_depth": 50, "max_depth": 400},
        "vehicle": {"min_width": 150, "max_width": 600, "min_height": 100, "max_height": 300, "min_depth": 300, "max_depth": 1200},
    }

    components = {
        "furniture": ["seat", "legs", "back"],
        "architecture": ["walls", "roof", "floor", "door"],
        "terrain": ["surface", "base"],
        "prop": ["body"],
        "vegetation": ["trunk", "canopy"],
        "vehicle": ["body", "wheels"],
    }

    # Build name from prompt
    name = prompt.lower().strip()
    for prefix in ("create ", "make ", "generate ", "build ", "a ", "an ", "the "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    import re
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    parts = name.split("_")[:4]
    name = "_".join(parts) or "asset"

    return AssetSpec(
        prompt=prompt,
        asset_name=name,
        category=category,
        purpose=prompt,
        required_components=components.get(category, ["body"]),
        expected_silhouette=f"recognizable {category} shape",
        scale_range_cm=scales.get(category, scales["prop"]),
        interior_required=category == "architecture" and any(
            w in prompt.lower() for w in ("house", "building", "cabin", "room", "interior")
        ),
        failure_conditions=[
            f"does not look like a {category}",
            "disconnected geometry",
            "floating parts",
            "wrong proportions",
        ],
        style="",
        color_palette=[],
    )
