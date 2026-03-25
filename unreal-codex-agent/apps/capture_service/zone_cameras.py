from __future__ import annotations

from typing import Any


def _normalize_view(view: Any) -> dict[str, Any] | None:
    if not isinstance(view, dict):
        return None
    name = str(view.get("name") or "").strip()
    if not name:
        return None
    return {
        "name": name,
        "type": str(view.get("type") or "2d"),
        "purpose": str(view.get("purpose") or "unknown"),
    }


def _dedupe_views(views: list[dict[str, Any]], max_images: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for view in views:
        name = str(view.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(view)
    return deduped[: max(1, max_images)]


def zone_camera_views(profile: dict[str, Any]) -> list[dict[str, Any]]:
    views = [normalized for normalized in (_normalize_view(view) for view in list(profile.get("views", []))) if normalized]
    if profile.get("include_top_view", False):
        views.append({"name": "top_view", "type": "2d", "purpose": "layout_check"})
    if profile.get("include_closeup", False):
        views.append({"name": "closeup_detail", "type": "2d", "purpose": "detail_check"})
    max_images = int(profile.get("max_images", len(views) or 1))
    return _dedupe_views(views, max_images)
