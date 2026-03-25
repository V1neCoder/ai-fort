from __future__ import annotations

from pathlib import Path


DEFAULT_PREVIEW_NAMES = ("front", "angle", "top")


def _stringify_path(path: Path) -> str:
    return path.as_posix()


def resolve_existing_preview_set(asset_id: str, preview_root: Path) -> dict[str, str]:
    asset_dir = preview_root / asset_id
    preview_set: dict[str, str] = {}
    if not asset_dir.exists():
        return preview_set
    for name in DEFAULT_PREVIEW_NAMES:
        candidate = asset_dir / f"{name}.png"
        if candidate.exists():
            preview_set[name] = _stringify_path(candidate)
    return preview_set


def build_preview_set(raw: dict, asset_id: str, preview_root: Path) -> dict[str, str]:
    existing = raw.get("preview_set") or {}
    if isinstance(existing, dict) and existing:
        return {str(key): str(value) for key, value in existing.items()}
    resolved = resolve_existing_preview_set(asset_id=asset_id, preview_root=preview_root)
    if resolved:
        return resolved
    asset_dir = preview_root / asset_id
    return {name: _stringify_path(asset_dir / f"{name}.png") for name in DEFAULT_PREVIEW_NAMES}


def preview_quality_flags(preview_set: dict[str, str]) -> dict[str, bool]:
    return {
        "has_front": bool(preview_set.get("front")),
        "has_angle": bool(preview_set.get("angle")),
        "has_top": bool(preview_set.get("top")),
        "preview_verified": all(bool(preview_set.get(name)) for name in DEFAULT_PREVIEW_NAMES),
    }


def preview_capture(asset_id: str) -> list[str]:
    return [f"data/previews/{asset_id}/front.png"]
