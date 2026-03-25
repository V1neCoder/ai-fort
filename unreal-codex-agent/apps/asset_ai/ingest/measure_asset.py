from __future__ import annotations

from typing import Any

from apps.asset_ai.ingest.scale_policy import resolve_scale_limits


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def dimensions_from_raw(raw: dict[str, Any]) -> dict[str, float]:
    dims = raw.get("dimensions_cm") or {}
    if {"width", "depth", "height"} <= set(dims.keys()):
        return {"width": _safe_float(dims["width"]), "depth": _safe_float(dims["depth"]), "height": _safe_float(dims["height"])}
    bounds = raw.get("bounds_cm") or {}
    extent = bounds.get("box_extent")
    if isinstance(extent, (list, tuple)) and len(extent) == 3:
        return {"width": _safe_float(extent[0]) * 2.0, "depth": _safe_float(extent[1]) * 2.0, "height": _safe_float(extent[2]) * 2.0}
    return {
        "width": _safe_float(raw.get("width_cm")),
        "depth": _safe_float(raw.get("depth_cm")),
        "height": _safe_float(raw.get("height_cm")),
    }


def bounds_from_dimensions(dimensions_cm: dict[str, float]) -> dict[str, Any]:
    width = _safe_float(dimensions_cm.get("width"))
    depth = _safe_float(dimensions_cm.get("depth"))
    height = _safe_float(dimensions_cm.get("height"))
    return {
        "origin": [0.0, 0.0, round(height / 2.0, 2)],
        "box_extent": [round(width / 2.0, 2), round(depth / 2.0, 2), round(height / 2.0, 2)],
    }


def baseline_key_for_record(
    category: str,
    function_names: list[str],
    category_baselines: dict[str, Any],
    explicit_key: str | None = None,
) -> str | None:
    baselines = category_baselines.get("baselines", {}) or category_baselines
    if explicit_key and explicit_key in baselines:
        return explicit_key
    for key, baseline in baselines.items():
        if baseline.get("category") == category and baseline.get("function") in function_names:
            return key
    for function_name in function_names:
        if function_name in baselines:
            return function_name
    if category in baselines:
        return category
    return None


def expected_dimension_ranges(baseline: dict[str, Any]) -> dict[str, float]:
    dims = baseline.get("expected_dimensions_cm", {}) or {}
    if not dims and {"min_width_cm", "max_width_cm"} <= set(baseline.keys()):
        dims = {
            "width_min": baseline.get("min_width_cm", 0),
            "width_max": baseline.get("max_width_cm", 999999),
            "depth_min": baseline.get("min_depth_cm", 0),
            "depth_max": baseline.get("max_depth_cm", 999999),
            "height_min": baseline.get("min_height_cm", 0),
            "height_max": baseline.get("max_height_cm", 999999),
        }
    return {
        "width_min": _safe_float(dims.get("width_min", 0)),
        "width_max": _safe_float(dims.get("width_max", 999999)),
        "depth_min": _safe_float(dims.get("depth_min", 0)),
        "depth_max": _safe_float(dims.get("depth_max", 999999)),
        "height_min": _safe_float(dims.get("height_min", 0)),
        "height_max": _safe_float(dims.get("height_max", 999999)),
    }


def dimension_score(dimensions_cm: dict[str, float], expected_ranges: dict[str, float]) -> int:
    width = dimensions_cm["width"]
    depth = dimensions_cm["depth"]
    height = dimensions_cm["height"]
    if min(width, depth, height) <= 0:
        return 20
    in_range = (
        expected_ranges["width_min"] <= width <= expected_ranges["width_max"]
        and expected_ranges["depth_min"] <= depth <= expected_ranges["depth_max"]
        and expected_ranges["height_min"] <= height <= expected_ranges["height_max"]
    )
    return 95 if in_range else 45


def measure_record(raw: dict[str, Any], tags: dict[str, Any], category_baselines: dict[str, Any]) -> dict[str, Any]:
    dimensions_cm = dimensions_from_raw(raw)
    bounds_cm = raw.get("bounds_cm") or bounds_from_dimensions(dimensions_cm)
    baseline_key = baseline_key_for_record(
        category=tags.get("category", "decor"),
        function_names=tags.get("function", []) or [],
        category_baselines=category_baselines,
        explicit_key=tags.get("clearance_profile"),
    )
    baselines = category_baselines.get("baselines", {}) or category_baselines
    baseline = baselines.get(baseline_key, {}) if baseline_key else {}
    expected = expected_dimension_ranges(baseline) if baseline else expected_dimension_ranges({})
    return {
        "dimensions_cm": dimensions_cm,
        "bounds_cm": bounds_cm,
        "baseline_key": baseline_key,
        "dimension_score": dimension_score(dimensions_cm, expected),
        "scale_limits": resolve_scale_limits(scale_policy=tags.get("scale_policy", "medium"), baseline=baseline),
    }


def measure_asset(asset_id: str) -> dict[str, Any]:
    return {"asset_id": asset_id, "bounds_cm": [0, 0, 0]}
