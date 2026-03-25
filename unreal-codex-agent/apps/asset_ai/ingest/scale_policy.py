from __future__ import annotations

from typing import Any


LOCKED_FUNCTIONS = {"access"}
LOCKED_CATEGORIES = {"opening"}
TIGHT_FUNCTIONS = {"seating", "sleeping", "lighting", "surface", "storage"}
WIDE_CATEGORIES = {"decor", "foliage"}


def infer_scale_policy(category: str, function_names: list[str]) -> str:
    fn = set(function_names)
    if category in LOCKED_CATEGORIES or fn & LOCKED_FUNCTIONS:
        return "locked"
    if category in WIDE_CATEGORIES:
        return "wide"
    if fn & TIGHT_FUNCTIONS:
        return "tight"
    return "medium"


def resolve_scale_limits(scale_policy: str, baseline: dict[str, Any] | None = None) -> dict[str, float]:
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


def scale_policy(category: str) -> dict[str, str]:
    return {"category": category, "policy": "default"}
