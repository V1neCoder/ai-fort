from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from apps.integrations.uefn_backend import backend_settings, uefn_content_root
from apps.integrations.uefn_toolbelt import write_shared_init_script
from apps.placement.managed_registry import (
    default_identity_policy,
    default_managed_slot,
    get_slot_record,
    managed_records_for_zone,
    registry_owned_actor_paths,
    upsert_slot_record,
)
from apps.placement.interference import detect_actor_conflicts, find_non_interfering_location, translated_actor
from apps.placement.profile_store import load_pose_profile, save_pose_profile
from apps.placement.support_profiles import save_support_profile
from apps.placement.support_fit import classify_support_surface_fit


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_repo_path(repo_root: Path, value: Any, default: str) -> Path:
    raw = str(value or default).strip() or default
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _write_atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def mcp_settings(repo_root: Path) -> dict[str, Any]:
    settings = backend_settings(repo_root)
    default_port = _safe_int(settings.get("uefn_mcp_port"), 8765)
    max_port = max(default_port, _safe_int(settings.get("uefn_mcp_max_port"), 8770))
    return {
        "enabled": bool(settings.get("uefn_mcp_enabled", False)),
        "default_port": default_port,
        "max_port": max_port,
        "repo_root": _resolve_repo_path(repo_root, settings.get("uefn_mcp_repo_path"), "vendor/uefn-mcp-server"),
        "server_path": _resolve_repo_path(repo_root, settings.get("uefn_mcp_server_path"), "vendor/uefn-mcp-server/mcp_server.py"),
        "listener_source_path": _resolve_repo_path(repo_root, settings.get("uefn_mcp_listener_path"), "vendor/uefn-mcp-server/uefn_listener.py"),
        "init_source_path": _resolve_repo_path(repo_root, settings.get("uefn_mcp_init_path"), "vendor/uefn-mcp-server/init_unreal.py"),
        "client_config_path": _resolve_repo_path(repo_root, settings.get("uefn_mcp_client_config_path"), ".mcp.json"),
    }


def mcp_content_python_root(repo_root: Path) -> Path | None:
    content_root = uefn_content_root(repo_root)
    if content_root is None:
        return None
    return (content_root / "Python").resolve()


def mcp_package_installed() -> bool:
    return importlib.util.find_spec("mcp") is not None


def mcp_listener_deployed(repo_root: Path) -> dict[str, Any]:
    target_root = mcp_content_python_root(repo_root)
    if target_root is None:
        return {
            "content_python_root": "",
            "listener_path": "",
            "bridge_init_path": "",
            "init_path": "",
            "listener_exists": False,
            "bridge_init_exists": False,
            "init_exists": False,
            "ready": False,
        }
    listener_path = target_root / "uefn_listener.py"
    bridge_init_path = target_root / "uefn_mcp_init.py"
    init_path = target_root / "init_unreal.py"
    return {
        "content_python_root": str(target_root),
        "listener_path": str(listener_path),
        "bridge_init_path": str(bridge_init_path),
        "init_path": str(init_path),
        "listener_exists": listener_path.exists(),
        "bridge_init_exists": bridge_init_path.exists(),
        "init_exists": init_path.exists(),
        "ready": listener_path.exists() and init_path.exists(),
    }


def _http_get_json(url: str, timeout: float = 1.0) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _http_post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body if isinstance(body, dict) else {}


def discover_listener_port(repo_root: Path, timeout: float = 1.0) -> int | None:
    settings = mcp_settings(repo_root)
    if not settings["enabled"]:
        return None
    for port in range(settings["default_port"], settings["max_port"] + 1):
        try:
            body = _http_get_json(f"http://127.0.0.1:{port}", timeout=timeout)
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            continue
        if body.get("status") == "ok":
            return port
    return None


def mcp_listener_running(repo_root: Path) -> bool:
    return discover_listener_port(repo_root) is not None


def send_command(
    repo_root: Path,
    command: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float = 20.0,
) -> dict[str, Any]:
    port = discover_listener_port(repo_root, timeout=min(timeout, 1.5))
    if port is None:
        raise ConnectionError("UEFN MCP listener is not running.")
    body = _http_post_json(
        f"http://127.0.0.1:{port}",
        {"command": command, "params": params or {}},
        timeout=timeout,
    )
    if not body.get("success", False):
        raise RuntimeError(str(body.get("error") or f"UEFN MCP command failed: {command}"))
    result = body.get("result")
    return result if isinstance(result, dict) else {"value": result}


def execute_python(repo_root: Path, code: str, *, timeout: float = 20.0) -> dict[str, Any]:
    return send_command(repo_root, "execute_python", {"code": code}, timeout=timeout)


def _unique_text_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _asset_path_variants(asset_path: str) -> list[str]:
    raw = str(asset_path or "").strip()
    if not raw:
        return []
    variants = [raw]
    tail = raw.rsplit("/", 1)[-1]
    if "." in tail:
        package_path, _, object_name = raw.rpartition(".")
        if package_path:
            variants.append(package_path)
        if object_name:
            variants.append(raw)
    else:
        object_name = tail
        variants.append(f"{raw}.{object_name}")
    return _unique_text_values(variants)


def does_asset_exist(repo_root: Path, asset_path: str) -> bool:
    raw = str(asset_path or "").strip()
    if not raw:
        return False
    try:
        result = send_command(repo_root, "does_asset_exist", {"asset_path": raw}, timeout=10.0)
    except Exception:
        return False
    return bool(result.get("exists", False))


def resolve_existing_asset_path(
    repo_root: Path,
    asset_path: str,
    alternatives: list[str] | None = None,
) -> dict[str, Any]:
    checked: list[dict[str, Any]] = []
    inputs = _unique_text_values([asset_path, *(alternatives or [])])
    for candidate in inputs:
        for variant in _asset_path_variants(candidate):
            exists = does_asset_exist(repo_root, variant)
            checked.append({"input": candidate, "candidate": variant, "exists": exists})
            if exists:
                return {"asset_path": variant, "checked": checked}
    return {"asset_path": "", "checked": checked}


def _vector_triplet(value: Any) -> list[float]:
    if isinstance(value, dict):
        return [
            float(value.get("x", 0.0) or 0.0),
            float(value.get("y", 0.0) or 0.0),
            float(value.get("z", 0.0) or 0.0),
        ]
    if isinstance(value, (list, tuple)):
        padded = list(value[:3]) + [0.0, 0.0, 0.0]
        return [float(padded[0]), float(padded[1]), float(padded[2])]
    return [0.0, 0.0, 0.0]


def _rotator_triplet(value: Any) -> list[float]:
    if isinstance(value, dict):
        roll = float(value.get("roll", 0.0) or 0.0)
        pitch = float(value.get("pitch", 0.0) or 0.0)
        yaw = float(value.get("yaw", 0.0) or 0.0)
        return [roll, pitch, yaw]
    return _vector_triplet(value)


def _internal_rotation_to_unreal(rotation: Any) -> list[float]:
    values = _vector_triplet(rotation)
    roll, pitch, yaw = values[0], values[1], values[2]
    return [pitch, yaw, roll]


def _aggregate_bounds(actors: list[dict[str, Any]]) -> dict[str, Any]:
    min_corner: list[float] | None = None
    max_corner: list[float] | None = None
    for actor in actors:
        bounds = actor.get("bounds_cm")
        if not isinstance(bounds, dict):
            continue
        origin = _vector_triplet(bounds.get("origin"))
        extent = _vector_triplet(bounds.get("box_extent"))
        lower = [origin[0] - extent[0], origin[1] - extent[1], origin[2] - extent[2]]
        upper = [origin[0] + extent[0], origin[1] + extent[1], origin[2] + extent[2]]
        if min_corner is None:
            min_corner = lower
            max_corner = upper
            continue
        min_corner = [min(min_corner[i], lower[i]) for i in range(3)]
        max_corner = [max(max_corner[i], upper[i]) for i in range(3)]
    if min_corner is None or max_corner is None:
        return {}
    origin = [(min_corner[i] + max_corner[i]) / 2.0 for i in range(3)]
    extent = [(max_corner[i] - min_corner[i]) / 2.0 for i in range(3)]
    return {"origin": origin, "box_extent": extent}


def _normalize_actor_payload(raw_actor: dict[str, Any]) -> dict[str, Any]:
    actor = dict(raw_actor or {})
    normalized: dict[str, Any] = {
        "label": str(actor.get("label") or actor.get("name") or ""),
        "actor_name": str(actor.get("name") or actor.get("label") or ""),
        "class_name": str(actor.get("class") or actor.get("class_name") or ""),
        "actor_path": str(actor.get("path") or actor.get("actor_path") or ""),
        "asset_path": str(actor.get("asset_path") or ""),
        "material_paths": list(actor.get("material_paths") or []),
        "material_count": _safe_int(actor.get("material_count"), 0),
        "collision_enabled": actor.get("collision_enabled") if isinstance(actor.get("collision_enabled"), bool) or actor.get("collision_enabled") is None else None,
        "actor_collision_enabled": actor.get("actor_collision_enabled") if isinstance(actor.get("actor_collision_enabled"), bool) or actor.get("actor_collision_enabled") is None else None,
        "query_collision_enabled": actor.get("query_collision_enabled") if isinstance(actor.get("query_collision_enabled"), bool) or actor.get("query_collision_enabled") is None else None,
        "physics_collision_enabled": actor.get("physics_collision_enabled") if isinstance(actor.get("physics_collision_enabled"), bool) or actor.get("physics_collision_enabled") is None else None,
        "collision_mode": str(actor.get("collision_mode") or ""),
        "collision_profile_name": str(actor.get("collision_profile_name") or ""),
        "location": _vector_triplet(actor.get("location")),
        "rotation": _rotator_triplet(actor.get("rotation")),
        "scale": _vector_triplet(actor.get("scale") or [1.0, 1.0, 1.0]),
        "selected": bool(actor.get("selected", False)),
        "room_type": str(actor.get("room_type") or ""),
    }
    if isinstance(actor.get("bounds_cm"), dict):
        normalized["bounds_cm"] = {
            "origin": _vector_triplet((actor.get("bounds_cm") or {}).get("origin")),
            "box_extent": _vector_triplet((actor.get("bounds_cm") or {}).get("box_extent")),
        }
    return normalized


def collect_scene_state(repo_root: Path) -> dict[str, Any]:
    code = """
world = unreal.EditorLevelLibrary.get_editor_world()
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_sub.get_all_level_actors()
selected_paths = {a.get_path_name() for a in actor_sub.get_selected_level_actors()}
items = []
for actor in actors:
    loc = actor.get_actor_location()
    rot = actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()
    try:
        bounds_origin, bounds_extent = actor.get_actor_bounds(False)
    except Exception:
        bounds_origin, bounds_extent = loc, unreal.Vector(0, 0, 0)

    asset_path = ""
    material_paths = []
    material_count = 0
    collision_enabled = None
    actor_collision_enabled = None
    query_collision_enabled = None
    physics_collision_enabled = None
    collision_mode = ""
    collision_profile_name = ""
    try:
        if hasattr(actor, "get_actor_enable_collision"):
            try:
                actor_collision_enabled = bool(actor.get_actor_enable_collision())
            except Exception:
                actor_collision_enabled = None
        smc = actor.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            mesh = smc.get_editor_property("static_mesh")
            if mesh:
                asset_path = mesh.get_path_name()
            try:
                mats = smc.get_materials()
                material_paths = [mat.get_path_name() for mat in mats if mat]
                material_count = len(material_paths)
            except Exception:
                material_paths = []
                material_count = 0
            try:
                if hasattr(smc, "is_collision_enabled"):
                    collision_enabled = bool(smc.is_collision_enabled())
            except Exception:
                collision_enabled = None
            try:
                if hasattr(smc, "is_query_collision_enabled"):
                    query_collision_enabled = bool(smc.is_query_collision_enabled())
            except Exception:
                query_collision_enabled = None
            try:
                if hasattr(smc, "is_physics_collision_enabled"):
                    physics_collision_enabled = bool(smc.is_physics_collision_enabled())
            except Exception:
                physics_collision_enabled = None
            try:
                if hasattr(smc, "get_collision_enabled"):
                    collision_mode = str(smc.get_collision_enabled() or "")
            except Exception:
                collision_mode = ""
            try:
                if hasattr(smc, "get_collision_profile_name"):
                    collision_profile_name = str(smc.get_collision_profile_name() or "")
            except Exception:
                collision_profile_name = ""
    except Exception:
        asset_path = ""
        material_paths = []
        material_count = 0
        collision_enabled = None
        actor_collision_enabled = None
        query_collision_enabled = None
        physics_collision_enabled = None
        collision_mode = ""
        collision_profile_name = ""

    if collision_enabled is None:
        collision_enabled = actor_collision_enabled

    items.append({
        "name": actor.get_name(),
        "label": actor.get_actor_label(),
        "class": actor.get_class().get_name(),
        "path": actor.get_path_name(),
        "asset_path": asset_path,
        "material_paths": material_paths,
        "material_count": material_count,
        "collision_enabled": collision_enabled,
        "actor_collision_enabled": actor_collision_enabled,
        "query_collision_enabled": query_collision_enabled,
        "physics_collision_enabled": physics_collision_enabled,
        "collision_mode": collision_mode,
        "collision_profile_name": collision_profile_name,
        "location": {"x": loc.x, "y": loc.y, "z": loc.z},
        "rotation": {"pitch": rot.pitch, "yaw": rot.yaw, "roll": rot.roll},
        "scale": {"x": scale.x, "y": scale.y, "z": scale.z},
        "bounds_cm": {
            "origin": {"x": bounds_origin.x, "y": bounds_origin.y, "z": bounds_origin.z},
            "box_extent": {"x": bounds_extent.x, "y": bounds_extent.y, "z": bounds_extent.z},
        },
        "selected": actor.get_path_name() in selected_paths,
    })

result = {
    "map_name": world.get_name() if world else "UnknownMap",
    "world_path": world.get_path_name() if world else "",
    "actors": items,
}
"""
    execution = execute_python(repo_root, code, timeout=25.0)
    execution_result = execution.get("result")
    raw = execution_result if isinstance(execution_result, dict) else {}
    raw_actors = raw.get("actors") if isinstance(raw.get("actors"), list) else []
    actors = [_normalize_actor_payload(actor) for actor in raw_actors if isinstance(actor, dict)]
    selected = [actor for actor in actors if actor.get("selected")]
    dirty_actor_ids = [
        actor.get("label") or actor.get("actor_name")
        for actor in selected
        if actor.get("label") or actor.get("actor_name")
    ]
    scene_state = {
        "map_name": raw.get("map_name") or raw.get("world_path") or "UnknownMap",
        "actors": actors,
        "dirty_actor_ids": dirty_actor_ids,
        "dirty_bounds": _aggregate_bounds(selected),
        "room_type": "unknown",
        "shell_sensitive": False,
        "clearance_observations": {},
        "shell_alignment": {
            "inside_checked": False,
            "outside_checked": False,
            "is_consistent": None,
        },
        "collision_issues": [],
        "backend_notes": [],
    }
    stdout = str(execution.get("stdout") or "").strip()
    stderr = str(execution.get("stderr") or "").strip()
    if stdout:
        scene_state["backend_notes"].append(f"uefn_mcp stdout: {stdout}")
    if stderr:
        scene_state["backend_notes"].append(f"uefn_mcp stderr: {stderr}")
    return scene_state


def _actor_identifier_from_payload(action_payload: dict[str, Any]) -> str | None:
    for key in ("actor_path", "target_actor_path", "actor_label", "target_actor_label", "spawn_label"):
        value = str(action_payload.get(key) or "").strip()
        if value:
            return value
    return None


def _normalize_spawned_actor(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "actor_name": str(raw.get("name") or ""),
        "label": str(raw.get("label") or ""),
        "class_name": str(raw.get("class") or ""),
        "actor_path": str(raw.get("path") or ""),
        "location": _vector_triplet(raw.get("location")),
        "rotation": _rotator_triplet(raw.get("rotation")),
        "scale": _vector_triplet(raw.get("scale") or [1.0, 1.0, 1.0]),
    }


def _actor_bottom_z(actor_payload: dict[str, Any]) -> float | None:
    bounds = dict(actor_payload.get("bounds_cm") or {})
    origin = bounds.get("origin")
    extent = bounds.get("box_extent")
    if not isinstance(origin, list) or not isinstance(extent, list) or len(origin) < 3 or len(extent) < 3:
        return None
    return float(origin[2]) - float(extent[2])


def _actor_height_cm(actor_payload: dict[str, Any]) -> float | None:
    bounds = dict(actor_payload.get("bounds_cm") or {})
    extent = bounds.get("box_extent")
    if not isinstance(extent, list) or len(extent) < 3:
        return None
    return float(extent[2]) * 2.0


def _fit_state_for_actor_support(
    actor_payload: dict[str, Any],
    support_z: float,
    *,
    mount_type: str = "",
    structural_role: str = "",
    support_fit_reference_z: float | None = None,
) -> dict[str, Any]:
    normalized_mount_type = str(mount_type or "").strip().lower()
    normalized_role = str(structural_role or "").strip().lower()
    effective_support_z = float(support_fit_reference_z) if support_fit_reference_z is not None else float(support_z)
    if normalized_role in {"wall_base", "wall_header", "roof_panel", "roof_ridge"}:
        bottom_z = _actor_bottom_z(actor_payload)
        return {
            "support_surface_delta_cm": round((_safe_float(bottom_z, effective_support_z) - effective_support_z), 3),
            "support_surface_fit_state": "not_applicable",
            "support_surface_fit_ok": True,
            "support_fit_skipped": "structural_role_not_floor_like",
        }
    if normalized_mount_type and normalized_mount_type not in {"floor", "surface", "exterior_ground"}:
        bottom_z = _actor_bottom_z(actor_payload)
        return {
            "support_surface_delta_cm": round((_safe_float(bottom_z, effective_support_z) - effective_support_z), 3),
            "support_surface_fit_state": "not_applicable",
            "support_surface_fit_ok": True,
            "support_fit_skipped": "mount_type_not_floor_like",
        }
    bottom_z = _actor_bottom_z(actor_payload)
    if bottom_z is None:
        return {}
    return classify_support_surface_fit(float(bottom_z) - effective_support_z)


def _support_reference_from_hint(
    placement_hint: dict[str, Any],
    *,
    support_anchor_type: str | None,
    support_anchor: list[float] | None,
) -> dict[str, Any]:
    return {
        "support_surface_kind": str(placement_hint.get("support_surface_kind") or ""),
        "support_level": int(_safe_float(placement_hint.get("support_level"), 0.0)),
        "parent_support_actor": str(placement_hint.get("parent_support_actor") or placement_hint.get("support_actor_label") or ""),
        "support_actor_label": str(placement_hint.get("support_actor_label") or ""),
        "support_actor_path": str(placement_hint.get("support_actor_path") or ""),
        "support_reference_policy": str(placement_hint.get("support_reference_policy") or ""),
        "support_reference_source": str(placement_hint.get("support_reference_source") or ""),
        "support_anchor_type": str(support_anchor_type or ""),
        "support_anchor": [round(float(value), 3) for value in list(support_anchor or [])[:3]] if isinstance(support_anchor, list) else None,
    }


def _normalized_placement_hint(action_payload: dict[str, Any]) -> dict[str, Any]:
    hint = dict(action_payload.get("placement_hint") or {})
    action_name = str(action_payload.get("action") or "").strip().lower()
    placement_phase = str(hint.get("placement_phase") or "").strip().lower()
    if placement_phase not in {"initial_place", "reposition", "reanchor"}:
        placement_phase = "reposition" if action_name in {"move_actor", "set_transform", "rotate_actor", "scale_actor"} else "initial_place"
    snap_policy = str(hint.get("snap_policy") or "").strip().lower()
    if snap_policy not in {"initial_only", "force", "none"}:
        snap_policy = "force" if placement_phase == "reanchor" else ("none" if placement_phase == "reposition" else "initial_only")
    support_reference_policy = str(hint.get("support_reference_policy") or "").strip().lower()
    if support_reference_policy not in {"selected_first", "nearest_surface", "explicit_only"}:
        support_reference_policy = "selected_first"
    interference_policy = str(hint.get("interference_policy") or "").strip().lower()
    if interference_policy not in {"avoid", "allow", "replace_managed"}:
        interference_policy = "allow" if placement_phase == "reposition" else "avoid"
    duplicate_policy = str(hint.get("duplicate_policy") or "").strip().lower()
    if duplicate_policy not in {"reuse", "cleanup_managed", "allow"}:
        duplicate_policy = "cleanup_managed" if action_name == "place_asset" else "reuse"
    hint["placement_phase"] = placement_phase
    hint["snap_policy"] = snap_policy
    hint["support_reference_policy"] = support_reference_policy
    hint["interference_policy"] = interference_policy
    hint["duplicate_policy"] = duplicate_policy
    return hint


def _should_apply_support_snap(placement_hint: dict[str, Any], mount_type: str) -> bool:
    if mount_type not in {"floor", "surface", "exterior_ground"}:
        return False
    placement_phase = str(placement_hint.get("placement_phase") or "initial_place").strip().lower()
    snap_policy = str(placement_hint.get("snap_policy") or "initial_only").strip().lower()
    structural_role = str(placement_hint.get("structural_role") or "").strip().lower()
    if snap_policy == "none":
        return False
    if snap_policy == "force":
        return True
    if structural_role in {"elevated_floor", "stair_step"}:
        return False
    return placement_phase == "initial_place"


def _support_anchor_from_hint(placement_hint: dict[str, Any], fallback_location: list[float]) -> tuple[str | None, list[float]]:
    support_kind = str(placement_hint.get("support_surface_kind") or "").strip().lower()
    if support_kind == "landscape":
        for key in ("ground_anchor", "landscape_anchor", "surface_anchor", "anchor_point"):
            value = placement_hint.get(key)
            if isinstance(value, list) and len(value) >= 3:
                return key, _vector_triplet(value)
        return "ground_anchor", list(fallback_location)
    for key in ("surface_anchor", "ground_anchor", "landscape_anchor", "anchor_point"):
        value = placement_hint.get(key)
        if isinstance(value, list) and len(value) >= 3:
            return key, _vector_triplet(value)
    return None, list(fallback_location)


def _actor_distance_sq(actor_payload: dict[str, Any], anchor: list[float] | None) -> float:
    location = _vector_triplet(actor_payload.get("location"))
    if not isinstance(anchor, list) or len(anchor) < 3:
        return 0.0
    dx = float(location[0]) - float(anchor[0])
    dy = float(location[1]) - float(anchor[1])
    dz = float(location[2]) - float(anchor[2])
    return (dx * dx) + (dy * dy) + (dz * dz)


def _stable_actor_sort_key(actor_payload: dict[str, Any], support_anchor: list[float] | None) -> tuple[float, str, str]:
    return (
        round(_actor_distance_sq(actor_payload, support_anchor), 3),
        str(actor_payload.get("actor_path") or "").lower(),
        str(actor_payload.get("label") or "").lower(),
    )


def find_actors_by_label(repo_root: Path, label: str) -> list[dict[str, Any]]:
    target_label = str(label or "").strip()
    if not target_label:
        return []
    code = f"""
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
items = []
for actor in actor_sub.get_all_level_actors():
    try:
        if actor.get_actor_label() != {target_label!r}:
            continue
        loc = actor.get_actor_location()
        rot = actor.get_actor_rotation()
        scale = actor.get_actor_scale3d()
        try:
            bounds_origin, bounds_extent = actor.get_actor_bounds(False)
        except Exception:
            bounds_origin, bounds_extent = loc, unreal.Vector(0, 0, 0)
        asset_path = ""
        try:
            smc = actor.get_component_by_class(unreal.StaticMeshComponent)
            if smc:
                mesh = smc.get_editor_property("static_mesh")
                if mesh:
                    asset_path = mesh.get_path_name()
        except Exception:
            asset_path = ""
        items.append({{
            "name": actor.get_name(),
            "label": actor.get_actor_label(),
            "class": actor.get_class().get_name(),
            "path": actor.get_path_name(),
            "asset_path": asset_path,
            "location": {{"x": loc.x, "y": loc.y, "z": loc.z}},
            "rotation": {{"pitch": rot.pitch, "yaw": rot.yaw, "roll": rot.roll}},
            "scale": {{"x": scale.x, "y": scale.y, "z": scale.z}},
            "bounds_cm": {{
                "origin": {{"x": bounds_origin.x, "y": bounds_origin.y, "z": bounds_origin.z}},
                "box_extent": {{"x": bounds_extent.x, "y": bounds_extent.y, "z": bounds_extent.z}},
            }},
        }})
    except Exception:
        pass
result = {{"actors": items}}
"""
    try:
        response = execute_python(repo_root, code, timeout=25.0)
    except Exception:
        return []
    result = response.get("result")
    if not isinstance(result, dict):
        return []
    actors = result.get("actors")
    if not isinstance(actors, list):
        return []
    normalized = [_normalize_actor_payload(actor) for actor in actors if isinstance(actor, dict)]
    return sorted(normalized, key=lambda actor: _stable_actor_sort_key(actor, None))


def _delete_actors_by_paths(repo_root: Path, actor_paths: list[str]) -> dict[str, Any] | None:
    target_paths = [str(path) for path in actor_paths if str(path or "").strip()]
    if not target_paths:
        return None
    code = f"""
paths = set({target_paths!r})
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
deleted = []
failed = []
for actor in list(actor_sub.get_all_level_actors()):
    if actor.get_path_name() not in paths:
        continue
    try:
        unreal.EditorLevelLibrary.destroy_actor(actor)
        deleted.append(actor.get_path_name())
    except Exception as exc:
        failed.append({{"path": actor.get_path_name(), "error": str(exc)}})
result = {{
    "requested_count": len(paths),
    "deleted_count": len(deleted),
    "deleted_paths": deleted,
    "failed": failed,
}}
"""
    try:
        response = execute_python(repo_root, code, timeout=30.0)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc), "requested_count": len(target_paths)}
    result = response.get("result")
    if isinstance(result, dict):
        return {"success": True, **result}
    return {"success": True, "requested_count": len(target_paths), "deleted_count": 0, "deleted_paths": [], "failed": []}


def _find_reusable_spawn_target(
    repo_root: Path,
    *,
    spawn_label: str,
    asset_path: str,
    support_anchor: list[float] | None,
    owned_actor_paths: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    label = str(spawn_label or "").strip()
    if not label:
        return {}, None
    matches = find_actors_by_label(repo_root, label)
    if asset_path:
        filtered = [actor for actor in matches if not actor.get("asset_path") or str(actor.get("asset_path")) == asset_path]
        if filtered:
            matches = filtered
    if not matches:
        return {}, None
    ordered = sorted(matches, key=lambda actor: _stable_actor_sort_key(actor, support_anchor))
    primary = dict(ordered[0])
    duplicates = ordered[1:]
    duplicate_paths = [str(actor.get("actor_path") or "") for actor in duplicates if str(actor.get("actor_path") or "").strip()]
    cleanup_paths = [
        path
        for path, actor in (
            (str(actor.get("actor_path") or ""), actor)
            for actor in duplicates
            if str(actor.get("actor_path") or "").strip()
        )
        if path in set(owned_actor_paths or set()) or str(actor.get("label") or "").strip().startswith("UCA_")
    ]
    cleanup_result = _delete_actors_by_paths(repo_root, cleanup_paths) if cleanup_paths else None
    return primary, {
        "spawn_label": label,
        "matched_count": len(ordered),
        "reused_actor_path": str(primary.get("actor_path") or ""),
        "deleted_duplicate_paths": cleanup_paths,
        "detected_duplicate_paths": duplicate_paths,
        "duplicate_cleanup": cleanup_result,
    }


def _get_selected_actor_paths(repo_root: Path) -> list[str]:
    code = """
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
result = {
    "actor_paths": [actor.get_path_name() for actor in actor_sub.get_selected_level_actors()]
}
"""
    try:
        response = execute_python(repo_root, code, timeout=15.0)
    except Exception:
        return []
    result = response.get("result")
    if not isinstance(result, dict):
        return []
    values = result.get("actor_paths")
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value or "").strip()]


def _restore_selected_actor_paths(repo_root: Path, actor_paths: list[str]) -> dict[str, Any]:
    desired_paths = [str(path) for path in actor_paths if str(path or "").strip()]
    code = f"""
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
try:
    actor_sub.select_nothing()
except Exception:
    pass
desired = set({desired_paths!r})
restored = 0
for actor in actor_sub.get_all_level_actors():
    if actor.get_path_name() in desired:
        try:
            actor_sub.set_actor_selection_state(actor, True)
            restored += 1
        except Exception:
            pass
result = {{
    "requested_count": len(desired),
    "restored_count": restored,
}}
"""
    try:
        response = execute_python(repo_root, code, timeout=20.0)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
    result = response.get("result")
    return {"success": True, **(result if isinstance(result, dict) else {})}


def _force_actor_transform(
    repo_root: Path,
    *,
    actor_identifier: str,
    location: list[float],
    rotation_internal: list[float],
    scale: list[float],
) -> dict[str, Any] | None:
    actor_value = str(actor_identifier or "").strip()
    if not actor_value:
        return None
    unreal_rotation = _internal_rotation_to_unreal(rotation_internal)
    code = f"""
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
target = None
for actor in actor_sub.get_all_level_actors():
    if actor.get_path_name() == {actor_value!r} or actor.get_actor_label() == {actor_value!r}:
        target = actor
        break

if target is None:
    raise RuntimeError(f"Actor not found for transform update: {actor_value}")

target.modify()
target.set_actor_location(unreal.Vector({float(location[0])}, {float(location[1])}, {float(location[2])}), False, False)
target.set_actor_rotation(unreal.Rotator({float(unreal_rotation[0])}, {float(unreal_rotation[1])}, {float(unreal_rotation[2])}), False)
target.set_actor_scale3d(unreal.Vector({float(scale[0])}, {float(scale[1])}, {float(scale[2])}))

loc = target.get_actor_location()
rot = target.get_actor_rotation()
actor_scale = target.get_actor_scale3d()
result = {{
    "actor_path": target.get_path_name(),
    "actor_label": target.get_actor_label(),
    "location": [loc.x, loc.y, loc.z],
    "rotation": [rot.roll, rot.pitch, rot.yaw],
    "scale": [actor_scale.x, actor_scale.y, actor_scale.z],
}}
"""
    try:
        response = execute_python(repo_root, code, timeout=25.0)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
    result = response.get("result")
    if isinstance(result, dict):
        return {"success": True, **result}
    return {"success": False, "stdout": str(response.get("stdout") or ""), "stderr": str(response.get("stderr") or "")}


def _floor_rotation_candidates(rotation_internal: list[float]) -> list[tuple[str, list[float], int]]:
    roll, pitch, yaw = _rotator_triplet(rotation_internal)
    candidates: list[tuple[str, list[float], int]] = [
        ("as_is", [roll, pitch, yaw], 0),
        ("roll_pos_90", [roll + 90.0, pitch, yaw], 90),
        ("roll_neg_90", [roll - 90.0, pitch, yaw], 90),
        ("pitch_pos_90", [roll, pitch + 90.0, yaw], 90),
        ("pitch_neg_90", [roll, pitch - 90.0, yaw], 90),
        ("yaw_pos_90", [roll, pitch, yaw + 90.0], 90),
        ("yaw_neg_90", [roll, pitch, yaw - 90.0], 90),
        ("roll_180", [roll + 180.0, pitch, yaw], 180),
        ("pitch_180", [roll, pitch + 180.0, yaw], 180),
        ("yaw_180", [roll, pitch, yaw + 180.0], 180),
    ]
    unique: list[tuple[str, list[float], int]] = []
    seen: set[tuple[float, float, float]] = set()
    for label, values, penalty in candidates:
        key = (round(float(values[0]), 3), round(float(values[1]), 3), round(float(values[2]), 3))
        if key in seen:
            continue
        seen.add(key)
        unique.append((label, [key[0], key[1], key[2]], penalty))
    return unique


def inspect_actor(repo_root: Path, actor_identifier: str) -> dict[str, Any]:
    actor_value = str(actor_identifier or "").strip()
    if not actor_value:
        return {}
    code = f"""
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
target = None
for actor in actor_sub.get_all_level_actors():
    if actor.get_path_name() == {actor_value!r} or actor.get_actor_label() == {actor_value!r}:
        target = actor
        break

if target is None:
    raise RuntimeError(f"Actor not found for inspection: {actor_value}")

loc = target.get_actor_location()
rot = target.get_actor_rotation()
scale = target.get_actor_scale3d()
try:
    bounds_origin, bounds_extent = target.get_actor_bounds(False)
except Exception:
    bounds_origin, bounds_extent = loc, unreal.Vector(0, 0, 0)

asset_path = ""
material_paths = []
material_count = 0
collision_enabled = None
actor_collision_enabled = None
query_collision_enabled = None
physics_collision_enabled = None
collision_mode = ""
collision_profile_name = ""

try:
    if hasattr(target, "get_actor_enable_collision"):
        actor_collision_enabled = bool(target.get_actor_enable_collision())
except Exception:
    actor_collision_enabled = None

try:
    smc = target.get_component_by_class(unreal.StaticMeshComponent)
    if smc:
        try:
            mesh = smc.get_editor_property("static_mesh")
            if mesh:
                asset_path = mesh.get_path_name()
        except Exception:
            asset_path = ""
        try:
            mats = smc.get_materials()
            material_paths = [mat.get_path_name() for mat in mats if mat]
            material_count = len(material_paths)
        except Exception:
            material_paths = []
            material_count = 0
        try:
            if hasattr(smc, "is_collision_enabled"):
                collision_enabled = bool(smc.is_collision_enabled())
        except Exception:
            collision_enabled = None
        try:
            if hasattr(smc, "is_query_collision_enabled"):
                query_collision_enabled = bool(smc.is_query_collision_enabled())
        except Exception:
            query_collision_enabled = None
        try:
            if hasattr(smc, "is_physics_collision_enabled"):
                physics_collision_enabled = bool(smc.is_physics_collision_enabled())
        except Exception:
            physics_collision_enabled = None
        try:
            if hasattr(smc, "get_collision_enabled"):
                collision_mode = str(smc.get_collision_enabled() or "")
        except Exception:
            collision_mode = ""
        try:
            if hasattr(smc, "get_collision_profile_name"):
                collision_profile_name = str(smc.get_collision_profile_name() or "")
        except Exception:
            collision_profile_name = ""
except Exception:
    pass

if collision_enabled is None:
    collision_enabled = actor_collision_enabled

result = {{
    "name": target.get_name(),
    "label": target.get_actor_label(),
    "class": target.get_class().get_name(),
    "path": target.get_path_name(),
    "asset_path": asset_path,
    "material_paths": material_paths,
    "material_count": material_count,
    "collision_enabled": collision_enabled,
    "actor_collision_enabled": actor_collision_enabled,
    "query_collision_enabled": query_collision_enabled,
    "physics_collision_enabled": physics_collision_enabled,
    "collision_mode": collision_mode,
    "collision_profile_name": collision_profile_name,
    "location": {{"x": loc.x, "y": loc.y, "z": loc.z}},
    "rotation": {{"pitch": rot.pitch, "yaw": rot.yaw, "roll": rot.roll}},
    "scale": {{"x": scale.x, "y": scale.y, "z": scale.z}},
    "bounds_cm": {{
        "origin": {{"x": bounds_origin.x, "y": bounds_origin.y, "z": bounds_origin.z}},
        "box_extent": {{"x": bounds_extent.x, "y": bounds_extent.y, "z": bounds_extent.z}},
    }},
}}
"""
    try:
        response = execute_python(repo_root, code, timeout=25.0)
    except Exception:
        return {}
    result = response.get("result")
    if not isinstance(result, dict):
        return {}
    return _normalize_actor_payload(result)


def _snap_floor_actor_to_support_surface(
    repo_root: Path,
    *,
    actor_identifier: str,
    actor_payload: dict[str, Any],
    support_z: float,
    rotation_internal: list[float],
    scale: list[float],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    bottom_z = _actor_bottom_z(actor_payload)
    if bottom_z is None:
        return actor_payload, None
    delta_cm = round(float(support_z) - float(bottom_z), 3)
    if abs(delta_cm) <= 1.0 or abs(delta_cm) > 2048.0:
        return actor_payload, None
    current_location = _vector_triplet(actor_payload.get("location"))
    corrected_location = [
        round(current_location[0], 3),
        round(current_location[1], 3),
        round(current_location[2] + delta_cm, 3),
    ]
    updated = send_command(
        repo_root,
        "set_actor_transform",
        {
            "actor_path": actor_identifier,
            "location": corrected_location,
            "rotation": _internal_rotation_to_unreal(rotation_internal),
            "scale": scale,
        },
        timeout=40.0,
    )
    corrected_actor = inspect_actor(repo_root, actor_identifier) or _normalize_spawned_actor(updated.get("actor"))
    if corrected_actor:
        corrected_actor["support_surface_adjustment_cm"] = delta_cm
        fit_state = _fit_state_for_actor_support(corrected_actor, support_z)
        corrected_actor["support_surface_fit_state"] = fit_state.get("support_surface_fit_state")
        corrected_actor["support_surface_fit_ok"] = fit_state.get("support_surface_fit_ok")
    return corrected_actor, {
        "delta_cm": delta_cm,
        "support_z": round(float(support_z), 3),
        "corrected_location": corrected_location,
    }


def _optimize_floor_actor_orientation(
    repo_root: Path,
    *,
    actor_identifier: str,
    actor_payload: dict[str, Any],
    support_z: float,
    rotation_internal: list[float],
    scale: list[float],
    asset_path: str,
    support_surface_kind: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    cached_profile = load_pose_profile(repo_root, asset_path)
    if isinstance(cached_profile, dict):
        cached_rotation = _vector_triplet(cached_profile.get("rest_rotation_internal"))
        updated = send_command(
            repo_root,
            "set_actor_transform",
            {
                "actor_path": actor_identifier,
                "location": _vector_triplet(actor_payload.get("location")),
                "rotation": _internal_rotation_to_unreal(cached_rotation),
                "scale": scale,
            },
            timeout=40.0,
        )
        cached_actor = inspect_actor(repo_root, actor_identifier) or _normalize_spawned_actor(updated.get("actor"))
        cached_actor, support_adjustment = _snap_floor_actor_to_support_surface(
            repo_root,
            actor_identifier=actor_identifier,
            actor_payload=cached_actor,
            support_z=support_z,
            rotation_internal=cached_rotation,
            scale=scale,
        )
        height_cm = _actor_height_cm(cached_actor) or _safe_float(cached_profile.get("height_cm"), 0.0)
        cached_actor["orientation_candidate"] = str(cached_profile.get("orientation_candidate") or "cached_pose_profile")
        cached_actor["orientation_height_cm"] = float(height_cm or 0.0)
        fit_state = _fit_state_for_actor_support(cached_actor, support_z)
        cached_actor["support_surface_fit_state"] = fit_state.get("support_surface_fit_state")
        cached_actor["support_surface_fit_ok"] = fit_state.get("support_surface_fit_ok")
        return cached_actor, {
            "rotation_label": str(cached_profile.get("orientation_candidate") or "cached_pose_profile"),
            "rotation_internal": [round(float(value), 3) for value in cached_rotation],
            "height_cm": round(float(height_cm or 0.0), 3),
            "support_adjustment": support_adjustment,
            "source": "cached_pose_profile",
        }

    base_location = _vector_triplet(actor_payload.get("location"))
    best_actor = dict(actor_payload)
    best_meta: dict[str, Any] | None = None
    best_key: tuple[float, float, int] | None = None

    for label, candidate_rotation, penalty in _floor_rotation_candidates(rotation_internal):
        updated = send_command(
            repo_root,
            "set_actor_transform",
            {
                "actor_path": actor_identifier,
                "location": base_location,
                "rotation": _internal_rotation_to_unreal(candidate_rotation),
                "scale": scale,
            },
            timeout=40.0,
        )
        candidate_actor = inspect_actor(repo_root, actor_identifier) or _normalize_spawned_actor(updated.get("actor"))
        candidate_actor, support_adjustment = _snap_floor_actor_to_support_surface(
            repo_root,
            actor_identifier=actor_identifier,
            actor_payload=candidate_actor,
            support_z=support_z,
            rotation_internal=candidate_rotation,
            scale=scale,
        )
        height_cm = _actor_height_cm(candidate_actor)
        if height_cm is None:
            height_cm = 999999.0
        adjustment_abs = abs(float((support_adjustment or {}).get("delta_cm") or 0.0))
        score_key = (round(height_cm, 3), round(adjustment_abs, 3), penalty)
        if best_key is None or score_key < best_key:
            best_key = score_key
            best_actor = dict(candidate_actor)
            best_meta = {
                "rotation_label": label,
                "rotation_internal": [round(float(value), 3) for value in candidate_rotation],
                "height_cm": round(float(height_cm), 3),
                "support_adjustment": support_adjustment,
            }

    if best_meta is None:
        return actor_payload, None

    final_location = _vector_triplet(best_actor.get("location"))
    send_command(
        repo_root,
        "set_actor_transform",
        {
            "actor_path": actor_identifier,
            "location": final_location,
            "rotation": _internal_rotation_to_unreal(best_meta["rotation_internal"]),
            "scale": scale,
        },
        timeout=40.0,
    )
    final_actor = inspect_actor(repo_root, actor_identifier) or best_actor
    if best_meta.get("support_adjustment"):
        final_actor["support_surface_adjustment_cm"] = float(best_meta["support_adjustment"]["delta_cm"])
    final_actor["orientation_candidate"] = str(best_meta.get("rotation_label") or "")
    final_actor["orientation_height_cm"] = float(best_meta.get("height_cm") or 0.0)
    if asset_path:
        fit_state = _fit_state_for_actor_support(final_actor, support_z)
        final_actor["support_surface_fit_state"] = fit_state.get("support_surface_fit_state")
        final_actor["support_surface_fit_ok"] = fit_state.get("support_surface_fit_ok")
        saved = save_pose_profile(
            repo_root,
            asset_path=asset_path,
            rest_rotation_internal=list(best_meta["rotation_internal"]),
            orientation_candidate=str(best_meta.get("rotation_label") or ""),
            height_cm=float(best_meta.get("height_cm") or 0.0),
            support_surface_kind=support_surface_kind,
            support_fit_state=str(fit_state.get("support_surface_fit_state") or ""),
        )
        final_actor["cached_pose_profile"] = saved
    return final_actor, best_meta


def _transform_snapshot(actor_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "location": [round(float(value), 3) for value in _vector_triplet(actor_payload.get("location"))],
        "rotation": [round(float(value), 3) for value in _rotator_triplet(actor_payload.get("rotation"))],
        "scale": [round(float(value), 3) for value in _vector_triplet(actor_payload.get("scale") or [1.0, 1.0, 1.0])],
    }


def _measure_transform_drift(
    actor_payload: dict[str, Any],
    *,
    requested_location: list[float],
    requested_rotation: list[float],
    requested_scale: list[float],
    location_tolerance_cm: float = 2.0,
    rotation_tolerance_deg: float = 2.0,
    scale_tolerance: float = 0.02,
) -> dict[str, Any]:
    actor_location = _vector_triplet(actor_payload.get("location"))
    actor_rotation = _rotator_triplet(actor_payload.get("rotation"))
    actor_scale = _vector_triplet(actor_payload.get("scale") or [1.0, 1.0, 1.0])
    max_location_delta = max(abs(actor_location[index] - requested_location[index]) for index in range(3))
    max_rotation_delta = max(abs(actor_rotation[index] - requested_rotation[index]) for index in range(3))
    max_scale_delta = max(abs(actor_scale[index] - requested_scale[index]) for index in range(3))
    drifted = (
        max_location_delta > location_tolerance_cm
        or max_rotation_delta > rotation_tolerance_deg
        or max_scale_delta > scale_tolerance
    )
    return {
        "drifted": drifted,
        "max_location_delta_cm": round(float(max_location_delta), 3),
        "max_rotation_delta_deg": round(float(max_rotation_delta), 3),
        "max_scale_delta": round(float(max_scale_delta), 3),
    }


def _save_support_profile_from_actor(
    repo_root: Path,
    *,
    support_reference: dict[str, Any],
    support_z: float,
) -> dict[str, Any] | None:
    support_key = str(
        support_reference.get("parent_support_actor")
        or support_reference.get("support_actor_label")
        or support_reference.get("support_surface_kind")
        or ""
    ).strip()
    if not support_key:
        return None
    support_kind = str(support_reference.get("support_surface_kind") or "")
    support_level = int(_safe_float(support_reference.get("support_level"), 0.0))
    return save_support_profile(
        repo_root,
        support_key=support_key,
        support_surface_kind=support_kind,
        support_level=support_level,
        surface_z=support_z,
        thickness_cm=0.0,
        snap_margin_cm=6.0,
        visual_gap_expected=False,
    )


def _collect_scene_actors_safe(repo_root: Path) -> list[dict[str, Any]]:
    try:
        scene_state = collect_scene_state(repo_root)
    except Exception:
        return []
    actors = scene_state.get("actors")
    if not isinstance(actors, list):
        return []
    return [dict(actor) for actor in actors if isinstance(actor, dict)]


def _cleanup_duplicate_conflicts(
    repo_root: Path,
    *,
    active_actor_path: str,
    conflicts: dict[str, Any],
    owned_actor_paths: set[str],
    duplicate_policy: str,
) -> dict[str, Any] | None:
    if duplicate_policy not in {"cleanup_managed", "reuse"}:
        return None
    def _tool_owned_duplicate(item: dict[str, Any]) -> bool:
        label = str(item.get("actor_label") or "").strip()
        return label.startswith("UCA_")
    cleanup_paths = sorted(
        {
            str(item.get("actor_path") or "").strip()
            for item in list(conflicts.get("duplicates") or [])
            if str(item.get("actor_path") or "").strip()
            and str(item.get("actor_path") or "").strip() != active_actor_path
            and (
                str(item.get("actor_path") or "").strip() in owned_actor_paths
                or _tool_owned_duplicate(item)
            )
        }
    )
    if not cleanup_paths:
        return None
    cleanup_result = _delete_actors_by_paths(repo_root, cleanup_paths)
    return {
        "requested_cleanup_paths": cleanup_paths,
        "cleanup_result": cleanup_result,
    }


def _resolve_interference_after_apply(
    repo_root: Path,
    *,
    actor_identifier: str,
    actor_payload: dict[str, Any],
    placement_hint: dict[str, Any],
    requested_location: list[float],
    requested_rotation: list[float],
    requested_scale: list[float],
    support_reference: dict[str, Any],
    support_z: float,
    mount_type: str,
    owned_actor_paths: set[str],
    assembly_actor_paths: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    placement_phase = str(placement_hint.get("placement_phase") or "initial_place").strip().lower()
    interference_policy = str(placement_hint.get("interference_policy") or "avoid").strip().lower()
    duplicate_policy = str(placement_hint.get("duplicate_policy") or "cleanup_managed").strip().lower()
    structural_role = str(placement_hint.get("structural_role") or "").strip().lower()
    reserved_volumes = [dict(item) for item in list(placement_hint.get("reserved_volumes") or []) if isinstance(item, dict)]
    allowed_reserved_volume_kinds = [
        str(value).strip()
        for value in list(placement_hint.get("allowed_reserved_volume_kinds") or [])
        if str(value or "").strip()
    ]
    scene_actors = _collect_scene_actors_safe(repo_root)
    ignore_paths = {
        str(actor_identifier or "").strip(),
        *{
            str(value or "").strip()
            for value in set(assembly_actor_paths or set())
            if str(value or "").strip()
        },
    }
    conflicts = detect_actor_conflicts(
        actor_payload,
        scene_actors,
        ignore_actor_paths=ignore_paths,
        ignore_actor_labels=set(),
        support_reference=support_reference,
        mount_type=mount_type,
        reserved_volumes=reserved_volumes,
        allowed_reserved_volume_kinds=allowed_reserved_volume_kinds,
    )
    duplicate_cleanup = _cleanup_duplicate_conflicts(
        repo_root,
        active_actor_path=str(actor_payload.get("actor_path") or actor_identifier),
        conflicts=conflicts,
        owned_actor_paths=owned_actor_paths,
        duplicate_policy=duplicate_policy,
    )
    if duplicate_cleanup and duplicate_cleanup.get("cleanup_result", {}).get("success", False):
        scene_actors = _collect_scene_actors_safe(repo_root)
        conflicts = detect_actor_conflicts(
            actor_payload,
            scene_actors,
            ignore_actor_paths=ignore_paths,
            ignore_actor_labels=set(),
            support_reference=support_reference,
            mount_type=mount_type,
            reserved_volumes=reserved_volumes,
            allowed_reserved_volume_kinds=allowed_reserved_volume_kinds,
        )

    interference_correction = None
    corrected_actor = dict(actor_payload)
    if (
        conflicts.get("blocking_interference_count", 0) > 0
        and interference_policy == "avoid"
        and placement_phase in {"initial_place", "reanchor"}
        and mount_type in {"floor", "surface", "exterior_ground"}
    ):
        candidate = find_non_interfering_location(
            actor_payload,
            scene_actors,
            requested_location=requested_location,
            support_z=support_z,
            grid_cm=_safe_float(placement_hint.get("snap_grid_cm"), 0.0),
            ignore_actor_paths=ignore_paths,
            ignore_actor_labels=set(),
            support_reference=support_reference,
            mount_type=mount_type,
            reserved_volumes=reserved_volumes,
            allowed_reserved_volume_kinds=allowed_reserved_volume_kinds,
        )
        if candidate is not None:
            target_location = list(candidate.get("location") or requested_location)
            try:
                send_command(
                    repo_root,
                    "set_actor_transform",
                    {
                        "actor_path": actor_identifier,
                        "location": target_location,
                        "rotation": _internal_rotation_to_unreal(requested_rotation),
                        "scale": requested_scale,
                    },
                    timeout=40.0,
                )
                _force_actor_transform(
                    repo_root,
                    actor_identifier=actor_identifier,
                    location=target_location,
                    rotation_internal=requested_rotation,
                    scale=requested_scale,
                )
                corrected_actor = inspect_actor(repo_root, actor_identifier) or translated_actor(actor_payload, target_location)
                scene_actors = _collect_scene_actors_safe(repo_root)
                conflicts = detect_actor_conflicts(
                    corrected_actor,
                    scene_actors,
                    ignore_actor_paths=ignore_paths,
                ignore_actor_labels=set(),
                support_reference=support_reference,
                mount_type=mount_type,
                reserved_volumes=reserved_volumes,
                allowed_reserved_volume_kinds=allowed_reserved_volume_kinds,
            )
                interference_correction = {
                    "applied": True,
                    **candidate,
                }
            except Exception as exc:  # noqa: BLE001
                interference_correction = {
                    "applied": False,
                    "error": str(exc),
                    "candidate": candidate,
                }

    observed_support = dict(conflicts.get("support_contact") or {})
    if observed_support:
        corrected_actor["observed_support_surface_kind"] = observed_support.get("support_surface_kind")
        corrected_actor["observed_support_actor_label"] = observed_support.get("actor_label")
        corrected_actor["observed_support_actor_path"] = observed_support.get("actor_path")
        corrected_actor["observed_support_surface_z"] = observed_support.get("support_surface_z")
        corrected_actor["support_surface_kind"] = observed_support.get("support_surface_kind") or corrected_actor.get("support_surface_kind")
        corrected_actor["parent_support_actor"] = observed_support.get("actor_label") or corrected_actor.get("parent_support_actor")
    if structural_role in {"wall_base", "wall_header"} and observed_support:
        observed_kind = str(observed_support.get("support_surface_kind") or "").strip().lower()
        if observed_kind in {"support_surface", "upper_slab", "balcony", "landscape"}:
            conflicts["support_mismatch"] = False
            conflicts["support_compatibility"] = "compatible"

    final_status = "clear"
    if bool(conflicts.get("support_mismatch", False)):
        final_status = "support_mismatch"
    elif conflicts.get("blocking_interference_count", 0) > 0:
        final_status = "blocked"
    elif conflicts.get("reserved_volume_conflict_count", 0) > 0:
        final_status = "reserved_volume_conflict"
    elif conflicts.get("support_occupancy_count", 0) > 0:
        final_status = "occupied"
    elif conflicts.get("duplicate_count", 0) > 0:
        final_status = "duplicates_remaining"

    support_fit_reference_z = _safe_float(placement_hint.get("support_fit_reference_z"), support_z) if placement_hint.get("support_fit_reference_z") is not None else None
    support_fit = _fit_state_for_actor_support(
        corrected_actor,
        support_z,
        mount_type=mount_type,
        structural_role=structural_role,
        support_fit_reference_z=support_fit_reference_z,
    )
    corrected_actor.update(support_fit)
    report = {
        **conflicts,
        "interference_policy": interference_policy,
        "duplicate_policy": duplicate_policy,
        "placement_phase": placement_phase,
        "duplicate_cleanup": duplicate_cleanup,
        "interference_correction": interference_correction,
        "interference_status": final_status,
    }
    corrected_actor["interference_report"] = report
    corrected_actor["interference_status"] = final_status
    corrected_actor["blocking_interference_count"] = int(conflicts.get("blocking_interference_count", 0))
    corrected_actor["duplicate_count"] = int(conflicts.get("duplicate_count", 0))
    return corrected_actor, report


def _reconcile_actor_after_apply(
    repo_root: Path,
    *,
    actor_identifier: str,
    actor_payload: dict[str, Any],
    action_name: str,
    placement_hint: dict[str, Any],
    requested_location: list[float],
    requested_rotation: list[float],
    requested_scale: list[float],
    support_z: float,
    mount_type: str,
    asset_path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    placement_phase = str(placement_hint.get("placement_phase") or "initial_place").strip().lower()
    structural_role = str(placement_hint.get("structural_role") or "").strip().lower()
    support_fit_reference_z = _safe_float(placement_hint.get("support_fit_reference_z"), support_z) if placement_hint.get("support_fit_reference_z") is not None else None
    support_fit = _fit_state_for_actor_support(
        actor_payload,
        support_z,
        mount_type=mount_type,
        structural_role=structural_role,
        support_fit_reference_z=support_fit_reference_z,
    )
    drift = _measure_transform_drift(
        actor_payload,
        requested_location=requested_location,
        requested_rotation=requested_rotation,
        requested_scale=requested_scale,
    )
    drift_status = "none"
    if str(support_fit.get("support_surface_fit_state") or "") in {"embedded", "floating"}:
        drift_status = "support_drift"
    elif placement_phase == "reposition" and bool(drift.get("drifted")):
        drift_status = "transform_drift"

    reconciliation_status = "clean"
    corrected = False
    reconciled_actor = dict(actor_payload)

    if drift_status == "support_drift" and placement_phase in {"initial_place", "reanchor"} and mount_type in {"floor", "surface", "exterior_ground"} and structural_role not in {"elevated_floor", "stair_step"}:
        reconciled_actor, orientation_adjustment = _optimize_floor_actor_orientation(
            repo_root,
            actor_identifier=actor_identifier,
            actor_payload=actor_payload,
            support_z=support_z,
            rotation_internal=requested_rotation,
            scale=requested_scale,
            asset_path=asset_path,
            support_surface_kind=str(placement_hint.get("support_surface_kind") or ""),
        )
        corrected = True
        support_fit = _fit_state_for_actor_support(
            reconciled_actor,
            support_z,
            mount_type=mount_type,
            structural_role=structural_role,
            support_fit_reference_z=support_fit_reference_z,
        )
        if str(support_fit.get("support_surface_fit_state") or "") in {"embedded", "floating"}:
            reconciliation_status = "failed"
        else:
            reconciliation_status = "corrected"
            drift_status = "none"
        reconciled_actor["orientation_adjustment"] = orientation_adjustment
    elif drift_status == "transform_drift":
        reconciliation_status = "failed"

    reconciled_actor["support_surface_fit_state"] = support_fit.get("support_surface_fit_state")
    reconciled_actor["support_surface_fit_ok"] = support_fit.get("support_surface_fit_ok")
    return reconciled_actor, {
        "reconciliation_attempted": True,
        "reconciliation_status": reconciliation_status if corrected or drift_status != "none" else "clean",
        "drift_status": drift_status,
        "transform_drift": drift,
        "support_surface_fit": support_fit,
        "corrected": corrected,
        "reconciled_actor_path": str(reconciled_actor.get("actor_path") or actor_identifier),
    }


def _set_actor_label(repo_root: Path, actor_identifier: str, label: str) -> dict[str, Any] | None:
    actor_value = str(actor_identifier or "").strip()
    label_value = str(label or "").strip()
    if not actor_value or not label_value:
        return None
    code = f"""
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
target = None
for actor in actor_sub.get_all_level_actors():
    if actor.get_path_name() == {actor_value!r} or actor.get_actor_label() == {actor_value!r}:
        target = actor
        break

if target is None:
    raise RuntimeError(f"Actor not found for label update: {actor_value}")

target.set_actor_label({label_value!r}, mark_dirty=True)
result = {{
    "actor_path": target.get_path_name(),
    "actor_label": target.get_actor_label(),
}}
"""
    try:
        response = execute_python(repo_root, code, timeout=20.0)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
    result = response.get("result")
    if isinstance(result, dict):
        return {"success": True, **result}
    return {
        "success": False,
        "stdout": str(response.get("stdout") or ""),
        "stderr": str(response.get("stderr") or ""),
    }


def set_actor_material(
    repo_root: Path,
    *,
    actor_identifier: str,
    material_path: str,
    material_index: int = 0,
) -> dict[str, Any]:
    actor_value = str(actor_identifier or "").strip()
    material_value = str(material_path or "").strip()
    if not actor_value:
        return {"success": False, "error": "actor_identifier was empty"}
    if not material_value:
        return {"success": False, "error": "material_path was empty"}
    code = f"""
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
target = None
for actor in actor_sub.get_all_level_actors():
    if actor.get_path_name() == {actor_value!r} or actor.get_actor_label() == {actor_value!r}:
        target = actor
        break

if target is None:
    raise RuntimeError(f"Actor not found for material update: {actor_value}")

material = unreal.EditorAssetLibrary.load_asset({material_value!r})
if material is None:
    raise RuntimeError(f"Material not found: {material_value}")

smc = target.get_component_by_class(unreal.StaticMeshComponent)
if smc is None:
    raise RuntimeError(f"StaticMeshComponent not found on actor: {actor_value}")

smc.set_material({int(material_index)}, material)
result = {{
    "actor_path": target.get_path_name(),
    "actor_label": target.get_actor_label(),
    "material_path": material.get_path_name(),
    "material_index": {int(material_index)},
}}
"""
    try:
        response = execute_python(repo_root, code, timeout=30.0)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
    result = response.get("result")
    if isinstance(result, dict):
        return {"success": True, **result}
    return {
        "success": False,
        "stdout": str(response.get("stdout") or ""),
        "stderr": str(response.get("stderr") or ""),
    }


def _save_level_if_requested(repo_root: Path, auto_save: bool) -> dict[str, Any] | None:
    if not auto_save:
        return None
    try:
        return send_command(repo_root, "save_current_level", timeout=30.0)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


def _finalize_editor_state(
    repo_root: Path,
    *,
    actor_identifier: str,
    previous_selection: list[str],
    auto_select_after_apply: bool,
    auto_focus_after_apply: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if auto_select_after_apply:
        select_result = send_command(repo_root, "select_actors", {"actor_paths": [actor_identifier]}, timeout=20.0)
    else:
        select_result = _restore_selected_actor_paths(repo_root, previous_selection)
        if not select_result.get("success", False):
            select_result = {
                "success": False,
                "reason": "could not restore prior selection after apply",
                **select_result,
            }
    if auto_focus_after_apply:
        try:
            focus_result = send_command(repo_root, "focus_selected", timeout=20.0)
        except Exception as exc:  # noqa: BLE001
            focus_result = {"success": False, "error": str(exc)}
    else:
        focus_result = {"success": True, "skipped": True, "reason": "auto_focus_after_apply disabled"}
    return select_result, focus_result


def apply_action_via_mcp(
    repo_root: Path,
    action_payload: dict[str, Any],
    *,
    session_path: Path | None = None,
    cycle_number: int | None = None,
    auto_save: bool = False,
) -> dict[str, Any]:
    settings = backend_settings(repo_root)
    action = dict(action_payload or {})
    action_name = str(action.get("action") or "no_op").strip().lower()
    transform = dict(action.get("transform") or {})
    location = _vector_triplet(transform.get("location"))
    rotation_internal = _rotator_triplet(transform.get("rotation"))
    scale = _vector_triplet(transform.get("scale") or [1.0, 1.0, 1.0])
    placement_hint = _normalized_placement_hint(action)
    mount_type = str(
        placement_hint.get("expected_mount_type")
        or placement_hint.get("mount_type")
        or ""
    ).strip().lower()
    zone_id = str(action.get("target_zone") or "unknown_zone").strip()
    managed_slot = str(action.get("managed_slot") or default_managed_slot(action))
    identity_policy = str(action.get("identity_policy") or default_identity_policy(action_name))
    registry_record = get_slot_record(session_path, zone_id, managed_slot) if session_path is not None else None
    owned_actor_paths = registry_owned_actor_paths(session_path) if session_path is not None else set()
    assembly_actor_paths = {
        str(record.get("actor_path") or "").strip()
        for record in (managed_records_for_zone(session_path, zone_id) if session_path is not None else [])
        if str(record.get("actor_path") or "").strip() and str(record.get("managed_slot") or "") != managed_slot
    }
    support_anchor_type, support_anchor = _support_anchor_from_hint(placement_hint, location)
    support_z = float(support_anchor[2]) if isinstance(support_anchor, list) and len(support_anchor) >= 3 else float(location[2])
    support_reference = _support_reference_from_hint(
        placement_hint,
        support_anchor_type=support_anchor_type,
        support_anchor=support_anchor,
    )
    should_snap = _should_apply_support_snap(placement_hint, mount_type)
    previous_selection = _get_selected_actor_paths(repo_root)

    if action_name in {"", "no_op"}:
        return {
            "status": "skipped",
            "backend": "uefn_mcp_apply",
            "applied_mode": "uefn_mcp_apply",
            "degraded_to_fallback": False,
            "applied": False,
            "reason": "Action was no_op.",
        }

    if action_name == "place_asset":
        asset_path = str(action.get("asset_path") or "").strip()
        spawn_label = str(action.get("spawn_label") or "").strip()
        alternatives = [
            str(value).strip()
            for value in list(action.get("alternatives") or [])
            if str(value or "").strip()
        ]
        if not asset_path and not alternatives:
            return {
                "status": "error",
                "backend": "uefn_mcp_apply",
                "applied": False,
                "reason": "place_asset requires asset_path.",
            }
        resolution = resolve_existing_asset_path(repo_root, asset_path, alternatives=alternatives)
        resolved_asset_path = str(resolution.get("asset_path") or "").strip()
        if not resolved_asset_path:
            return {
                "status": "error",
                "backend": "uefn_mcp_apply",
                "applied": False,
                "reason": "No existing UEFN asset path could be resolved for this placement action.",
                "asset_resolution": resolution,
            }

        reuse_result = None
        actor_info: dict[str, Any] = {}
        actor_identifier = ""
        registry_status = "created"
        if identity_policy != "create_only" and registry_record is not None:
            candidate_identifier = str(registry_record.get("actor_path") or registry_record.get("actor_label") or "").strip()
            if candidate_identifier:
                actor_info = inspect_actor(repo_root, candidate_identifier)
                if actor_info:
                    actor_identifier = str(actor_info.get("actor_path") or actor_info.get("label") or "").strip()
                    registry_status = "reused"
                    reuse_result = {
                        "source": "managed_registry",
                        "reused_actor_path": actor_identifier,
                        "managed_slot": managed_slot,
                        "registry_key": registry_record.get("registry_key"),
                    }
        reusable_actor = {}
        if not actor_identifier and identity_policy != "create_only":
            reusable_actor, reuse_result = _find_reusable_spawn_target(
                repo_root,
                spawn_label=spawn_label,
                asset_path=resolved_asset_path,
                support_anchor=support_anchor,
                owned_actor_paths=owned_actor_paths,
            )
            if reuse_result is not None:
                reuse_result["source"] = reuse_result.get("source") or "label_search"
        if reusable_actor:
            actor_info = inspect_actor(repo_root, str(reusable_actor.get("actor_path") or "")) or reusable_actor
            actor_identifier = str(actor_info.get("actor_path") or actor_info.get("label") or "")
            if actor_identifier:
                registry_status = "reused"
        spawned: dict[str, Any] = {}
        if not actor_identifier:
            spawned = send_command(
                repo_root,
                "spawn_actor",
                {
                    "asset_path": resolved_asset_path,
                    "location": location,
                    "rotation": _internal_rotation_to_unreal(rotation_internal),
                },
                timeout=40.0,
            )
            actor_info = _normalize_spawned_actor(spawned.get("actor"))
            actor_identifier = actor_info.get("actor_path") or actor_info.get("label") or ""
            registry_status = "created"
        if not actor_identifier:
            return {
                "status": "error",
                "backend": "uefn_mcp_apply",
                "applied_mode": "uefn_mcp_apply",
                "degraded_to_fallback": False,
                "applied": False,
                "reason": "UEFN MCP spawn did not return an actor identifier.",
                "spawn_result": spawned,
            }

        updated = send_command(
            repo_root,
            "set_actor_transform",
            {
                "actor_path": actor_identifier,
                "location": location,
                "rotation": _internal_rotation_to_unreal(rotation_internal),
                "scale": scale,
            },
            timeout=40.0,
        )
        forced_transform = _force_actor_transform(
            repo_root,
            actor_identifier=actor_identifier,
            location=location,
            rotation_internal=rotation_internal,
            scale=scale,
        )
        normalized_actor = _normalize_spawned_actor(updated.get("actor"))
        label_result = _set_actor_label(repo_root, actor_identifier, spawn_label)
        if label_result and label_result.get("success"):
            normalized_actor["label"] = str(label_result.get("actor_label") or normalized_actor.get("label") or "")
            normalized_actor["actor_path"] = str(label_result.get("actor_path") or normalized_actor.get("actor_path") or actor_identifier)
            actor_identifier = normalized_actor["actor_path"] or actor_identifier
        inspected_actor = inspect_actor(repo_root, actor_identifier)
        if inspected_actor:
            merged_actor = dict(inspected_actor)
            for key, value in normalized_actor.items():
                existing = merged_actor.get(key)
                if key not in merged_actor or existing is None or existing == "" or existing == []:
                    merged_actor[key] = value
            normalized_actor = merged_actor
        normalized_actor["support_surface_kind"] = placement_hint.get("support_surface_kind")
        normalized_actor["support_anchor_type"] = support_anchor_type
        normalized_actor["support_level"] = placement_hint.get("support_level")
        normalized_actor["parent_support_actor"] = placement_hint.get("parent_support_actor") or placement_hint.get("support_actor_label")
        support_surface_adjustment = None
        orientation_adjustment = None
        if should_snap:
            if bool(settings.get("auto_optimize_floor_orientation", True)):
                normalized_actor, orientation_adjustment = _optimize_floor_actor_orientation(
                    repo_root,
                    actor_identifier=actor_identifier,
                    actor_payload=normalized_actor,
                    support_z=support_z,
                    rotation_internal=rotation_internal,
                    scale=scale,
                    asset_path=resolved_asset_path,
                    support_surface_kind=str(placement_hint.get("support_surface_kind") or ""),
                )
                support_surface_adjustment = dict(orientation_adjustment.get("support_adjustment") or {}) if isinstance(orientation_adjustment, dict) else None
            else:
                normalized_actor, support_surface_adjustment = _snap_floor_actor_to_support_surface(
                    repo_root,
                    actor_identifier=actor_identifier,
                    actor_payload=normalized_actor,
                    support_z=support_z,
                    rotation_internal=rotation_internal,
                    scale=scale,
                )
        normalized_actor, reconciliation = _reconcile_actor_after_apply(
            repo_root,
            actor_identifier=actor_identifier,
            actor_payload=normalized_actor,
            action_name=action_name,
            placement_hint=placement_hint,
            requested_location=location,
            requested_rotation=rotation_internal,
            requested_scale=scale,
            support_z=support_z,
            mount_type=mount_type,
            asset_path=resolved_asset_path,
        )
        normalized_actor, interference_report = _resolve_interference_after_apply(
            repo_root,
            actor_identifier=actor_identifier,
            actor_payload=normalized_actor,
            placement_hint=placement_hint,
            requested_location=location,
            requested_rotation=rotation_internal,
            requested_scale=scale,
            support_reference=support_reference,
            support_z=support_z,
            mount_type=mount_type,
            owned_actor_paths=owned_actor_paths,
            assembly_actor_paths=assembly_actor_paths if placement_hint.get("assembly_zone") else None,
        )
        support_profile = _save_support_profile_from_actor(
            repo_root,
            support_reference=support_reference,
            support_z=support_z,
        )
        if session_path is not None:
            upsert_slot_record(
                session_path,
                zone_id=zone_id,
                managed_slot=managed_slot,
                action_name=action_name,
                identity_policy=identity_policy,
                actor_label=str(normalized_actor.get("label") or spawn_label),
                actor_path=str(normalized_actor.get("actor_path") or actor_identifier),
                asset_path=resolved_asset_path,
                support_reference=support_reference,
                placement_phase=str(placement_hint.get("placement_phase") or ""),
                last_confirmed_transform=_transform_snapshot(normalized_actor),
                fit_status={
                    "support_surface_fit_state": normalized_actor.get("support_surface_fit_state"),
                    "orientation_candidate": normalized_actor.get("orientation_candidate"),
                    "reconciliation_status": reconciliation.get("reconciliation_status"),
                    "drift_status": reconciliation.get("drift_status"),
                    "interference_status": interference_report.get("interference_status"),
                    "blocking_interference_count": interference_report.get("blocking_interference_count"),
                    "duplicate_count": interference_report.get("duplicate_count"),
                    "mount_type": mount_type,
                    "expected_mount_type": str(placement_hint.get("expected_mount_type") or mount_type),
                    "structural_role": str(placement_hint.get("structural_role") or ""),
                },
                registry_status="claimed" if registry_status == "created" else registry_status,
            )
        select_result, focus_result = _finalize_editor_state(
            repo_root,
            actor_identifier=actor_identifier,
            previous_selection=previous_selection,
            auto_select_after_apply=bool(settings.get("auto_select_after_apply", True)),
            auto_focus_after_apply=bool(settings.get("auto_focus_after_apply", False)),
        )
        save_result = _save_level_if_requested(repo_root, auto_save)
        return {
            "status": "ok",
            "backend": "uefn_mcp_apply",
            "applied_mode": "uefn_mcp_apply",
            "degraded_to_fallback": False,
            "applied": True,
            "action": action_name,
            "asset_path": resolved_asset_path,
            "requested_asset_path": asset_path,
            "asset_resolution": resolution,
            "placement_phase": placement_hint.get("placement_phase"),
            "snap_policy": placement_hint.get("snap_policy"),
            "managed_slot": managed_slot,
            "identity_policy": identity_policy,
            "actor": normalized_actor,
            "reuse_result": reuse_result,
            "registry_status": "claimed" if registry_status == "created" else registry_status,
            "reconciled_actor_path": reconciliation.get("reconciled_actor_path"),
            "reconciliation_attempted": reconciliation.get("reconciliation_attempted"),
            "reconciliation_status": reconciliation.get("reconciliation_status"),
            "drift_status": reconciliation.get("drift_status"),
            "support_reference": support_reference,
            "support_profile": support_profile,
            "label_result": label_result,
            "support_surface_adjustment": support_surface_adjustment,
            "orientation_adjustment": orientation_adjustment,
            "forced_transform": forced_transform,
            "reconciliation": reconciliation,
            "interference_report": interference_report,
            "select_result": select_result,
            "focus_result": focus_result,
            "save_result": save_result,
        }

    if action_name in {"move_actor", "set_transform"}:
        actor_identifier = _actor_identifier_from_payload(action)
        registry_status = "reused"
        if not actor_identifier and registry_record is not None:
            actor_identifier = str(registry_record.get("actor_path") or registry_record.get("actor_label") or "").strip()
        if not actor_identifier:
            return {
                "status": "error",
                "backend": "uefn_mcp_apply",
                "applied_mode": "uefn_mcp_apply",
                "degraded_to_fallback": False,
                "applied": False,
                "reason": f"{action_name} requires an actor identifier.",
            }
        updated = send_command(
            repo_root,
            "set_actor_transform",
            {
                "actor_path": actor_identifier,
                "location": location,
                "rotation": _internal_rotation_to_unreal(rotation_internal),
                "scale": scale,
            },
            timeout=40.0,
        )
        forced_transform = _force_actor_transform(
            repo_root,
            actor_identifier=actor_identifier,
            location=location,
            rotation_internal=rotation_internal,
            scale=scale,
        )
        normalized_actor = inspect_actor(repo_root, actor_identifier) or _normalize_spawned_actor(updated.get("actor"))
        normalized_actor["support_surface_kind"] = placement_hint.get("support_surface_kind")
        normalized_actor["support_anchor_type"] = support_anchor_type
        normalized_actor["support_level"] = placement_hint.get("support_level")
        normalized_actor["parent_support_actor"] = placement_hint.get("parent_support_actor") or placement_hint.get("support_actor_label")
        support_surface_adjustment = None
        orientation_adjustment = None
        if should_snap:
            if bool(settings.get("auto_optimize_floor_orientation", True)):
                normalized_actor, orientation_adjustment = _optimize_floor_actor_orientation(
                    repo_root,
                    actor_identifier=actor_identifier,
                    actor_payload=normalized_actor,
                    support_z=support_z,
                    rotation_internal=rotation_internal,
                    scale=scale,
                    asset_path=str(action.get("asset_path") or ""),
                    support_surface_kind=str(placement_hint.get("support_surface_kind") or ""),
                )
                support_surface_adjustment = dict(orientation_adjustment.get("support_adjustment") or {}) if isinstance(orientation_adjustment, dict) else None
            else:
                normalized_actor, support_surface_adjustment = _snap_floor_actor_to_support_surface(
                    repo_root,
                    actor_identifier=actor_identifier,
                    actor_payload=normalized_actor,
                    support_z=support_z,
                    rotation_internal=rotation_internal,
                    scale=scale,
                )
        normalized_actor, reconciliation = _reconcile_actor_after_apply(
            repo_root,
            actor_identifier=actor_identifier,
            actor_payload=normalized_actor,
            action_name=action_name,
            placement_hint=placement_hint,
            requested_location=location,
            requested_rotation=rotation_internal,
            requested_scale=scale,
            support_z=support_z,
            mount_type=mount_type,
            asset_path=str(action.get("asset_path") or (registry_record.get("asset_path") if isinstance(registry_record, dict) else "") or ""),
        )
        normalized_actor, interference_report = _resolve_interference_after_apply(
            repo_root,
            actor_identifier=actor_identifier,
            actor_payload=normalized_actor,
            placement_hint=placement_hint,
            requested_location=location,
            requested_rotation=rotation_internal,
            requested_scale=scale,
            support_reference=support_reference,
            support_z=support_z,
            mount_type=mount_type,
            owned_actor_paths=owned_actor_paths,
        )
        support_profile = _save_support_profile_from_actor(
            repo_root,
            support_reference=support_reference,
            support_z=support_z,
        )
        if session_path is not None:
            upsert_slot_record(
                session_path,
                zone_id=zone_id,
                managed_slot=managed_slot,
                action_name=action_name,
                identity_policy=identity_policy,
                actor_label=str(normalized_actor.get("label") or ""),
                actor_path=str(normalized_actor.get("actor_path") or actor_identifier),
                asset_path=str(action.get("asset_path") or (registry_record or {}).get("asset_path") or ""),
                support_reference=support_reference,
                placement_phase=str(placement_hint.get("placement_phase") or ""),
                last_confirmed_transform=_transform_snapshot(normalized_actor),
                fit_status={
                    "support_surface_fit_state": normalized_actor.get("support_surface_fit_state"),
                    "orientation_candidate": normalized_actor.get("orientation_candidate"),
                    "reconciliation_status": reconciliation.get("reconciliation_status"),
                    "drift_status": reconciliation.get("drift_status"),
                    "interference_status": interference_report.get("interference_status"),
                    "blocking_interference_count": interference_report.get("blocking_interference_count"),
                    "duplicate_count": interference_report.get("duplicate_count"),
                    "mount_type": mount_type,
                    "expected_mount_type": str(placement_hint.get("expected_mount_type") or mount_type),
                },
                registry_status=registry_status,
            )
        select_result, focus_result = _finalize_editor_state(
            repo_root,
            actor_identifier=actor_identifier,
            previous_selection=previous_selection,
            auto_select_after_apply=bool(settings.get("auto_select_after_apply", True)),
            auto_focus_after_apply=bool(settings.get("auto_focus_after_apply", False)),
        )
        save_result = _save_level_if_requested(repo_root, auto_save)
        return {
            "status": "ok",
            "backend": "uefn_mcp_apply",
            "applied_mode": "uefn_mcp_apply",
            "degraded_to_fallback": False,
            "applied": True,
            "action": action_name,
            "placement_phase": placement_hint.get("placement_phase"),
            "snap_policy": placement_hint.get("snap_policy"),
            "managed_slot": managed_slot,
            "identity_policy": identity_policy,
            "actor": normalized_actor,
            "registry_status": registry_status,
            "reconciled_actor_path": reconciliation.get("reconciled_actor_path"),
            "reconciliation_attempted": reconciliation.get("reconciliation_attempted"),
            "reconciliation_status": reconciliation.get("reconciliation_status"),
            "drift_status": reconciliation.get("drift_status"),
            "support_reference": support_reference,
            "support_profile": support_profile,
            "support_surface_adjustment": support_surface_adjustment,
            "orientation_adjustment": orientation_adjustment,
            "forced_transform": forced_transform,
            "reconciliation": reconciliation,
            "interference_report": interference_report,
            "select_result": select_result,
            "focus_result": focus_result,
            "save_result": save_result,
        }

    return {
        "status": "skipped",
        "backend": "uefn_mcp_apply",
        "applied_mode": "uefn_mcp_apply",
        "degraded_to_fallback": False,
        "applied": False,
        "reason": f"Unsupported live action: {action_name}",
    }


def deploy_listener_files(repo_root: Path, destination_root: Path | None = None) -> dict[str, Any]:
    settings = mcp_settings(repo_root)
    target_root = destination_root or mcp_content_python_root(repo_root)
    if target_root is None:
        raise ValueError("Could not determine the UEFN Content/Python directory.")
    target_root.mkdir(parents=True, exist_ok=True)
    listener_path = target_root / "uefn_listener.py"
    bridge_init_path = target_root / "uefn_mcp_init.py"
    _write_atomic_text(listener_path, settings["listener_source_path"].read_text(encoding="utf-8"))
    _write_atomic_text(bridge_init_path, settings["init_source_path"].read_text(encoding="utf-8"))
    init_path = write_shared_init_script(target_root)
    return {
        "content_python_root": str(target_root),
        "listener_path": str(listener_path),
        "bridge_init_path": str(bridge_init_path),
        "init_path": str(init_path),
        "listener_exists": listener_path.exists(),
        "bridge_init_exists": bridge_init_path.exists(),
        "init_exists": init_path.exists(),
    }


def write_client_config(repo_root: Path, output_path: Path | None = None) -> Path:
    settings = mcp_settings(repo_root)
    target_path = (output_path or settings["client_config_path"]).resolve()
    payload = {
        "mcpServers": {
            "uefn": {
                "command": sys.executable,
                "args": [str(settings["server_path"])],
                "env": {
                    "UEFN_MCP_PORT": str(settings["default_port"]),
                },
            }
        }
    }
    _write_atomic_text(target_path, json.dumps(payload, indent=2))
    return target_path


def mcp_status_summary(repo_root: Path) -> dict[str, Any]:
    settings = mcp_settings(repo_root)
    deployed = mcp_listener_deployed(repo_root)
    port = discover_listener_port(repo_root)
    listener_info: dict[str, Any] = {}
    if port is not None:
        try:
            listener_info = _http_get_json(f"http://127.0.0.1:{port}", timeout=1.0)
        except Exception as exc:  # noqa: BLE001
            listener_info = {"status": "error", "error": str(exc)}
    return {
        "enabled": settings["enabled"],
        "package_installed": mcp_package_installed(),
        "listener_deployed": deployed["ready"],
        "listener_running": port is not None,
        "listener_port": port,
        "paths": {
            "vendor_root": str(settings["repo_root"]),
            "server_path": str(settings["server_path"]),
            "listener_source_path": str(settings["listener_source_path"]),
            "init_source_path": str(settings["init_source_path"]),
            "client_config_path": str(settings["client_config_path"]),
            "content_python_root": deployed["content_python_root"],
            "listener_path": deployed["listener_path"],
            "bridge_init_path": deployed["bridge_init_path"],
            "init_path": deployed["init_path"],
        },
        "listener_info": listener_info,
    }
