from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from apps.orchestrator.state_store import SessionStateStore


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_triplet(value: Any, default: list[float] | None = None) -> list[float]:
    fallback = list(default or [0.0, 0.0, 0.0])
    if isinstance(value, dict):
        return [
            _safe_float(value.get("x"), fallback[0]),
            _safe_float(value.get("y"), fallback[1]),
            _safe_float(value.get("z"), fallback[2]),
        ]
    if isinstance(value, (list, tuple)):
        padded = list(value[:3]) + fallback[len(value[:3]) :]
        return [
            _safe_float(padded[0], fallback[0]),
            _safe_float(padded[1], fallback[1]),
            _safe_float(padded[2], fallback[2]),
        ]
    return fallback


def placement_profile_path(repo_root: Path) -> Path:
    return repo_root / "data" / "cache" / "placement_pose_profiles.json"


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"profiles": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("profiles", {})
    if not isinstance(payload["profiles"], dict):
        payload["profiles"] = {}
    return payload


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True))
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def load_pose_profiles(repo_root: Path) -> dict[str, Any]:
    return _load_payload(placement_profile_path(repo_root))


def load_pose_profile(repo_root: Path, asset_path: str | None) -> dict[str, Any] | None:
    asset_key = str(asset_path or "").strip()
    if not asset_key:
        return None
    payload = load_pose_profiles(repo_root)
    profile = payload.get("profiles", {}).get(asset_key)
    return dict(profile) if isinstance(profile, dict) else None


def save_pose_profile(
    repo_root: Path,
    *,
    asset_path: str,
    rest_rotation_internal: list[float],
    orientation_candidate: str,
    height_cm: float,
    support_surface_kind: str,
    support_fit_state: str,
    source: str = "uefn_mcp",
) -> dict[str, Any]:
    asset_key = str(asset_path or "").strip()
    if not asset_key:
        raise ValueError("asset_path is required to save a placement pose profile.")
    payload = load_pose_profiles(repo_root)
    profile = {
        "asset_path": asset_key,
        "rest_rotation_internal": [round(value, 3) for value in _safe_triplet(rest_rotation_internal)],
        "orientation_candidate": str(orientation_candidate or ""),
        "height_cm": round(_safe_float(height_cm, 0.0), 3),
        "support_surface_kind": str(support_surface_kind or ""),
        "support_fit_state": str(support_fit_state or ""),
        "source": str(source or "uefn_mcp"),
        "updated_at_utc": SessionStateStore.utcnow_static(),
    }
    payload.setdefault("profiles", {})
    payload["profiles"][asset_key] = profile
    _write_payload(placement_profile_path(repo_root), payload)
    return profile
