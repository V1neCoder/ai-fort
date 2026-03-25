from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from apps.orchestrator.state_store import SessionStateStore


def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(json.dumps(payload, indent=2))
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def profile_store_path(repo_root: Path) -> Path:
    return repo_root / "data" / "cache" / "support_profiles.json"


def load_profiles(repo_root: Path) -> dict[str, Any]:
    path = profile_store_path(repo_root)
    if not path.exists():
        return {"profiles": {}, "updated_at_utc": SessionStateStore.utcnow_static()}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"profiles": {}, "updated_at_utc": SessionStateStore.utcnow_static()}
    if not isinstance(payload, dict):
        return {"profiles": {}, "updated_at_utc": SessionStateStore.utcnow_static()}
    payload.setdefault("profiles", {})
    payload.setdefault("updated_at_utc", SessionStateStore.utcnow_static())
    return payload


def load_support_profile(repo_root: Path, support_key: str) -> dict[str, Any] | None:
    payload = load_profiles(repo_root)
    profiles = dict(payload.get("profiles") or {})
    profile = dict(profiles.get(_safe_text(support_key)) or {})
    return profile or None


def save_support_profile(
    repo_root: Path,
    *,
    support_key: str,
    support_surface_kind: str,
    support_level: int,
    surface_z: float,
    thickness_cm: float,
    snap_margin_cm: float,
    visual_gap_expected: bool,
) -> dict[str, Any]:
    payload = load_profiles(repo_root)
    profiles = dict(payload.get("profiles") or {})
    key = _safe_text(support_key) or _safe_text(support_surface_kind) or "support_surface"
    profiles[key] = {
        "support_key": key,
        "support_surface_kind": _safe_text(support_surface_kind),
        "support_level": int(support_level),
        "surface_z": round(_safe_float(surface_z), 3),
        "thickness_cm": round(_safe_float(thickness_cm), 3),
        "snap_margin_cm": round(_safe_float(snap_margin_cm), 3),
        "visual_gap_expected": bool(visual_gap_expected),
        "updated_at_utc": SessionStateStore.utcnow_static(),
    }
    payload["profiles"] = profiles
    payload["updated_at_utc"] = SessionStateStore.utcnow_static()
    _write_atomic_json(profile_store_path(repo_root), payload)
    return dict(profiles[key])
