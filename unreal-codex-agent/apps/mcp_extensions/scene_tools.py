from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import typer

from apps.integrations.uefn_backend import choose_scene_backend, latest_scene_state_export_path
from apps.placement.support_surfaces import (
    actor_origin_and_extent,
    actor_text,
    actor_tokens,
    compatible_support_kinds,
    is_support_kind_compatible,
    safe_float,
    safe_triplet,
    support_anchor_for_actor,
    support_kind_for_actor,
    support_kind_priority,
    support_level_for_actor,
)
from apps.placement.placement_solver import MOUNT_KEYWORDS, infer_expected_mount_type, placement_context
from apps.orchestrator.dirty_zone import DirtyZoneDetector
from apps.orchestrator.state_store import SessionStateStore

app = typer.Typer(help="Scene-state helpers for local tooling and MCP-style workflows.")
SUPPORT_SURFACE_NEGATIVE_KEYWORDS = {
    "spawn",
    "spawner",
    "playerstart",
    "player",
    "beacon",
    "device",
    "islandsettings",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def _load_project_defaults(repo_root: Path) -> dict[str, Any]:
    project_path = repo_root / "config" / "project.json"
    if not project_path.exists():
        return {}
    try:
        return _load_json(project_path)
    except Exception:
        return {}


def _load_room_taxonomy(repo_root: Path) -> dict[str, Any]:
    taxonomy_path = repo_root / "config" / "room_taxonomy.json"
    if not taxonomy_path.exists():
        return {}
    try:
        return _load_json(taxonomy_path)
    except Exception:
        return {}


def _known_room_types(repo_root: Path) -> set[str]:
    taxonomy = _load_room_taxonomy(repo_root)
    known: set[str] = set()

    rooms = taxonomy.get("rooms", [])
    if isinstance(rooms, list):
        known.update(str(room) for room in rooms if room)

    top_level_groups = taxonomy.get("top_level_groups", {})
    if isinstance(top_level_groups, dict):
        for values in top_level_groups.values():
            if isinstance(values, list):
                known.update(str(room) for room in values if room)

    aliases = taxonomy.get("aliases", {})
    if isinstance(aliases, dict):
        known.update(str(room) for room in aliases.values() if room)

    if not known:
        known.update({"living_room", "bedroom", "kitchen", "bathroom", "office"})
    return known


def _guess_room_type_from_map_name(map_name: str, repo_root: Path) -> str | None:
    known = sorted(_known_room_types(repo_root), key=len, reverse=True)
    normalized = map_name.strip().lower()
    for room_type in known:
        if room_type.lower() in normalized:
            return room_type
    return None


def _default_room_type(repo_root: Path) -> str:
    project = _load_project_defaults(repo_root)
    value = project.get("default_room_type")
    if value:
        return str(value)
    orchestrator = project.get("orchestrator", {})
    if isinstance(orchestrator, dict) and orchestrator.get("default_room_type"):
        return str(orchestrator["default_room_type"])
    return "living_room"


def _fallback_clearance_observations(room_type: str, shell_sensitive: bool) -> dict[str, Any]:
    room_key = (room_type or "living_room").strip().lower()
    if shell_sensitive:
        values = {"front_cm": 75.0, "side_cm": 20.0, "back_cm": 8.0}
    elif room_key in {"kitchen", "bathroom", "powder_room", "pantry"}:
        values = {"front_cm": 65.0, "side_cm": 16.0, "back_cm": 6.0}
    elif room_key in {"office", "bedroom"}:
        values = {"front_cm": 80.0, "side_cm": 24.0, "back_cm": 8.0}
    else:
        values = {"front_cm": 90.0, "side_cm": 28.0, "back_cm": 8.0}
    values["source"] = "fallback_estimate"
    return values


def _actor_match_score(actor: dict[str, Any], expected_mount_type: str) -> int:
    text = actor_text(actor)
    tokens = actor_tokens(actor)
    keywords = MOUNT_KEYWORDS.get(expected_mount_type, set())
    score = sum(1 for keyword in keywords if keyword in text or keyword in tokens)
    if expected_mount_type in {"floor", "surface", "exterior_ground"}:
        score += _support_actor_score(actor)
    if expected_mount_type == "wall" and "opening" in text:
        score += 1
    if expected_mount_type == "opening" and ("door" in text or "window" in text):
        score += 2
    if expected_mount_type == "corner" and "corner" in text:
        score += 3
    if expected_mount_type == "roof" and "roof" in text:
        score += 3
    return score


def _support_level(actor: dict[str, Any]) -> int:
    return support_level_for_actor(actor)


def _support_actor_score(actor: dict[str, Any]) -> int:
    text = actor_text(actor)
    tokens = actor_tokens(actor)
    origin, extent = actor_origin_and_extent(actor)
    support_kind = support_kind_for_actor(actor) or ""
    del origin
    footprint = max(abs(extent[0]), abs(extent[1]))
    thickness = abs(extent[2])
    score = 0
    if "landscapestreamingproxy" in text or "landscapestreamingproxy" in tokens:
        score += 30
    if "landscape" in text or "landscape" in tokens:
        score += 20
    if "terrain" in text or "terrain" in tokens:
        score += 16
    if "gridplane" in text or "gridplane" in tokens:
        score += 28
    if "grid" in tokens:
        score += 12
    if "asphalt" in tokens:
        score += 8
    if support_kind == "landscape":
        score += 18
    elif support_kind == "upper_slab":
        score += 16
    elif support_kind == "balcony":
        score += 12
    elif support_kind == "support_surface":
        score += 10
    elif support_kind in {"wall_surface", "roof_surface", "ceiling_surface"}:
        score += 6
    if footprint >= 2048.0:
        score += 18
    elif footprint >= 512.0:
        score += 10
    elif footprint >= 128.0:
        score += 4
    elif footprint >= 64.0:
        score += 2
    if footprint > 0 and thickness <= max(footprint * 0.35, 64.0):
        score += 2
    if footprint > 0 and thickness <= max(footprint * 0.05, 32.0):
        score += 10
    if bool(actor.get("selected", False)) and footprint >= 512.0 and thickness <= max(footprint * 0.05, 32.0):
        score += 20
    score += min(_support_level(actor) * 3, 12)
    if str(actor.get("category") or "").lower() in {"surface", "terrain", "landscape", "architecture", "structural"}:
        score += 2
    if any(keyword in text or keyword in tokens for keyword in SUPPORT_SURFACE_NEGATIVE_KEYWORDS):
        score -= 18
    return score


def _distance_xy(a: list[float], b: list[float]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _stable_actor_identity(actor: dict[str, Any]) -> str:
    return str(
        actor.get("actor_path")
        or actor.get("label")
        or actor.get("actor_name")
        or actor.get("asset_path")
        or actor.get("class_name")
        or ""
    ).lower()


def _select_support_actor(
    actors: list[dict[str, Any]],
    *,
    target_location: list[float] | None = None,
    reference_actors: list[dict[str, Any]] | None = None,
    expected_mount_type: str = "floor",
) -> tuple[dict[str, Any] | None, str]:
    reference_actor_keys = {_stable_actor_identity(actor) for actor in list(reference_actors or []) if isinstance(actor, dict)}
    compatible_kinds = compatible_support_kinds(expected_mount_type)
    best_actor: dict[str, Any] | None = None
    best_key: tuple[int, int, float, str] | None = None
    best_score: int | None = None
    for actor in actors:
        if not isinstance(actor, dict):
            continue
        support_kind = support_kind_for_actor(actor)
        if support_kind is None:
            continue
        if compatible_kinds and not is_support_kind_compatible(expected_mount_type, support_kind):
            continue
        score = _support_actor_score(actor)
        if score <= 0:
            continue
        actor_key = _stable_actor_identity(actor)
        source_priority = 2
        if bool(actor.get("selected", False)):
            source_priority = 0
        elif actor_key in reference_actor_keys:
            source_priority = 1
        kind_priority = support_kind_priority(expected_mount_type, support_kind)
        distance_penalty = 0.0
        if target_location is not None:
            origin, extent = actor_origin_and_extent(actor)
            surface_anchor = [origin[0], origin[1], origin[2] + extent[2]]
            distance_penalty = _distance_xy(surface_anchor, target_location)
        key = (source_priority, kind_priority, round(distance_penalty, 3), actor_key)
        if best_key is None or key < best_key or (key == best_key and score > (best_score or -999999)):
            best_key = key
            best_actor = actor
            best_score = score
    if best_key is None:
        return None, "fallback_bounds"
    if bool(best_actor.get("selected", False)):
        return best_actor, "selected_actor"
    if _stable_actor_identity(best_actor) in reference_actor_keys:
        return best_actor, "dirty_zone_reference_actor"
    return best_actor, "nearest_structural_support"


def _select_reference_actors(actors: list[dict[str, Any]], expected_mount_type: str) -> list[dict[str, Any]]:
    selected = [actor for actor in actors if bool(actor.get("selected", False))]
    if selected:
        return sorted(selected, key=_stable_actor_identity)[:4]
    scored: list[tuple[int, dict[str, Any]]] = []
    for actor in actors:
        if not isinstance(actor, dict):
            continue
        scored.append((_actor_match_score(actor, expected_mount_type), actor))
    scored.sort(key=lambda item: (-item[0], _stable_actor_identity(item[1])))
    matched = [actor for score, actor in scored if score > 0]
    if matched:
        return matched[:4]
    return [actor for _, actor in scored[:4]]


def _aggregate_bounds(reference_actors: list[dict[str, Any]]) -> dict[str, Any]:
    if not reference_actors:
        return {}
    min_corner: list[float] | None = None
    max_corner: list[float] | None = None
    for actor in reference_actors:
        origin, extent = actor_origin_and_extent(actor)
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
    return {
        "origin": [round(value, 3) for value in origin],
        "box_extent": [round(value, 3) for value in extent],
    }


def _derive_spatial_targets(scene_state: dict[str, Any], expected_mount_type: str) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    actors = [actor for actor in (scene_state.get("actors") or []) if isinstance(actor, dict)]
    reference_actors = _select_reference_actors(actors, expected_mount_type)
    target_location = None
    if reference_actors:
        target_location = safe_triplet(reference_actors[0].get("location"), [0.0, 0.0, 0.0])
    support_actor, support_reference_source = _select_support_actor(
        actors,
        target_location=target_location,
        reference_actors=reference_actors,
        expected_mount_type=expected_mount_type,
    )
    if expected_mount_type in {"floor", "surface", "exterior_ground"} and support_actor is not None:
        reference_actors = [support_actor] + [actor for actor in reference_actors if actor is not support_actor]
    dirty_actor_ids = [
        str(actor.get("label") or actor.get("actor_name") or "")
        for actor in reference_actors
        if str(actor.get("label") or actor.get("actor_name") or "").strip()
    ]
    aggregated_bounds = _aggregate_bounds(reference_actors)
    if not reference_actors:
        return dirty_actor_ids, aggregated_bounds, {}

    reference_actor = reference_actors[0]
    reference_location = safe_triplet(reference_actor.get("location"), aggregated_bounds.get("origin", [0.0, 0.0, 0.0]))
    reference_rotation = safe_triplet(reference_actor.get("rotation"), [0.0, 0.0, 0.0])
    targets: dict[str, Any] = {
        "anchor_point": [round(value, 3) for value in reference_location],
        "reference_yaw_deg": round(reference_rotation[2], 3),
        "reference_pitch_deg": round(reference_rotation[1], 3),
        "reference_actor_label": reference_actor.get("label") or reference_actor.get("actor_name"),
        "reference_actor_count": len(reference_actors),
        "support_reference_source": support_reference_source,
    }
    if support_actor is not None:
        support_anchor = support_anchor_for_actor(support_actor)
        support_kind = support_kind_for_actor(support_actor) or "support_surface"
        targets["support_surface_kind"] = support_kind
        targets["support_level"] = _support_level(support_actor)
        targets["support_actor_label"] = support_actor.get("label") or support_actor.get("actor_name")
        targets["support_actor_path"] = support_actor.get("actor_path")
        targets["support_actor_class"] = support_actor.get("class_name")
        targets["parent_support_actor"] = support_actor.get("label") or support_actor.get("actor_name")
        if support_kind == "landscape":
            targets["landscape_anchor"] = list(support_anchor)
            targets["ground_anchor"] = list(support_anchor)
        else:
            targets["surface_anchor"] = list(support_anchor)
    if expected_mount_type in {"wall", "opening"}:
        targets["plane_anchor"] = [round(value, 3) for value in reference_location]
    if expected_mount_type == "corner":
        targets["corner_anchor"] = [round(value, 3) for value in reference_location]
    if expected_mount_type in {"ceiling", "roof"}:
        origin = safe_triplet(aggregated_bounds.get("origin"), reference_location)
        extent = safe_triplet(aggregated_bounds.get("box_extent"), [0.0, 0.0, 0.0])
        targets["surface_anchor"] = [round(origin[0], 3), round(origin[1], 3), round(origin[2] + extent[2], 3)]
    return dirty_actor_ids, aggregated_bounds, targets


def _build_support_graph(actors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    graph: list[dict[str, Any]] = []
    for actor in actors:
        if not isinstance(actor, dict):
            continue
        support_kind = support_kind_for_actor(actor)
        if support_kind is None:
            continue
        origin, extent = actor_origin_and_extent(actor)
        graph.append(
            {
                "actor_label": actor.get("label") or actor.get("actor_name"),
                "actor_path": actor.get("actor_path"),
                "class_name": actor.get("class_name"),
                "support_surface_kind": support_kind,
                "support_level": _support_level(actor),
                "selected": bool(actor.get("selected", False)),
                "surface_anchor": support_anchor_for_actor(actor),
                "footprint_cm": [
                    round(float(extent[0]) * 2.0, 3),
                    round(float(extent[1]) * 2.0, 3),
                ],
                "thickness_cm": round(float(extent[2]) * 2.0, 3),
            }
        )
    graph.sort(
        key=lambda entry: (
            0 if bool(entry.get("selected")) else 1,
            int(entry.get("support_level") or 0),
            str(entry.get("actor_path") or entry.get("actor_label") or "").lower(),
        )
    )
    return graph


def enrich_scene_state(scene_state: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    enriched = dict(scene_state) if isinstance(scene_state, dict) else {}
    map_name = str(enriched.get("map_name") or "UnknownMap")
    room_type = str(enriched.get("room_type") or "").strip()
    if not room_type or room_type == "unknown":
        room_type = _guess_room_type_from_map_name(map_name, repo_root) or _default_room_type(repo_root)
    enriched["room_type"] = room_type
    shell_sensitive = bool(enriched.get("shell_sensitive", False))

    actors_value = enriched.get("actors") or []
    actors = list(actors_value) if isinstance(actors_value, list) else []
    enriched_actors: list[dict[str, Any]] = []
    for actor in actors:
        if not isinstance(actor, dict):
            continue
        actor_copy = dict(actor)
        actor_room_type = str(actor_copy.get("room_type") or "").strip()
        if not actor_room_type or actor_room_type == "unknown":
            actor_copy["room_type"] = room_type
        support_kind = support_kind_for_actor(actor_copy)
        if support_kind is not None:
            actor_copy["support_surface_kind"] = support_kind
            actor_copy["support_level"] = support_level_for_actor(actor_copy)
            actor_copy["support_anchor"] = support_anchor_for_actor(actor_copy)
        enriched_actors.append(actor_copy)
    enriched["actors"] = enriched_actors

    expected_mount_type = str(enriched.get("expected_mount_type") or infer_expected_mount_type(enriched))
    derived_dirty_actor_ids, derived_bounds, derived_targets = _derive_spatial_targets(enriched, expected_mount_type)
    if not enriched.get("dirty_actor_ids"):
        enriched["dirty_actor_ids"] = derived_dirty_actor_ids
    else:
        enriched["dirty_actor_ids"] = list(enriched.get("dirty_actor_ids") or [])
    dirty_bounds = dict(enriched.get("dirty_bounds") or {})
    if not dirty_bounds:
        dirty_bounds = dict(derived_bounds)
    for key, value in derived_targets.items():
        dirty_bounds.setdefault(key, value)
    enriched["dirty_bounds"] = dirty_bounds
    enriched["placement_targets"] = {
        key: dirty_bounds.get(key)
        for key in (
            "anchor_point",
            "ground_anchor",
            "landscape_anchor",
            "plane_anchor",
            "corner_anchor",
            "surface_anchor",
            "reference_yaw_deg",
            "reference_pitch_deg",
            "reference_actor_label",
            "reference_actor_count",
            "support_actor_label",
            "support_actor_path",
            "support_actor_class",
            "support_surface_kind",
            "support_level",
            "parent_support_actor",
            "support_reference_source",
        )
        if dirty_bounds.get(key) is not None
    }
    support_graph = _build_support_graph(enriched_actors)
    if support_graph:
        enriched["support_graph"] = support_graph
    if dirty_bounds.get("surface_anchor") is not None or dirty_bounds.get("ground_anchor") is not None:
        enriched["placement_reference_quality"] = "derived_support_surface"
    else:
        enriched["placement_reference_quality"] = "derived_actor_reference" if derived_targets else "fallback_bounds"
    enriched.setdefault("shell_sensitive", False)
    observations = dict(enriched.get("clearance_observations") or {})
    if not observations:
        observations = _fallback_clearance_observations(room_type, shell_sensitive)
    else:
        observations.setdefault("source", "scene_state")
    enriched["clearance_observations"] = observations
    enriched.setdefault(
        "shell_alignment",
        {
            "inside_checked": False,
            "outside_checked": False,
            "is_consistent": None,
        },
    )
    enriched.setdefault("collision_issues", [])
    enriched["expected_mount_type"] = expected_mount_type
    enriched["placement_context"] = placement_context(scene_state=enriched, dirty_zone=None, asset_record=None)
    enriched["timestamp_utc"] = str(enriched.get("timestamp_utc") or SessionStateStore.utcnow_static())
    return enriched


def load_scene_state_for_context(repo_root: Path) -> dict[str, Any]:
    try:
        backend = choose_scene_backend(repo_root)
    except Exception:
        backend = "fallback"

    if backend == "uefn_session_export":
        export_path = latest_scene_state_export_path(repo_root)
        if export_path.exists():
            try:
                raw = _load_json(export_path)
            except Exception:
                backend = "fallback"
                raw = {
                    "map_name": "UnknownMap",
                    "actors": [],
                    "dirty_actor_ids": [],
                    "dirty_bounds": {},
                    "room_type": "unknown",
                    "shell_sensitive": False,
                    "clearance_observations": {},
                    "shell_alignment": {
                        "inside_checked": False,
                        "outside_checked": False,
                        "is_consistent": None,
                    },
                    "collision_issues": [],
                    "backend_notes": ["UEFN scene-state export was malformed, used fallback"],
                }
        else:
            backend = "fallback"
            raw = {
                "map_name": "UnknownMap",
                "actors": [],
                "dirty_actor_ids": [],
                "dirty_bounds": {},
                "room_type": "unknown",
                "shell_sensitive": False,
                "clearance_observations": {},
                "shell_alignment": {
                    "inside_checked": False,
                    "outside_checked": False,
                    "is_consistent": None,
                },
                "collision_issues": [],
                "backend_notes": [f"UEFN scene-state export not found at {export_path}, used fallback"],
            }
    elif backend == "uefn_mcp":
        try:
            from apps.integrations.uefn_mcp import collect_scene_state

            raw = collect_scene_state(repo_root)
        except Exception:
            backend = "fallback"
            raw = {
                "map_name": "UnknownMap",
                "actors": [],
                "dirty_actor_ids": [],
                "dirty_bounds": {},
                "room_type": "unknown",
                "shell_sensitive": False,
                "clearance_observations": {},
                "shell_alignment": {
                    "inside_checked": False,
                    "outside_checked": False,
                    "is_consistent": None,
                },
                "collision_issues": [],
                "backend_notes": ["uefn_mcp backend failed, used fallback"],
            }
    elif backend == "unreal_python":
        try:
            from unreal.python.ue_scene_state import export_scene_state

            raw = export_scene_state()
        except Exception:
            backend = "fallback"
            raw = {
                "map_name": "UnknownMap",
                "actors": [],
                "dirty_actor_ids": [],
                "dirty_bounds": {},
                "room_type": "unknown",
                "shell_sensitive": False,
                "clearance_observations": {},
                "shell_alignment": {
                    "inside_checked": False,
                    "outside_checked": False,
                    "is_consistent": None,
                },
                "collision_issues": [],
                "backend_notes": ["unreal_python backend failed, used fallback"],
            }
    else:
        raw = {
            "map_name": "UnknownMap",
            "actors": [],
            "dirty_actor_ids": [],
            "dirty_bounds": {},
            "room_type": "unknown",
            "shell_sensitive": False,
            "clearance_observations": {},
            "shell_alignment": {
                "inside_checked": False,
                "outside_checked": False,
                "is_consistent": None,
            },
            "collision_issues": [],
            "backend_notes": [f"{backend} backend not directly embedded, used fallback"],
        }
    enriched = enrich_scene_state(raw, repo_root)
    enriched["scene_state_backend"] = backend
    enriched["runtime_platform"] = "uefn"
    return enriched


def derive_dirty_zone(scene_state: dict[str, Any], cycle_number: int) -> dict[str, Any]:
    try:
        zone = DirtyZoneDetector().detect(scene_state=scene_state, cycle_number=cycle_number)
    except Exception:
        zone = DirtyZoneDetector().detect(
            scene_state={
                "dirty_actor_ids": [],
                "room_type": scene_state.get("room_type", "unknown") if isinstance(scene_state, dict) else "unknown",
                "shell_sensitive": bool(scene_state.get("shell_sensitive", False)) if isinstance(scene_state, dict) else False,
                "dirty_bounds": {},
            },
            cycle_number=cycle_number,
        )
    return zone.to_dict()


@app.command("scene-state")
def scene_state_command(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
) -> None:
    try:
        payload = load_scene_state_for_context(repo_root)
    except Exception as exc:  # noqa: BLE001
        payload = enrich_scene_state({}, repo_root)
        payload["scene_state_backend"] = "fallback"
        payload["backend_notes"] = list(payload.get("backend_notes", [])) + [f"scene-state helper failed open: {exc}"]
    typer.echo(json.dumps(payload, indent=2))


@app.command("dirty-zone")
def dirty_zone_command(
    scene_state_json: Path = typer.Option(..., help="Path to a saved scene state JSON file."),
    cycle_number: int = typer.Option(1, help="Cycle number used to derive the zone id."),
    repo_root: Path = typer.Option(Path("."), help="Repo root path for enrichment defaults."),
) -> None:
    warnings: list[str] = []
    if scene_state_json.exists():
        try:
            scene_state = enrich_scene_state(_load_json(scene_state_json), repo_root)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"scene state could not be parsed cleanly: {exc}")
            scene_state = enrich_scene_state({}, repo_root)
    else:
        warnings.append(f"scene state file not found: {scene_state_json}")
        scene_state = enrich_scene_state({}, repo_root)

    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "dirty_zone": derive_dirty_zone(scene_state=scene_state, cycle_number=cycle_number),
                "warnings": warnings,
            },
            indent=2,
        )
    )


def scene_tools() -> list[str]:
    return ["scene-state", "dirty-zone"]


if __name__ == "__main__":
    app()
