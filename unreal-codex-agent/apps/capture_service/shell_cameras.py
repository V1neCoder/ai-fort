from __future__ import annotations

from typing import Any

from apps.capture_service.zone_cameras import _dedupe_views, _normalize_view


def shell_camera_views(profile: dict[str, Any]) -> list[dict[str, Any]]:
    views = [normalized for normalized in (_normalize_view(view) for view in list(profile.get("views", []))) if normalized]
    labels = {view.get("name") for view in views}
    for required in (
        {"name": "outside_context", "type": "2d", "purpose": "exterior_check"},
        {"name": "inside_context", "type": "2d", "purpose": "interior_check"},
        {"name": "cross_boundary", "type": "2d", "purpose": "boundary_check"},
    ):
        if required["name"] not in labels:
            views.append(required)
    if profile.get("include_top_view", False):
        views.append({"name": "top_view", "type": "2d", "purpose": "layout_check"})
    if profile.get("include_closeup", False):
        views.append({"name": "closeup_detail", "type": "2d", "purpose": "detail_check"})
    max_images = int(profile.get("max_images", len(views) or 1))
    return _dedupe_views(views, max_images)
