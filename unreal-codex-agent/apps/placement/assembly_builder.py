from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from apps.placement.support_surfaces import actor_origin_and_extent, support_kind_for_actor, support_level_for_actor

CUBE_SIZE_CM = 100.0
IGNORED_STRUCTURE_LABELS = {"LevelBounds", "IslandSettings0"}
IGNORED_STRUCTURE_CLASSES = {"LevelBounds", "Device_ExperienceSettings_V2_UEFN_C"}


def _snap(value: float, grid_cm: float) -> float:
    if grid_cm <= 0.0:
        return round(float(value), 3)
    return round(round(float(value) / grid_cm) * grid_cm, 3)


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class BoxRoomSpec:
    zone_id: str
    center_x: float
    center_y: float
    support_z: float
    inner_width_cm: float = 400.0
    inner_depth_cm: float = 400.0
    wall_height_cm: float = 300.0
    wall_thickness_cm: float = 20.0
    door_width_cm: float = 140.0
    door_height_cm: float = 220.0
    grid_snap_cm: float = 10.0
    asset_path: str = "/Engine/BasicShapes/Cube.Cube"
    label_prefix: str = "UCA_BoxRoom"
    mount_type: str = "floor"
    support_surface_kind: str = "support_surface"
    support_level: int = 0
    support_actor_label: str = ""
    parent_support_actor: str = ""
    support_reference_policy: str = "explicit_only"
    corner_join_style: str = "butt_join"
    grid_safe_joints: bool = True


@dataclass(frozen=True)
class HouseSpec:
    zone_id: str
    center_x: float
    center_y: float
    support_z: float
    inner_width_cm: float = 700.0
    inner_depth_cm: float = 600.0
    story_height_cm: float = 300.0
    wall_thickness_cm: float = 20.0
    floor_thickness_cm: float = 20.0
    door_width_cm: float = 160.0
    door_height_cm: float = 230.0
    roof_pitch_deg: float = 30.0
    roof_thickness_cm: float = 18.0
    roof_overhang_cm: float = 25.0
    roof_rise_cm: float = 120.0
    stair_width_cm: float = 140.0
    stair_step_rise_cm: float = 20.0
    stair_step_run_cm: float = 30.0
    stair_step_count: int = 10
    stair_opening_margin_cm: float = 8.0
    landing_depth_cm: float = 110.0
    stair_guard_height_cm: float = 95.0
    stair_guard_thickness_cm: float = 8.0
    roof_ridge_thickness_cm: float = 8.0
    gable_infill_step_count: int = 4
    grid_snap_cm: float = 10.0
    asset_path: str = "/Engine/BasicShapes/Cube.Cube"
    label_prefix: str = "UCA_House"
    support_surface_kind: str = "support_surface"
    support_level: int = 0
    support_actor_label: str = ""
    parent_support_actor: str = ""
    support_reference_policy: str = "explicit_only"
    corner_join_style: str = "butt_join"
    grid_safe_joints: bool = True


ENCLOSED_GENERATIVE_STRUCTURE_TYPES = {
    "garage",
    "shed",
    "workshop",
    "barn",
    "warehouse",
    "greenhouse",
    "studio",
    "hangar",
    "kiosk",
}

OPEN_GENERATIVE_STRUCTURE_TYPES = {
    "pavilion",
    "gazebo",
    "pergola",
    "canopy",
    "carport",
    "market_stall",
}

SUPPORTED_GENERATIVE_STRUCTURE_TYPES = (
    ENCLOSED_GENERATIVE_STRUCTURE_TYPES | OPEN_GENERATIVE_STRUCTURE_TYPES
)

STRUCTURE_TYPE_ALIASES = {
    "garage": "garage",
    "car garage": "garage",
    "auto garage": "garage",
    "workshop": "workshop",
    "shop": "workshop",
    "barn": "barn",
    "shed": "shed",
    "tool shed": "shed",
    "storage shed": "shed",
    "warehouse": "warehouse",
    "storage building": "warehouse",
    "greenhouse": "greenhouse",
    "glasshouse": "greenhouse",
    "studio": "studio",
    "art studio": "studio",
    "hangar": "hangar",
    "aircraft hangar": "hangar",
    "kiosk": "kiosk",
    "booth": "kiosk",
    "pavilion": "pavilion",
    "gazebo": "gazebo",
    "pergola": "pergola",
    "canopy": "canopy",
    "carport": "carport",
    "market stall": "market_stall",
    "stall": "market_stall",
}


@dataclass(frozen=True)
class StructureSpec:
    zone_id: str
    structure_type: str
    center_x: float
    center_y: float
    support_z: float
    width_cm: float = 720.0
    depth_cm: float = 620.0
    wall_height_cm: float = 280.0
    wall_thickness_cm: float = 20.0
    floor_thickness_cm: float = 20.0
    door_width_cm: float = 120.0
    door_height_cm: float = 220.0
    opening_width_cm: float = 260.0
    opening_height_cm: float = 235.0
    roof_style: str = "gable"
    roof_pitch_deg: float = 28.0
    roof_thickness_cm: float = 18.0
    roof_overhang_cm: float = 24.0
    roof_rise_cm: float = 110.0
    roof_ridge_thickness_cm: float = 8.0
    gable_infill_step_count: int = 3
    post_thickness_cm: float = 20.0
    beam_thickness_cm: float = 14.0
    railing_height_cm: float = 90.0
    grid_snap_cm: float = 10.0
    asset_path: str = "/Engine/BasicShapes/Cube.Cube"
    label_prefix: str = "UCA_Structure"
    support_surface_kind: str = "support_surface"
    support_level: int = 0
    support_actor_label: str = ""
    parent_support_actor: str = ""
    support_reference_policy: str = "explicit_only"
    corner_join_style: str = "butt_join"
    grid_safe_joints: bool = True


def canonical_structure_type(value: Any, fallback: str = "shed") -> str:
    normalized = _safe_text(value).lower()
    if normalized in SUPPORTED_GENERATIVE_STRUCTURE_TYPES:
        return normalized
    return STRUCTURE_TYPE_ALIASES.get(normalized, fallback)


def normalize_box_room_spec(spec: BoxRoomSpec) -> BoxRoomSpec:
    inner_width = max(100.0, _safe_float(spec.inner_width_cm, 400.0))
    inner_depth = max(100.0, _safe_float(spec.inner_depth_cm, 400.0))
    wall_height = max(100.0, _safe_float(spec.wall_height_cm, 300.0))
    wall_thickness = max(10.0, _safe_float(spec.wall_thickness_cm, 20.0))
    max_door_width = max(40.0, inner_width - (wall_thickness * 2.0) - 40.0)
    door_width = min(max_door_width, max(60.0, _safe_float(spec.door_width_cm, 140.0)))
    door_height = min(wall_height - 40.0, max(80.0, _safe_float(spec.door_height_cm, 220.0)))
    corner_join_style = str(spec.corner_join_style or "butt_join").strip().lower()
    if corner_join_style not in {"butt_join", "overlap"}:
        corner_join_style = "butt_join"
    return BoxRoomSpec(
        zone_id=str(spec.zone_id or "zone_box_room"),
        center_x=_snap(_safe_float(spec.center_x, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        center_y=_snap(_safe_float(spec.center_y, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        support_z=_snap(_safe_float(spec.support_z, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        inner_width_cm=inner_width,
        inner_depth_cm=inner_depth,
        wall_height_cm=wall_height,
        wall_thickness_cm=wall_thickness,
        door_width_cm=door_width,
        door_height_cm=door_height,
        grid_snap_cm=max(0.0, _safe_float(spec.grid_snap_cm, 10.0)),
        asset_path=str(spec.asset_path or "/Engine/BasicShapes/Cube.Cube"),
        label_prefix=str(spec.label_prefix or "UCA_BoxRoom"),
        mount_type=str(spec.mount_type or "floor"),
        support_surface_kind=str(spec.support_surface_kind or "support_surface"),
        support_level=int(spec.support_level or 0),
        support_actor_label=str(spec.support_actor_label or ""),
        parent_support_actor=str(spec.parent_support_actor or spec.support_actor_label or ""),
        support_reference_policy=str(spec.support_reference_policy or "explicit_only"),
        corner_join_style=corner_join_style,
        grid_safe_joints=bool(spec.grid_safe_joints),
    )


def normalize_house_spec(spec: HouseSpec) -> HouseSpec:
    inner_width = max(300.0, _safe_float(spec.inner_width_cm, 700.0))
    inner_depth = max(300.0, _safe_float(spec.inner_depth_cm, 600.0))
    story_height = max(220.0, _safe_float(spec.story_height_cm, 300.0))
    wall_thickness = max(10.0, _safe_float(spec.wall_thickness_cm, 20.0))
    floor_thickness = max(10.0, _safe_float(spec.floor_thickness_cm, 20.0))
    max_door_width = max(80.0, inner_width - (wall_thickness * 2.0) - 80.0)
    door_width = min(max_door_width, max(100.0, _safe_float(spec.door_width_cm, 160.0)))
    door_height = min(story_height - 30.0, max(120.0, _safe_float(spec.door_height_cm, 230.0)))
    roof_pitch_deg = max(10.0, min(55.0, _safe_float(spec.roof_pitch_deg, 30.0)))
    roof_thickness = max(8.0, _safe_float(spec.roof_thickness_cm, 18.0))
    roof_overhang = max(0.0, _safe_float(spec.roof_overhang_cm, 25.0))
    roof_rise = max(40.0, _safe_float(spec.roof_rise_cm, 120.0))
    stair_width = max(80.0, min(inner_width - 60.0, _safe_float(spec.stair_width_cm, 140.0)))
    stair_step_rise = max(10.0, _safe_float(spec.stair_step_rise_cm, 20.0))
    stair_step_run = max(20.0, _safe_float(spec.stair_step_run_cm, 30.0))
    stair_step_count = max(6, min(24, int(spec.stair_step_count or 10)))
    stair_opening_margin = max(4.0, _safe_float(spec.stair_opening_margin_cm, 8.0))
    landing_depth = max(90.0, _safe_float(spec.landing_depth_cm, 110.0))
    stair_guard_height = max(60.0, _safe_float(spec.stair_guard_height_cm, 95.0))
    stair_guard_thickness = max(4.0, _safe_float(spec.stair_guard_thickness_cm, 8.0))
    roof_ridge_thickness = max(4.0, _safe_float(spec.roof_ridge_thickness_cm, 8.0))
    gable_infill_step_count = max(2, min(8, int(spec.gable_infill_step_count or 4)))
    corner_join_style = str(spec.corner_join_style or "butt_join").strip().lower()
    if corner_join_style not in {"butt_join", "overlap"}:
        corner_join_style = "butt_join"
    return HouseSpec(
        zone_id=str(spec.zone_id or "zone_house"),
        center_x=_snap(_safe_float(spec.center_x, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        center_y=_snap(_safe_float(spec.center_y, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        support_z=_snap(_safe_float(spec.support_z, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        inner_width_cm=inner_width,
        inner_depth_cm=inner_depth,
        story_height_cm=story_height,
        wall_thickness_cm=wall_thickness,
        floor_thickness_cm=floor_thickness,
        door_width_cm=door_width,
        door_height_cm=door_height,
        roof_pitch_deg=roof_pitch_deg,
        roof_thickness_cm=roof_thickness,
        roof_overhang_cm=roof_overhang,
        roof_rise_cm=roof_rise,
        stair_width_cm=stair_width,
        stair_step_rise_cm=stair_step_rise,
        stair_step_run_cm=stair_step_run,
        stair_step_count=stair_step_count,
        stair_opening_margin_cm=stair_opening_margin,
        landing_depth_cm=landing_depth,
        stair_guard_height_cm=stair_guard_height,
        stair_guard_thickness_cm=stair_guard_thickness,
        roof_ridge_thickness_cm=roof_ridge_thickness,
        gable_infill_step_count=gable_infill_step_count,
        grid_snap_cm=max(0.0, _safe_float(spec.grid_snap_cm, 10.0)),
        asset_path=str(spec.asset_path or "/Engine/BasicShapes/Cube.Cube"),
        label_prefix=str(spec.label_prefix or "UCA_House"),
        support_surface_kind=str(spec.support_surface_kind or "support_surface"),
        support_level=int(spec.support_level or 0),
        support_actor_label=str(spec.support_actor_label or ""),
        parent_support_actor=str(spec.parent_support_actor or spec.support_actor_label or ""),
        support_reference_policy=str(spec.support_reference_policy or "explicit_only"),
        corner_join_style=corner_join_style,
        grid_safe_joints=bool(spec.grid_safe_joints),
    )


def normalize_structure_spec(spec: StructureSpec) -> StructureSpec:
    structure_type = canonical_structure_type(spec.structure_type, fallback="shed")
    width_cm = max(260.0, _safe_float(spec.width_cm, 720.0))
    depth_cm = max(260.0, _safe_float(spec.depth_cm, 620.0))
    wall_height_cm = max(180.0, _safe_float(spec.wall_height_cm, 280.0))
    wall_thickness_cm = max(8.0, _safe_float(spec.wall_thickness_cm, 20.0))
    floor_thickness_cm = max(8.0, _safe_float(spec.floor_thickness_cm, 20.0))
    door_width_cm = max(80.0, min(width_cm - 80.0, _safe_float(spec.door_width_cm, 120.0)))
    door_height_cm = max(120.0, min(wall_height_cm - 20.0, _safe_float(spec.door_height_cm, 220.0)))
    opening_width_cm = max(120.0, min(width_cm - 60.0, _safe_float(spec.opening_width_cm, 260.0)))
    opening_height_cm = max(140.0, min(wall_height_cm - 12.0, _safe_float(spec.opening_height_cm, 235.0)))
    roof_style = _safe_text(spec.roof_style).lower() or "gable"
    if structure_type == "pergola":
        roof_style = "beam"
    elif roof_style not in {"gable", "beam"}:
        roof_style = "gable"
    roof_pitch_deg = max(8.0, min(50.0, _safe_float(spec.roof_pitch_deg, 28.0)))
    roof_thickness_cm = max(6.0, _safe_float(spec.roof_thickness_cm, 18.0))
    roof_overhang_cm = max(0.0, _safe_float(spec.roof_overhang_cm, 24.0))
    roof_rise_cm = max(30.0, _safe_float(spec.roof_rise_cm, 110.0))
    roof_ridge_thickness_cm = max(4.0, _safe_float(spec.roof_ridge_thickness_cm, 8.0))
    gable_infill_step_count = max(2, min(6, int(spec.gable_infill_step_count or 3)))
    post_thickness_cm = max(10.0, _safe_float(spec.post_thickness_cm, 20.0))
    beam_thickness_cm = max(8.0, _safe_float(spec.beam_thickness_cm, 14.0))
    railing_height_cm = max(60.0, _safe_float(spec.railing_height_cm, 90.0))
    corner_join_style = _safe_text(spec.corner_join_style).lower() or "butt_join"
    if corner_join_style not in {"butt_join", "overlap"}:
        corner_join_style = "butt_join"
    return StructureSpec(
        zone_id=_safe_text(spec.zone_id) or "zone_structure",
        structure_type=structure_type,
        center_x=_snap(_safe_float(spec.center_x, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        center_y=_snap(_safe_float(spec.center_y, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        support_z=_snap(_safe_float(spec.support_z, 0.0), max(0.0, _safe_float(spec.grid_snap_cm, 10.0))),
        width_cm=width_cm,
        depth_cm=depth_cm,
        wall_height_cm=wall_height_cm,
        wall_thickness_cm=wall_thickness_cm,
        floor_thickness_cm=floor_thickness_cm,
        door_width_cm=door_width_cm,
        door_height_cm=door_height_cm,
        opening_width_cm=opening_width_cm,
        opening_height_cm=opening_height_cm,
        roof_style=roof_style,
        roof_pitch_deg=roof_pitch_deg,
        roof_thickness_cm=roof_thickness_cm,
        roof_overhang_cm=roof_overhang_cm,
        roof_rise_cm=roof_rise_cm,
        roof_ridge_thickness_cm=roof_ridge_thickness_cm,
        gable_infill_step_count=gable_infill_step_count,
        post_thickness_cm=post_thickness_cm,
        beam_thickness_cm=beam_thickness_cm,
        railing_height_cm=railing_height_cm,
        grid_snap_cm=max(0.0, _safe_float(spec.grid_snap_cm, 10.0)),
        asset_path=str(spec.asset_path or "/Engine/BasicShapes/Cube.Cube"),
        label_prefix=str(spec.label_prefix or "UCA_Structure"),
        support_surface_kind=str(spec.support_surface_kind or "support_surface"),
        support_level=int(spec.support_level or 0),
        support_actor_label=str(spec.support_actor_label or ""),
        parent_support_actor=str(spec.parent_support_actor or spec.support_actor_label or ""),
        support_reference_policy=str(spec.support_reference_policy or "explicit_only"),
        corner_join_style=corner_join_style,
        grid_safe_joints=bool(spec.grid_safe_joints),
    )


def _outer_dimensions(spec: BoxRoomSpec) -> tuple[float, float]:
    return (
        spec.inner_width_cm + (spec.wall_thickness_cm * 2.0),
        spec.inner_depth_cm + (spec.wall_thickness_cm * 2.0),
    )


def room_footprint(spec: BoxRoomSpec) -> dict[str, Any]:
    normalized = normalize_box_room_spec(spec)
    outer_width, outer_depth = _outer_dimensions(normalized)
    half_width = outer_width / 2.0
    half_depth = outer_depth / 2.0
    return {
        "center": [normalized.center_x, normalized.center_y, normalized.support_z],
        "outer_dimensions_cm": [outer_width, outer_depth, normalized.wall_height_cm],
        "min_xy": [round(normalized.center_x - half_width, 3), round(normalized.center_y - half_depth, 3)],
        "max_xy": [round(normalized.center_x + half_width, 3), round(normalized.center_y + half_depth, 3)],
        "support_z": normalized.support_z,
        "top_z": round(normalized.support_z + normalized.wall_height_cm, 3),
    }


def house_footprint(spec: HouseSpec) -> dict[str, Any]:
    normalized = normalize_house_spec(spec)
    outer_width = normalized.inner_width_cm + (normalized.wall_thickness_cm * 2.0)
    outer_depth = normalized.inner_depth_cm + (normalized.wall_thickness_cm * 2.0)
    half_width = (outer_width / 2.0) + normalized.roof_overhang_cm
    half_depth = (outer_depth / 2.0) + normalized.roof_overhang_cm
    total_height = (normalized.story_height_cm * 2.0) + normalized.floor_thickness_cm + normalized.roof_rise_cm + normalized.roof_thickness_cm
    return {
        "center": [normalized.center_x, normalized.center_y, normalized.support_z],
        "outer_dimensions_cm": [outer_width, outer_depth, total_height],
        "min_xy": [round(normalized.center_x - half_width, 3), round(normalized.center_y - half_depth, 3)],
        "max_xy": [round(normalized.center_x + half_width, 3), round(normalized.center_y + half_depth, 3)],
        "support_z": normalized.support_z,
        "top_z": round(normalized.support_z + total_height, 3),
    }


def _xy_overlap_area(
    a_min_xy: list[float],
    a_max_xy: list[float],
    b_min_xy: list[float],
    b_max_xy: list[float],
) -> float:
    x_overlap = max(0.0, min(a_max_xy[0], b_max_xy[0]) - max(a_min_xy[0], b_min_xy[0]))
    y_overlap = max(0.0, min(a_max_xy[1], b_max_xy[1]) - max(a_min_xy[1], b_min_xy[1]))
    return round(x_overlap * y_overlap, 3)


def _actor_bounds_xy(actor_payload: dict[str, Any]) -> tuple[list[float], list[float], float, float] | None:
    try:
        origin, extent = actor_origin_and_extent(actor_payload)
    except Exception:
        return None
    min_xy = [float(origin[0]) - float(extent[0]), float(origin[1]) - float(extent[1])]
    max_xy = [float(origin[0]) + float(extent[0]), float(origin[1]) + float(extent[1])]
    min_z = float(origin[2]) - float(extent[2])
    max_z = float(origin[2]) + float(extent[2])
    return min_xy, max_xy, min_z, max_z


def _room_candidate_conflicts(
    spec: BoxRoomSpec,
    scene_actors: list[dict[str, Any]],
    *,
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
) -> list[dict[str, Any]]:
    footprint = room_footprint(spec)
    min_xy = list(footprint["min_xy"])
    max_xy = list(footprint["max_xy"])
    support_z = float(footprint["support_z"])
    top_z = float(footprint["top_z"])
    ignore_paths = {str(value or "").strip().lower() for value in set(ignore_actor_paths or set()) if str(value or "").strip()}
    ignore_labels = {str(value or "").strip().lower() for value in set(ignore_actor_labels or set()) if str(value or "").strip()}
    conflicts: list[dict[str, Any]] = []

    for raw_actor in scene_actors:
        if not isinstance(raw_actor, dict):
            continue
        actor = dict(raw_actor)
        actor_path = _safe_text(actor.get("actor_path")).lower()
        actor_label = _safe_text(actor.get("label")).lower()
        actor_class = _safe_text(actor.get("class_name"))
        if actor_path and actor_path in ignore_paths:
            continue
        if actor_label and actor_label in ignore_labels:
            continue
        if actor_class in IGNORED_STRUCTURE_CLASSES or _safe_text(actor.get("label")) in IGNORED_STRUCTURE_LABELS:
            continue
        bounds = _actor_bounds_xy(actor)
        if bounds is None:
            continue
        actor_min_xy, actor_max_xy, actor_min_z, actor_max_z = bounds
        if actor_max_z < support_z - 2.0 or actor_min_z > top_z + 2.0:
            continue
        overlap_area = _xy_overlap_area(min_xy, max_xy, actor_min_xy, actor_max_xy)
        if overlap_area <= 1.0:
            continue
        support_kind = _safe_text(support_kind_for_actor(actor))
        support_level = support_level_for_actor(actor)
        conflicts.append(
            {
                "actor_label": _safe_text(actor.get("label")),
                "actor_path": _safe_text(actor.get("actor_path")),
                "asset_path": _safe_text(actor.get("asset_path")),
                "class_name": _safe_text(actor.get("class_name")),
                "support_surface_kind": support_kind,
                "support_level": support_level,
                "xy_overlap_area_cm2": overlap_area,
                "z_span_cm": [round(actor_min_z, 3), round(actor_max_z, 3)],
            }
        )
    conflicts.sort(
        key=lambda item: (
            -float(item.get("xy_overlap_area_cm2") or 0.0),
            _safe_text(item.get("actor_path") or item.get("actor_label")).lower(),
        )
    )
    return conflicts


def _structure_candidate_conflicts(
    *,
    min_xy: list[float],
    max_xy: list[float],
    support_z: float,
    top_z: float,
    scene_actors: list[dict[str, Any]],
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
) -> list[dict[str, Any]]:
    ignore_paths = {str(value or "").strip().lower() for value in set(ignore_actor_paths or set()) if str(value or "").strip()}
    ignore_labels = {str(value or "").strip().lower() for value in set(ignore_actor_labels or set()) if str(value or "").strip()}
    conflicts: list[dict[str, Any]] = []
    for raw_actor in scene_actors:
        if not isinstance(raw_actor, dict):
            continue
        actor = dict(raw_actor)
        actor_path = _safe_text(actor.get("actor_path")).lower()
        actor_label = _safe_text(actor.get("label")).lower()
        actor_class = _safe_text(actor.get("class_name"))
        if actor_path and actor_path in ignore_paths:
            continue
        if actor_label and actor_label in ignore_labels:
            continue
        if actor_class in IGNORED_STRUCTURE_CLASSES or _safe_text(actor.get("label")) in IGNORED_STRUCTURE_LABELS:
            continue
        bounds = _actor_bounds_xy(actor)
        if bounds is None:
            continue
        actor_min_xy, actor_max_xy, actor_min_z, actor_max_z = bounds
        if actor_max_z < support_z - 2.0 or actor_min_z > top_z + 2.0:
            continue
        overlap_area = _xy_overlap_area(min_xy, max_xy, actor_min_xy, actor_max_xy)
        if overlap_area <= 1.0:
            continue
        conflicts.append(
            {
                "actor_label": _safe_text(actor.get("label")),
                "actor_path": _safe_text(actor.get("actor_path")),
                "asset_path": _safe_text(actor.get("asset_path")),
                "class_name": _safe_text(actor.get("class_name")),
                "support_surface_kind": _safe_text(support_kind_for_actor(actor)),
                "support_level": support_level_for_actor(actor),
                "xy_overlap_area_cm2": overlap_area,
                "z_span_cm": [round(actor_min_z, 3), round(actor_max_z, 3)],
            }
        )
    conflicts.sort(
        key=lambda item: (
            -float(item.get("xy_overlap_area_cm2") or 0.0),
            _safe_text(item.get("actor_path") or item.get("actor_label")).lower(),
        )
    )
    return conflicts


def _spiral_offsets(step_cm: float, max_rings: int) -> list[tuple[float, float]]:
    step = max(1.0, float(step_cm))
    offsets: list[tuple[float, float]] = [(0.0, 0.0)]
    for ring in range(1, max_rings + 1):
        for dx in range(-ring, ring + 1):
            for dy in range(-ring, ring + 1):
                if max(abs(dx), abs(dy)) != ring:
                    continue
                offsets.append((round(dx * step, 3), round(dy * step, 3)))
    offsets.sort(key=lambda item: ((item[0] * item[0]) + (item[1] * item[1]), item[0], item[1]))
    return offsets


def plan_box_room_spec(
    spec: BoxRoomSpec,
    scene_actors: list[dict[str, Any]],
    *,
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
    max_rings: int = 8,
) -> dict[str, Any]:
    normalized = normalize_box_room_spec(spec)
    grid_step = normalized.grid_snap_cm or max(normalized.wall_thickness_cm, 10.0)
    tried: list[dict[str, Any]] = []
    chosen_spec = normalized
    chosen_conflicts = _room_candidate_conflicts(
        normalized,
        scene_actors,
        ignore_actor_paths=ignore_actor_paths,
        ignore_actor_labels=ignore_actor_labels,
    )
    if not chosen_conflicts:
        return {
            "spec": chosen_spec,
            "relocated": False,
            "offset_cm": [0.0, 0.0],
            "conflict_count": 0,
            "blocking_conflicts": [],
            "tried_positions": [
                {
                    "center": [normalized.center_x, normalized.center_y],
                    "conflict_count": 0,
                }
            ],
        }

    for offset_x, offset_y in _spiral_offsets(grid_step, max_rings):
        candidate = normalize_box_room_spec(
            BoxRoomSpec(
                **{
                    **normalized.__dict__,
                    "center_x": normalized.center_x + offset_x,
                    "center_y": normalized.center_y + offset_y,
                }
            )
        )
        conflicts = _room_candidate_conflicts(
            candidate,
            scene_actors,
            ignore_actor_paths=ignore_actor_paths,
            ignore_actor_labels=ignore_actor_labels,
        )
        tried.append(
            {
                "center": [candidate.center_x, candidate.center_y],
                "offset_cm": [offset_x, offset_y],
                "conflict_count": len(conflicts),
            }
        )
        if not conflicts:
            chosen_spec = candidate
            chosen_conflicts = []
            return {
                "spec": chosen_spec,
                "relocated": offset_x != 0.0 or offset_y != 0.0,
                "offset_cm": [offset_x, offset_y],
                "conflict_count": 0,
                "blocking_conflicts": [],
                "tried_positions": tried,
            }
        if len(conflicts) < len(chosen_conflicts):
            chosen_spec = candidate
            chosen_conflicts = conflicts

    return {
        "spec": chosen_spec,
        "relocated": chosen_spec.center_x != normalized.center_x or chosen_spec.center_y != normalized.center_y,
        "offset_cm": [round(chosen_spec.center_x - normalized.center_x, 3), round(chosen_spec.center_y - normalized.center_y, 3)],
        "conflict_count": len(chosen_conflicts),
        "blocking_conflicts": chosen_conflicts,
        "tried_positions": tried,
    }


def plan_house_spec(
    spec: HouseSpec,
    scene_actors: list[dict[str, Any]],
    *,
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
    max_rings: int = 10,
) -> dict[str, Any]:
    normalized = normalize_house_spec(spec)
    footprint = house_footprint(normalized)
    grid_step = normalized.grid_snap_cm or max(normalized.wall_thickness_cm, 10.0)
    tried: list[dict[str, Any]] = []
    chosen_spec = normalized
    chosen_conflicts = _structure_candidate_conflicts(
        min_xy=list(footprint["min_xy"]),
        max_xy=list(footprint["max_xy"]),
        support_z=float(footprint["support_z"]),
        top_z=float(footprint["top_z"]),
        scene_actors=scene_actors,
        ignore_actor_paths=ignore_actor_paths,
        ignore_actor_labels=ignore_actor_labels,
    )
    if not chosen_conflicts:
        return {
            "spec": chosen_spec,
            "relocated": False,
            "offset_cm": [0.0, 0.0],
            "conflict_count": 0,
            "blocking_conflicts": [],
            "tried_positions": [{"center": [normalized.center_x, normalized.center_y], "conflict_count": 0}],
        }
    for offset_x, offset_y in _spiral_offsets(grid_step, max_rings):
        candidate = normalize_house_spec(
            HouseSpec(
                **{
                    **normalized.__dict__,
                    "center_x": normalized.center_x + offset_x,
                    "center_y": normalized.center_y + offset_y,
                }
            )
        )
        candidate_footprint = house_footprint(candidate)
        conflicts = _structure_candidate_conflicts(
            min_xy=list(candidate_footprint["min_xy"]),
            max_xy=list(candidate_footprint["max_xy"]),
            support_z=float(candidate_footprint["support_z"]),
            top_z=float(candidate_footprint["top_z"]),
            scene_actors=scene_actors,
            ignore_actor_paths=ignore_actor_paths,
            ignore_actor_labels=ignore_actor_labels,
        )
        tried.append(
            {
                "center": [candidate.center_x, candidate.center_y],
                "offset_cm": [offset_x, offset_y],
                "conflict_count": len(conflicts),
            }
        )
        if not conflicts:
            return {
                "spec": candidate,
                "relocated": offset_x != 0.0 or offset_y != 0.0,
                "offset_cm": [offset_x, offset_y],
                "conflict_count": 0,
                "blocking_conflicts": [],
                "tried_positions": tried,
            }
        if len(conflicts) < len(chosen_conflicts):
            chosen_spec = candidate
            chosen_conflicts = conflicts
    return {
        "spec": chosen_spec,
        "relocated": chosen_spec.center_x != normalized.center_x or chosen_spec.center_y != normalized.center_y,
        "offset_cm": [round(chosen_spec.center_x - normalized.center_x, 3), round(chosen_spec.center_y - normalized.center_y, 3)],
        "conflict_count": len(chosen_conflicts),
        "blocking_conflicts": chosen_conflicts,
        "tried_positions": tried,
    }


def build_box_room_segments(spec: BoxRoomSpec) -> list[dict[str, Any]]:
    normalized = normalize_box_room_spec(spec)
    t = normalized.wall_thickness_cm
    h = normalized.wall_height_cm
    z_center = normalized.support_z + (h / 2.0)
    inner_w = normalized.inner_width_cm
    inner_d = normalized.inner_depth_cm
    outer_w = inner_w + (t * 2.0)
    outer_d = inner_d + (t * 2.0)
    front_y = normalized.center_y - (inner_d / 2.0) - (t / 2.0)
    back_y = normalized.center_y + (inner_d / 2.0) + (t / 2.0)
    left_x = normalized.center_x - (inner_w / 2.0) - (t / 2.0)
    right_x = normalized.center_x + (inner_w / 2.0) + (t / 2.0)
    if normalized.corner_join_style == "butt_join":
        horizontal_span = inner_w
    else:
        horizontal_span = outer_w
    front_segment_length = max(10.0, (horizontal_span - normalized.door_width_cm) / 2.0)
    if normalized.corner_join_style == "butt_join" and normalized.grid_safe_joints and normalized.grid_snap_cm > 0.0:
        joint_unit = normalized.grid_snap_cm * 2.0
        snapped_segment_length = round(front_segment_length / joint_unit) * joint_unit
        front_segment_length = max(10.0, min(horizontal_span / 2.0, snapped_segment_length))
    effective_door_width = max(40.0, horizontal_span - (front_segment_length * 2.0))
    door_left_center_x = normalized.center_x - (effective_door_width / 2.0) - (front_segment_length / 2.0)
    door_right_center_x = normalized.center_x + (effective_door_width / 2.0) + (front_segment_length / 2.0)
    header_height = max(40.0, h - normalized.door_height_cm)
    header_center_z = normalized.support_z + normalized.door_height_cm + (header_height / 2.0)

    def loc(x: float, y: float, z: float) -> list[float]:
        return [
            round(float(x), 3),
            round(float(y), 3),
            round(float(z), 3),
        ]

    def scale(width_cm: float, depth_cm: float, height_cm: float) -> list[float]:
        return [
            round(width_cm / CUBE_SIZE_CM, 3),
            round(depth_cm / CUBE_SIZE_CM, 3),
            round(height_cm / CUBE_SIZE_CM, 3),
        ]

    return [
        {
            "managed_slot": "wall_back",
            "spawn_label": f"{normalized.label_prefix}_Back",
            "location": loc(normalized.center_x, back_y, z_center),
            "rotation": [0.0, 0.0, 0.0],
            "scale": scale(horizontal_span, t, h),
        },
        {
            "managed_slot": "wall_left",
            "spawn_label": f"{normalized.label_prefix}_Left",
            "location": loc(left_x, normalized.center_y, z_center),
            "rotation": [0.0, 0.0, 0.0],
            "scale": scale(t, outer_d, h),
        },
        {
            "managed_slot": "wall_right",
            "spawn_label": f"{normalized.label_prefix}_Right",
            "location": loc(right_x, normalized.center_y, z_center),
            "rotation": [0.0, 0.0, 0.0],
            "scale": scale(t, outer_d, h),
        },
        {
            "managed_slot": "wall_front_left",
            "spawn_label": f"{normalized.label_prefix}_FrontLeft",
            "location": loc(door_left_center_x, front_y, z_center),
            "rotation": [0.0, 0.0, 0.0],
            "scale": scale(front_segment_length, t, h),
        },
        {
            "managed_slot": "wall_front_right",
            "spawn_label": f"{normalized.label_prefix}_FrontRight",
            "location": loc(door_right_center_x, front_y, z_center),
            "rotation": [0.0, 0.0, 0.0],
            "scale": scale(front_segment_length, t, h),
        },
        {
            "managed_slot": "door_header",
            "spawn_label": f"{normalized.label_prefix}_DoorHeader",
            "location": loc(normalized.center_x, front_y, header_center_z),
            "rotation": [0.0, 0.0, 0.0],
            "scale": scale(effective_door_width, t, header_height),
        },
    ]


def build_box_room_actions(spec: BoxRoomSpec) -> list[dict[str, Any]]:
    normalized = normalize_box_room_spec(spec)
    support_hint = {
        "placement_phase": "initial_place",
        "snap_policy": "none",
        "support_reference_policy": normalized.support_reference_policy,
        "mount_type": "wall",
        "expected_mount_type": "wall",
        "support_surface_kind": normalized.support_surface_kind,
        "support_level": normalized.support_level,
        "support_actor_label": normalized.support_actor_label,
        "parent_support_actor": normalized.parent_support_actor,
        "surface_anchor": [
            _snap(normalized.center_x, normalized.grid_snap_cm),
            _snap(normalized.center_y, normalized.grid_snap_cm),
            _snap(normalized.support_z, normalized.grid_snap_cm),
        ],
    }
    actions: list[dict[str, Any]] = []
    for segment in build_box_room_segments(normalized):
        actions.append(
            {
                "action": "place_asset",
                "target_zone": normalized.zone_id,
                "managed_slot": segment["managed_slot"],
                "identity_policy": "reuse_or_create",
                "asset_path": normalized.asset_path,
                "spawn_label": segment["spawn_label"],
                "transform": {
                    "location": list(segment["location"]),
                    "rotation": list(segment["rotation"]),
                    "scale": list(segment["scale"]),
                },
                "placement_hint": dict(support_hint),
            }
        )
    return actions


def _rect_volume(
    *,
    name: str,
    kind: str,
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
    min_z: float,
    max_z: float,
    protected: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "min": [round(min_x, 3), round(min_y, 3), round(min_z, 3)],
        "max": [round(max_x, 3), round(max_y, 3), round(max_z, 3)],
        "protected": bool(protected),
    }


def _rect_segment(
    *,
    managed_slot: str,
    spawn_label: str,
    center_x: float,
    center_y: float,
    center_z: float,
    width_cm: float,
    depth_cm: float,
    height_cm: float,
    mount_type: str,
    structural_role: str,
    structure_piece_role: str,
    support_fit_reference_z: float | None = None,
    reserved_volume_relationship: str = "must_not_overlap",
    allowed_reserved_volume_kinds: list[str] | None = None,
    structure_story: int = 0,
    circulation_protected: bool = False,
    opening_protected: bool = False,
) -> dict[str, Any]:
    return {
        "managed_slot": managed_slot,
        "spawn_label": spawn_label,
        "location": [round(center_x, 3), round(center_y, 3), round(center_z, 3)],
        "rotation": [0.0, 0.0, 0.0],
        "scale": [
            round(width_cm / CUBE_SIZE_CM, 3),
            round(depth_cm / CUBE_SIZE_CM, 3),
            round(height_cm / CUBE_SIZE_CM, 3),
        ],
        "mount_type": mount_type,
        "structural_role": structural_role,
        "structure_piece_role": structure_piece_role,
        "support_fit_reference_z": round(float(support_fit_reference_z), 3) if support_fit_reference_z is not None else None,
        "reserved_volume_relationship": reserved_volume_relationship,
        "allowed_reserved_volume_kinds": list(allowed_reserved_volume_kinds or []),
        "structure_story": int(structure_story),
        "circulation_protected": bool(circulation_protected),
        "opening_protected": bool(opening_protected),
    }


def build_house_structure_plan(spec: HouseSpec) -> dict[str, Any]:
    normalized = normalize_house_spec(spec)
    t = normalized.wall_thickness_cm
    story_h = normalized.story_height_cm
    slab_t = normalized.floor_thickness_cm
    inner_w = normalized.inner_width_cm
    inner_d = normalized.inner_depth_cm
    outer_w = inner_w + (t * 2.0)
    outer_d = inner_d + (t * 2.0)
    front_y = normalized.center_y - (inner_d / 2.0) - (t / 2.0)
    back_y = normalized.center_y + (inner_d / 2.0) + (t / 2.0)
    left_x = normalized.center_x - (inner_w / 2.0) - (t / 2.0)
    right_x = normalized.center_x + (inner_w / 2.0) + (t / 2.0)
    outer_min_x = normalized.center_x - (outer_w / 2.0)
    outer_max_x = normalized.center_x + (outer_w / 2.0)
    outer_min_y = normalized.center_y - (outer_d / 2.0)
    outer_max_y = normalized.center_y + (outer_d / 2.0)
    interior_min_x = normalized.center_x - (inner_w / 2.0)
    interior_max_x = normalized.center_x + (inner_w / 2.0)
    interior_min_y = normalized.center_y - (inner_d / 2.0)
    interior_max_y = normalized.center_y + (inner_d / 2.0)
    floor0_z = normalized.support_z + (slab_t / 2.0)
    story1_wall_z = normalized.support_z + slab_t + (story_h / 2.0)
    floor1_z = normalized.support_z + story_h + (slab_t / 2.0)
    story2_wall_z = normalized.support_z + story_h + slab_t + (story_h / 2.0)
    roof_base_z = normalized.support_z + (story_h * 2.0) + slab_t

    if normalized.corner_join_style == "butt_join":
        horizontal_span = inner_w
    else:
        horizontal_span = outer_w

    front_segment_length = max(20.0, (horizontal_span - normalized.door_width_cm) / 2.0)
    if normalized.corner_join_style == "butt_join" and normalized.grid_safe_joints and normalized.grid_snap_cm > 0.0:
        joint_unit = max(normalized.grid_snap_cm, 1.0) * 2.0
        snapped_segment_length = round(front_segment_length / joint_unit) * joint_unit
        front_segment_length = max(20.0, min(horizontal_span / 2.0, snapped_segment_length))
    effective_door_width = max(80.0, horizontal_span - (front_segment_length * 2.0))
    door_left_center_x = normalized.center_x - (effective_door_width / 2.0) - (front_segment_length / 2.0)
    door_right_center_x = normalized.center_x + (effective_door_width / 2.0) + (front_segment_length / 2.0)
    door_header_height = max(30.0, story_h - normalized.door_height_cm)
    door_header_center_z = normalized.support_z + slab_t + normalized.door_height_cm + (door_header_height / 2.0)

    roof_pitch_rad = math.radians(normalized.roof_pitch_deg)
    half_roof_width = (outer_w / 2.0) + normalized.roof_overhang_cm
    roof_depth = outer_d + (normalized.roof_overhang_cm * 2.0)
    roof_panel_width = max(40.0, half_roof_width / max(0.2, math.cos(roof_pitch_rad)))
    roof_panel_center_z = roof_base_z + (normalized.roof_rise_cm / 2.0)
    roof_center_x_offset = half_roof_width / 2.0
    ridge_z = roof_base_z + normalized.roof_rise_cm
    ridge_center_z = ridge_z + (normalized.roof_ridge_thickness_cm / 2.0)

    stair_total_rise = story_h + slab_t
    step_rise = max(10.0, min(normalized.stair_step_rise_cm, stair_total_rise / max(1, normalized.stair_step_count)))
    step_count = max(1, int(round(stair_total_rise / step_rise)))
    step_rise = stair_total_rise / step_count
    step_run = normalized.stair_step_run_cm
    stair_start_x = normalized.center_x - (inner_w / 2.0) + (normalized.stair_width_cm / 2.0) + 40.0
    stair_start_y = normalized.center_y - (inner_d / 2.0) + (step_run / 2.0) + 60.0
    min_stair_start_y = interior_min_y + (step_run / 2.0) + 20.0
    max_top_step_back_y = interior_max_y - normalized.landing_depth_cm - 10.0
    top_step_back_y = stair_start_y + ((step_count - 1) * step_run) + (step_run / 2.0)
    if top_step_back_y > max_top_step_back_y:
        available_shift = max(0.0, stair_start_y - min_stair_start_y)
        required_shift = top_step_back_y - max_top_step_back_y
        applied_shift = min(available_shift, required_shift)
        stair_start_y -= applied_shift
        top_step_back_y = stair_start_y + ((step_count - 1) * step_run) + (step_run / 2.0)
    if top_step_back_y > max_top_step_back_y:
        available_run_length = max(120.0, max_top_step_back_y - stair_start_y + (step_run / 2.0))
        step_run = max(20.0, available_run_length / float(step_count))
        top_step_back_y = stair_start_y + ((step_count - 1) * step_run) + (step_run / 2.0)
    stair_opening_margin = normalized.stair_opening_margin_cm
    stair_x_min = max(interior_min_x + 6.0, stair_start_x - (normalized.stair_width_cm / 2.0) - stair_opening_margin)
    stair_x_max = min(interior_max_x - 6.0, stair_start_x + (normalized.stair_width_cm / 2.0) + stair_opening_margin)
    stair_opening_min_y = max(interior_min_y + 10.0, stair_start_y - (step_run / 2.0) - stair_opening_margin)
    stair_opening_max_y = min(interior_max_y - normalized.landing_depth_cm - 10.0, top_step_back_y + stair_opening_margin)
    if stair_opening_max_y <= stair_opening_min_y:
        stair_opening_max_y = min(interior_max_y - 20.0, stair_opening_min_y + max(step_run * 2.0, 100.0))
    landing_y_min = stair_opening_max_y
    landing_depth = max(normalized.landing_depth_cm, step_run * 2.0)
    landing_y_max = min(interior_max_y - 10.0, landing_y_min + landing_depth)
    if landing_y_max <= landing_y_min:
        landing_y_max = min(interior_max_y - 5.0, landing_y_min + 90.0)
    guard_height = normalized.stair_guard_height_cm
    guard_thickness = normalized.stair_guard_thickness_cm
    upper_floor_surface_z = normalized.support_z + story_h + slab_t

    def rect_center(min_value: float, max_value: float) -> float:
        return round((min_value + max_value) / 2.0, 3)

    def rect_size(min_value: float, max_value: float) -> float:
        return round(max(0.0, max_value - min_value), 3)

    segments: list[dict[str, Any]] = [
        _rect_segment(
            managed_slot="floor_ground",
            spawn_label=f"{normalized.label_prefix}_FloorGround",
            center_x=normalized.center_x,
            center_y=normalized.center_y,
            center_z=floor0_z,
            width_cm=outer_w,
            depth_cm=outer_d,
            height_cm=slab_t,
            mount_type="floor",
            structural_role="base_floor",
            structure_piece_role="floor_slab",
            support_fit_reference_z=normalized.support_z,
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        )
    ]

    upper_floor_rects = [
        ("floor_upper_left", f"{normalized.label_prefix}_FloorUpperLeft", outer_min_x, stair_x_min, outer_min_y, outer_max_y, "floor_slab"),
        ("floor_upper_right", f"{normalized.label_prefix}_FloorUpperRight", stair_x_max, outer_max_x, outer_min_y, outer_max_y, "floor_slab"),
        ("floor_upper_front", f"{normalized.label_prefix}_FloorUpperFront", stair_x_min, stair_x_max, outer_min_y, stair_opening_min_y, "floor_slab"),
        ("landing_upper", f"{normalized.label_prefix}_LandingUpper", stair_x_min, stair_x_max, landing_y_min, outer_max_y, "landing"),
    ]
    for slot, label, min_x, max_x, min_y, max_y, role_name in upper_floor_rects:
        width_cm = rect_size(min_x, max_x)
        depth_cm = rect_size(min_y, max_y)
        if width_cm < 20.0 or depth_cm < 20.0:
            continue
        segments.append(
            _rect_segment(
                managed_slot=slot,
                spawn_label=label,
                center_x=rect_center(min_x, max_x),
                center_y=rect_center(min_y, max_y),
                center_z=floor1_z,
                width_cm=width_cm,
                depth_cm=depth_cm,
                height_cm=slab_t,
                mount_type="floor",
                structural_role="elevated_floor",
                structure_piece_role=role_name,
                support_fit_reference_z=normalized.support_z + story_h,
                structure_story=2,
                allowed_reserved_volume_kinds=["landing_clearance"] if role_name == "landing" else [],
                circulation_protected=True,
                opening_protected=True,
            )
        )

    guard_depth = rect_size(stair_opening_min_y, landing_y_max)
    if guard_depth >= 20.0:
        segments.extend(
            [
                _rect_segment(
                    managed_slot="stair_guard_outer",
                    spawn_label=f"{normalized.label_prefix}_StairGuardOuter",
                    center_x=stair_x_max + (guard_thickness / 2.0),
                    center_y=rect_center(stair_opening_min_y, landing_y_max),
                    center_z=upper_floor_surface_z + (guard_height / 2.0),
                    width_cm=guard_thickness,
                    depth_cm=guard_depth,
                    height_cm=guard_height,
                    mount_type="wall",
                    structural_role="guard_wall",
                    structure_piece_role="guardrail",
                    support_fit_reference_z=upper_floor_surface_z,
                    structure_story=2,
                    circulation_protected=True,
                    opening_protected=True,
                ),
                _rect_segment(
                    managed_slot="stair_guard_front",
                    spawn_label=f"{normalized.label_prefix}_StairGuardFront",
                    center_x=rect_center(stair_x_min, stair_x_max),
                    center_y=stair_opening_min_y - (guard_thickness / 2.0),
                    center_z=upper_floor_surface_z + (guard_height / 2.0),
                    width_cm=rect_size(stair_x_min, stair_x_max),
                    depth_cm=guard_thickness,
                    height_cm=guard_height,
                    mount_type="wall",
                    structural_role="guard_wall",
                    structure_piece_role="guardrail",
                    support_fit_reference_z=upper_floor_surface_z,
                    structure_story=2,
                    circulation_protected=True,
                    opening_protected=True,
                ),
            ]
        )

    def add_story_wall_segments(story_prefix: str, wall_center_z: float, front_has_door: bool, story_index: int) -> None:
        segments.extend(
            [
                _rect_segment(
                    managed_slot=f"{story_prefix}_wall_back",
                    spawn_label=f"{normalized.label_prefix}_{story_prefix}_Back",
                    center_x=normalized.center_x,
                    center_y=back_y,
                    center_z=wall_center_z,
                    width_cm=horizontal_span,
                    depth_cm=t,
                    height_cm=story_h,
                    mount_type="wall",
                    structural_role="wall_base",
                    structure_piece_role="wall_span",
                    structure_story=story_index,
                    circulation_protected=True,
                    opening_protected=True,
                ),
                _rect_segment(
                    managed_slot=f"{story_prefix}_wall_left",
                    spawn_label=f"{normalized.label_prefix}_{story_prefix}_Left",
                    center_x=left_x,
                    center_y=normalized.center_y,
                    center_z=wall_center_z,
                    width_cm=t,
                    depth_cm=outer_d,
                    height_cm=story_h,
                    mount_type="wall",
                    structural_role="wall_base",
                    structure_piece_role="wall_span",
                    structure_story=story_index,
                    circulation_protected=True,
                    opening_protected=True,
                ),
                _rect_segment(
                    managed_slot=f"{story_prefix}_wall_right",
                    spawn_label=f"{normalized.label_prefix}_{story_prefix}_Right",
                    center_x=right_x,
                    center_y=normalized.center_y,
                    center_z=wall_center_z,
                    width_cm=t,
                    depth_cm=outer_d,
                    height_cm=story_h,
                    mount_type="wall",
                    structural_role="wall_base",
                    structure_piece_role="wall_span",
                    structure_story=story_index,
                    circulation_protected=True,
                    opening_protected=True,
                ),
            ]
        )
        if front_has_door:
            segments.extend(
                [
                    _rect_segment(
                        managed_slot=f"{story_prefix}_wall_front_left",
                        spawn_label=f"{normalized.label_prefix}_{story_prefix}_FrontLeft",
                        center_x=door_left_center_x,
                        center_y=front_y,
                        center_z=wall_center_z,
                        width_cm=front_segment_length,
                        depth_cm=t,
                        height_cm=story_h,
                        mount_type="wall",
                        structural_role="wall_base",
                        structure_piece_role="wall_span",
                        structure_story=story_index,
                        circulation_protected=True,
                        opening_protected=True,
                    ),
                    _rect_segment(
                        managed_slot=f"{story_prefix}_wall_front_right",
                        spawn_label=f"{normalized.label_prefix}_{story_prefix}_FrontRight",
                        center_x=door_right_center_x,
                        center_y=front_y,
                        center_z=wall_center_z,
                        width_cm=front_segment_length,
                        depth_cm=t,
                        height_cm=story_h,
                        mount_type="wall",
                        structural_role="wall_base",
                        structure_piece_role="wall_span",
                        structure_story=story_index,
                        circulation_protected=True,
                        opening_protected=True,
                    ),
                    _rect_segment(
                        managed_slot=f"{story_prefix}_door_header",
                        spawn_label=f"{normalized.label_prefix}_{story_prefix}_DoorHeader",
                        center_x=normalized.center_x,
                        center_y=front_y,
                        center_z=door_header_center_z,
                        width_cm=effective_door_width,
                        depth_cm=t,
                        height_cm=door_header_height,
                        mount_type="wall",
                        structural_role="wall_header",
                        structure_piece_role="wall_span",
                        structure_story=story_index,
                        circulation_protected=True,
                        opening_protected=True,
                    ),
                ]
            )
        else:
            segments.append(
                _rect_segment(
                    managed_slot=f"{story_prefix}_wall_front",
                    spawn_label=f"{normalized.label_prefix}_{story_prefix}_Front",
                    center_x=normalized.center_x,
                    center_y=front_y,
                    center_z=wall_center_z,
                    width_cm=horizontal_span,
                    depth_cm=t,
                    height_cm=story_h,
                    mount_type="wall",
                    structural_role="wall_base",
                    structure_piece_role="wall_span",
                    structure_story=story_index,
                    circulation_protected=True,
                    opening_protected=True,
                )
            )

    add_story_wall_segments("story1", story1_wall_z, True, 1)
    add_story_wall_segments("story2", story2_wall_z, False, 2)

    gable_step_height = normalized.roof_rise_cm / float(normalized.gable_infill_step_count)
    for side_name, wall_y in (("front", front_y), ("back", back_y)):
        for step_index in range(normalized.gable_infill_step_count):
            band_min_z = roof_base_z + (step_index * gable_step_height)
            band_max_z = roof_base_z + ((step_index + 1) * gable_step_height)
            band_mid_z = (band_min_z + band_max_z) / 2.0
            taper_ratio = (band_mid_z - roof_base_z) / max(1.0, normalized.roof_rise_cm)
            band_width = max(20.0, horizontal_span * (1.0 - taper_ratio))
            segments.append(
                _rect_segment(
                    managed_slot=f"gable_{side_name}_{step_index + 1:02d}",
                    spawn_label=f"{normalized.label_prefix}_Gable{side_name.title()}_{step_index + 1:02d}",
                    center_x=normalized.center_x,
                    center_y=wall_y,
                    center_z=band_mid_z,
                    width_cm=band_width,
                    depth_cm=t,
                    height_cm=max(10.0, band_max_z - band_min_z),
                    mount_type="wall",
                    structural_role="gable_infill",
                    structure_piece_role="roof_closure",
                    support_fit_reference_z=band_min_z,
                    structure_story=3,
                    circulation_protected=True,
                    opening_protected=True,
                )
            )

    segments.extend(
        [
            {
                "managed_slot": "roof_left",
                "spawn_label": f"{normalized.label_prefix}_RoofLeft",
                "location": [round(normalized.center_x - roof_center_x_offset, 3), round(normalized.center_y, 3), round(roof_panel_center_z, 3)],
                "rotation": [0.0, 0.0, normalized.roof_pitch_deg],
                "scale": [round(roof_panel_width / CUBE_SIZE_CM, 3), round(roof_depth / CUBE_SIZE_CM, 3), round(normalized.roof_thickness_cm / CUBE_SIZE_CM, 3)],
                "mount_type": "roof",
                "structural_role": "roof_panel",
                "structure_piece_role": "roof_panel",
                "reserved_volume_relationship": "must_not_overlap",
                "allowed_reserved_volume_kinds": [],
                "structure_story": 3,
                "circulation_protected": True,
                "opening_protected": True,
            },
            {
                "managed_slot": "roof_right",
                "spawn_label": f"{normalized.label_prefix}_RoofRight",
                "location": [round(normalized.center_x + roof_center_x_offset, 3), round(normalized.center_y, 3), round(roof_panel_center_z, 3)],
                "rotation": [0.0, 0.0, -normalized.roof_pitch_deg],
                "scale": [round(roof_panel_width / CUBE_SIZE_CM, 3), round(roof_depth / CUBE_SIZE_CM, 3), round(normalized.roof_thickness_cm / CUBE_SIZE_CM, 3)],
                "mount_type": "roof",
                "structural_role": "roof_panel",
                "structure_piece_role": "roof_panel",
                "reserved_volume_relationship": "must_not_overlap",
                "allowed_reserved_volume_kinds": [],
                "structure_story": 3,
                "circulation_protected": True,
                "opening_protected": True,
            },
            {
                "managed_slot": "roof_ridge",
                "spawn_label": f"{normalized.label_prefix}_RoofRidge",
                "location": [round(normalized.center_x, 3), round(normalized.center_y, 3), round(ridge_center_z, 3)],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [
                    round(normalized.roof_ridge_thickness_cm / CUBE_SIZE_CM, 3),
                    round(roof_depth / CUBE_SIZE_CM, 3),
                    round(normalized.roof_ridge_thickness_cm / CUBE_SIZE_CM, 3),
                ],
                "mount_type": "roof",
                "structural_role": "roof_ridge",
                "structure_piece_role": "roof_ridge",
                "reserved_volume_relationship": "must_not_overlap",
                "allowed_reserved_volume_kinds": [],
                "structure_story": 3,
                "circulation_protected": True,
                "opening_protected": True,
            },
        ]
    )

    for step_index in range(step_count):
        step_center_z = normalized.support_z + ((step_index + 0.5) * step_rise)
        step_center_y = stair_start_y + (step_index * step_run)
        segments.append(
            _rect_segment(
                managed_slot=f"stair_{step_index + 1:02d}",
                spawn_label=f"{normalized.label_prefix}_Stair_{step_index + 1:02d}",
                center_x=stair_start_x,
                center_y=step_center_y,
                center_z=step_center_z,
                width_cm=normalized.stair_width_cm,
                depth_cm=step_run,
                height_cm=step_rise,
                mount_type="floor",
                structural_role="stair_step",
                structure_piece_role="stair_run",
                support_fit_reference_z=step_center_z - (step_rise / 2.0),
                reserved_volume_relationship="allowed",
                allowed_reserved_volume_kinds=["stairwell_opening", "floor_void", "landing_clearance"],
                structure_story=1,
                circulation_protected=True,
                opening_protected=True,
            )
        )

    stairwell_opening = _rect_volume(
        name="stairwell_opening",
        kind="floor_void",
        min_x=stair_x_min,
        max_x=stair_x_max,
        min_y=stair_opening_min_y,
        max_y=stair_opening_max_y,
        min_z=normalized.support_z + story_h - 5.0,
        max_z=normalized.support_z + story_h + slab_t + 5.0,
    )
    stair_arrival = _rect_volume(
        name="stair_arrival_clearance",
        kind="landing_clearance",
        min_x=stair_x_min,
        max_x=stair_x_max,
        min_y=landing_y_min,
        max_y=landing_y_max,
        min_z=normalized.support_z + story_h + slab_t + 5.0,
        max_z=normalized.support_z + story_h + slab_t + min(story_h - 20.0, 220.0),
    )
    front_door_opening = _rect_volume(
        name="front_door_opening",
        kind="door_opening",
        min_x=normalized.center_x - (effective_door_width / 2.0),
        max_x=normalized.center_x + (effective_door_width / 2.0),
        min_y=front_y - (t / 2.0),
        max_y=front_y + (t / 2.0),
        min_z=normalized.support_z + slab_t,
        max_z=normalized.support_z + slab_t + normalized.door_height_cm,
    )
    circulation_plan = {
        "stair_kind": "straight_run",
        "stair_run": {
            "start": [round(stair_start_x, 3), round(stair_start_y, 3), round(normalized.support_z, 3)],
            "step_run_cm": round(step_run, 3),
            "step_rise_cm": round(step_rise, 3),
            "step_count": step_count,
            "top_exit_y": round(top_step_back_y, 3),
        },
        "stairwell_opening": {
            "min": stairwell_opening["min"],
            "max": stairwell_opening["max"],
        },
        "landing_zone": {
            "min": [round(stair_x_min, 3), round(landing_y_min, 3), round(normalized.support_z + story_h, 3)],
            "max": [round(stair_x_max, 3), round(outer_max_y, 3), round(normalized.support_z + story_h + slab_t, 3)],
        },
    }
    roof_envelope = {
        "style": "gable",
        "eave_z": round(roof_base_z, 3),
        "ridge_z": round(ridge_z, 3),
        "ridge_x": round(normalized.center_x, 3),
        "depth_cm": round(roof_depth, 3),
        "overhang_cm": round(normalized.roof_overhang_cm, 3),
        "left_panel": {
            "slot": "roof_left",
            "expected_location": [round(normalized.center_x - roof_center_x_offset, 3), round(normalized.center_y, 3), round(roof_panel_center_z, 3)],
            "expected_rotation": [0.0, 0.0, round(normalized.roof_pitch_deg, 3)],
            "expected_scale": [round(roof_panel_width / CUBE_SIZE_CM, 3), round(roof_depth / CUBE_SIZE_CM, 3), round(normalized.roof_thickness_cm / CUBE_SIZE_CM, 3)],
        },
        "right_panel": {
            "slot": "roof_right",
            "expected_location": [round(normalized.center_x + roof_center_x_offset, 3), round(normalized.center_y, 3), round(roof_panel_center_z, 3)],
            "expected_rotation": [0.0, 0.0, round(-normalized.roof_pitch_deg, 3)],
            "expected_scale": [round(roof_panel_width / CUBE_SIZE_CM, 3), round(roof_depth / CUBE_SIZE_CM, 3), round(normalized.roof_thickness_cm / CUBE_SIZE_CM, 3)],
        },
        "ridge": {
            "slot": "roof_ridge",
            "expected_location": [round(normalized.center_x, 3), round(normalized.center_y, 3), round(ridge_center_z, 3)],
        },
        "gable_front": {
            "slots": [f"gable_front_{index + 1:02d}" for index in range(normalized.gable_infill_step_count)],
        },
        "gable_back": {
            "slots": [f"gable_back_{index + 1:02d}" for index in range(normalized.gable_infill_step_count)],
        },
    }
    return {
        "structure_type": "house",
        "story_count": 2,
        "spec": normalized,
        "footprint": house_footprint(normalized),
        "circulation_plan": circulation_plan,
        "reserved_volumes": [stairwell_opening, stair_arrival, front_door_opening],
        "functional_openings": [stairwell_opening, front_door_opening],
        "roof_envelope": roof_envelope,
        "landing_requirements": {
            "min_depth_cm": round(landing_depth, 3),
            "required": True,
        },
        "clearance_requirements": {
            "stair_clearance_headroom_cm": 200.0,
            "door_clear_height_cm": round(normalized.door_height_cm, 3),
        },
        "segments": segments,
    }


def build_house_segments(spec: HouseSpec) -> list[dict[str, Any]]:
    return list(build_house_structure_plan(spec).get("segments") or [])


def build_house_actions(spec: HouseSpec) -> list[dict[str, Any]]:
    structure_plan = build_house_structure_plan(spec)
    normalized = structure_plan["spec"]
    support_hint = {
        "placement_phase": "initial_place",
        "snap_policy": "none",
        "support_reference_policy": normalized.support_reference_policy,
        "support_surface_kind": normalized.support_surface_kind,
        "support_level": normalized.support_level,
        "support_actor_label": normalized.support_actor_label,
        "parent_support_actor": normalized.parent_support_actor,
        "surface_anchor": [
            _snap(normalized.center_x, normalized.grid_snap_cm),
            _snap(normalized.center_y, normalized.grid_snap_cm),
            _snap(normalized.support_z, normalized.grid_snap_cm),
        ],
        "structure_type": structure_plan.get("structure_type"),
        "story_count": structure_plan.get("story_count"),
        "circulation_plan": dict(structure_plan.get("circulation_plan") or {}),
        "reserved_volumes": list(structure_plan.get("reserved_volumes") or []),
        "functional_openings": list(structure_plan.get("functional_openings") or []),
        "roof_envelope": dict(structure_plan.get("roof_envelope") or {}),
        "landing_requirements": dict(structure_plan.get("landing_requirements") or {}),
        "clearance_requirements": dict(structure_plan.get("clearance_requirements") or {}),
    }
    actions: list[dict[str, Any]] = []
    for segment in list(structure_plan.get("segments") or []):
        mount_type = str(segment.get("mount_type") or "wall")
        segment_hint = {
            **support_hint,
            "mount_type": mount_type,
            "expected_mount_type": mount_type,
            "structural_role": str(segment.get("structural_role") or ""),
            "structure_piece_role": str(segment.get("structure_piece_role") or ""),
            "support_fit_reference_z": segment.get("support_fit_reference_z"),
            "assembly_zone": normalized.zone_id,
            "assembly_group": normalized.label_prefix,
            "reserved_volume_relationship": str(segment.get("reserved_volume_relationship") or "must_not_overlap"),
            "allowed_reserved_volume_kinds": list(segment.get("allowed_reserved_volume_kinds") or []),
            "circulation_protected": bool(segment.get("circulation_protected", False)),
            "opening_protected": bool(segment.get("opening_protected", False)),
            "structure_story": int(segment.get("structure_story") or 0),
        }
        actions.append(
            {
                "action": "place_asset",
                "target_zone": normalized.zone_id,
                "managed_slot": segment["managed_slot"],
                "identity_policy": "reuse_or_create",
                "asset_path": normalized.asset_path,
                "spawn_label": segment["spawn_label"],
                "transform": {
                    "location": list(segment["location"]),
                    "rotation": list(segment["rotation"]),
                    "scale": list(segment["scale"]),
                },
                "placement_hint": segment_hint,
            }
        )
    return actions


def structure_footprint(spec: StructureSpec) -> dict[str, Any]:
    normalized = normalize_structure_spec(spec)
    roof_buffer = normalized.roof_overhang_cm if normalized.roof_style in {"gable", "beam"} else 0.0
    half_width = (normalized.width_cm / 2.0) + roof_buffer
    half_depth = (normalized.depth_cm / 2.0) + roof_buffer
    top_z = normalized.support_z + normalized.floor_thickness_cm + normalized.wall_height_cm
    if normalized.roof_style == "gable":
        top_z += normalized.roof_rise_cm + normalized.roof_thickness_cm
    elif normalized.roof_style == "beam":
        top_z += normalized.beam_thickness_cm
    return {
        "center": [normalized.center_x, normalized.center_y, normalized.support_z],
        "outer_dimensions_cm": [normalized.width_cm, normalized.depth_cm, round(top_z - normalized.support_z, 3)],
        "min_xy": [round(normalized.center_x - half_width, 3), round(normalized.center_y - half_depth, 3)],
        "max_xy": [round(normalized.center_x + half_width, 3), round(normalized.center_y + half_depth, 3)],
        "support_z": normalized.support_z,
        "top_z": round(top_z, 3),
    }


def plan_structure_spec(
    spec: StructureSpec,
    scene_actors: list[dict[str, Any]],
    *,
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
    max_rings: int = 10,
) -> dict[str, Any]:
    normalized = normalize_structure_spec(spec)
    footprint = structure_footprint(normalized)
    grid_step = normalized.grid_snap_cm or max(normalized.wall_thickness_cm, 10.0)
    tried: list[dict[str, Any]] = []
    chosen_spec = normalized
    chosen_conflicts = _structure_candidate_conflicts(
        min_xy=list(footprint["min_xy"]),
        max_xy=list(footprint["max_xy"]),
        support_z=float(footprint["support_z"]),
        top_z=float(footprint["top_z"]),
        scene_actors=scene_actors,
        ignore_actor_paths=ignore_actor_paths,
        ignore_actor_labels=ignore_actor_labels,
    )
    if not chosen_conflicts:
        return {
            "spec": chosen_spec,
            "relocated": False,
            "offset_cm": [0.0, 0.0],
            "conflict_count": 0,
            "blocking_conflicts": [],
            "tried_positions": [{"center": [normalized.center_x, normalized.center_y], "conflict_count": 0}],
        }
    for offset_x, offset_y in _spiral_offsets(grid_step, max_rings):
        candidate = normalize_structure_spec(
            StructureSpec(
                **{
                    **normalized.__dict__,
                    "center_x": normalized.center_x + offset_x,
                    "center_y": normalized.center_y + offset_y,
                }
            )
        )
        candidate_footprint = structure_footprint(candidate)
        conflicts = _structure_candidate_conflicts(
            min_xy=list(candidate_footprint["min_xy"]),
            max_xy=list(candidate_footprint["max_xy"]),
            support_z=float(candidate_footprint["support_z"]),
            top_z=float(candidate_footprint["top_z"]),
            scene_actors=scene_actors,
            ignore_actor_paths=ignore_actor_paths,
            ignore_actor_labels=ignore_actor_labels,
        )
        tried.append(
            {
                "center": [candidate.center_x, candidate.center_y],
                "offset_cm": [offset_x, offset_y],
                "conflict_count": len(conflicts),
            }
        )
        if not conflicts:
            return {
                "spec": candidate,
                "relocated": offset_x != 0.0 or offset_y != 0.0,
                "offset_cm": [offset_x, offset_y],
                "conflict_count": 0,
                "blocking_conflicts": [],
                "tried_positions": tried,
            }
        if len(conflicts) < len(chosen_conflicts):
            chosen_spec = candidate
            chosen_conflicts = conflicts
    return {
        "spec": chosen_spec,
        "relocated": chosen_spec.center_x != normalized.center_x or chosen_spec.center_y != normalized.center_y,
        "offset_cm": [round(chosen_spec.center_x - normalized.center_x, 3), round(chosen_spec.center_y - normalized.center_y, 3)],
        "conflict_count": len(chosen_conflicts),
        "blocking_conflicts": chosen_conflicts,
        "tried_positions": tried,
    }


def _add_gable_roof_segments(
    segments: list[dict[str, Any]],
    *,
    normalized: StructureSpec,
    roof_base_z: float,
    footprint_width_cm: float,
    footprint_depth_cm: float,
    gable_front_y: float | None,
    gable_back_y: float | None,
    story_index: int,
    include_closures: bool,
) -> dict[str, Any]:
    roof_pitch_rad = math.radians(normalized.roof_pitch_deg)
    half_roof_width = (footprint_width_cm / 2.0) + normalized.roof_overhang_cm
    roof_depth = footprint_depth_cm + (normalized.roof_overhang_cm * 2.0)
    roof_panel_width = max(40.0, half_roof_width / max(0.2, math.cos(roof_pitch_rad)))
    roof_panel_center_z = roof_base_z + (normalized.roof_rise_cm / 2.0)
    roof_center_x_offset = half_roof_width / 2.0
    ridge_z = roof_base_z + normalized.roof_rise_cm
    ridge_center_z = ridge_z + (normalized.roof_ridge_thickness_cm / 2.0)
    segments.extend(
        [
            {
                "managed_slot": "roof_left",
                "spawn_label": f"{normalized.label_prefix}_RoofLeft",
                "location": [round(normalized.center_x - roof_center_x_offset, 3), round(normalized.center_y, 3), round(roof_panel_center_z, 3)],
                "rotation": [0.0, 0.0, normalized.roof_pitch_deg],
                "scale": [round(roof_panel_width / CUBE_SIZE_CM, 3), round(roof_depth / CUBE_SIZE_CM, 3), round(normalized.roof_thickness_cm / CUBE_SIZE_CM, 3)],
                "mount_type": "roof",
                "structural_role": "roof_panel",
                "structure_piece_role": "roof_panel",
                "reserved_volume_relationship": "must_not_overlap",
                "allowed_reserved_volume_kinds": [],
                "structure_story": int(story_index),
                "circulation_protected": True,
                "opening_protected": True,
            },
            {
                "managed_slot": "roof_right",
                "spawn_label": f"{normalized.label_prefix}_RoofRight",
                "location": [round(normalized.center_x + roof_center_x_offset, 3), round(normalized.center_y, 3), round(roof_panel_center_z, 3)],
                "rotation": [0.0, 0.0, -normalized.roof_pitch_deg],
                "scale": [round(roof_panel_width / CUBE_SIZE_CM, 3), round(roof_depth / CUBE_SIZE_CM, 3), round(normalized.roof_thickness_cm / CUBE_SIZE_CM, 3)],
                "mount_type": "roof",
                "structural_role": "roof_panel",
                "structure_piece_role": "roof_panel",
                "reserved_volume_relationship": "must_not_overlap",
                "allowed_reserved_volume_kinds": [],
                "structure_story": int(story_index),
                "circulation_protected": True,
                "opening_protected": True,
            },
            {
                "managed_slot": "roof_ridge",
                "spawn_label": f"{normalized.label_prefix}_RoofRidge",
                "location": [round(normalized.center_x, 3), round(normalized.center_y, 3), round(ridge_center_z, 3)],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [
                    round(normalized.roof_ridge_thickness_cm / CUBE_SIZE_CM, 3),
                    round(roof_depth / CUBE_SIZE_CM, 3),
                    round(normalized.roof_ridge_thickness_cm / CUBE_SIZE_CM, 3),
                ],
                "mount_type": "roof",
                "structural_role": "roof_ridge",
                "structure_piece_role": "roof_ridge",
                "reserved_volume_relationship": "must_not_overlap",
                "allowed_reserved_volume_kinds": [],
                "structure_story": int(story_index),
                "circulation_protected": True,
                "opening_protected": True,
            },
        ]
    )
    if include_closures and gable_front_y is not None and gable_back_y is not None:
        gable_step_height = normalized.roof_rise_cm / float(normalized.gable_infill_step_count)
        for side_name, wall_y in (("front", gable_front_y), ("back", gable_back_y)):
            for step_index in range(normalized.gable_infill_step_count):
                band_min_z = roof_base_z + (step_index * gable_step_height)
                band_max_z = roof_base_z + ((step_index + 1) * gable_step_height)
                band_mid_z = (band_min_z + band_max_z) / 2.0
                taper_ratio = (band_mid_z - roof_base_z) / max(1.0, normalized.roof_rise_cm)
                band_width = max(20.0, footprint_width_cm * (1.0 - taper_ratio))
                segments.append(
                    _rect_segment(
                        managed_slot=f"gable_{side_name}_{step_index + 1:02d}",
                        spawn_label=f"{normalized.label_prefix}_Gable{side_name.title()}_{step_index + 1:02d}",
                        center_x=normalized.center_x,
                        center_y=wall_y,
                        center_z=band_mid_z,
                        width_cm=band_width,
                        depth_cm=normalized.wall_thickness_cm,
                        height_cm=max(10.0, band_max_z - band_min_z),
                        mount_type="wall",
                        structural_role="gable_infill",
                        structure_piece_role="roof_closure",
                        support_fit_reference_z=band_min_z,
                        structure_story=int(story_index),
                        circulation_protected=True,
                        opening_protected=True,
                    )
                )
    roof_envelope: dict[str, Any] = {
        "style": "gable",
        "eave_z": round(roof_base_z, 3),
        "ridge_z": round(ridge_z, 3),
        "ridge_x": round(normalized.center_x, 3),
        "depth_cm": round(roof_depth, 3),
        "overhang_cm": round(normalized.roof_overhang_cm, 3),
        "left_panel": {
            "slot": "roof_left",
            "expected_location": [round(normalized.center_x - roof_center_x_offset, 3), round(normalized.center_y, 3), round(roof_panel_center_z, 3)],
            "expected_rotation": [0.0, 0.0, round(normalized.roof_pitch_deg, 3)],
            "expected_scale": [round(roof_panel_width / CUBE_SIZE_CM, 3), round(roof_depth / CUBE_SIZE_CM, 3), round(normalized.roof_thickness_cm / CUBE_SIZE_CM, 3)],
        },
        "right_panel": {
            "slot": "roof_right",
            "expected_location": [round(normalized.center_x + roof_center_x_offset, 3), round(normalized.center_y, 3), round(roof_panel_center_z, 3)],
            "expected_rotation": [0.0, 0.0, round(-normalized.roof_pitch_deg, 3)],
            "expected_scale": [round(roof_panel_width / CUBE_SIZE_CM, 3), round(roof_depth / CUBE_SIZE_CM, 3), round(normalized.roof_thickness_cm / CUBE_SIZE_CM, 3)],
        },
        "ridge": {
            "slot": "roof_ridge",
            "expected_location": [round(normalized.center_x, 3), round(normalized.center_y, 3), round(ridge_center_z, 3)],
        },
    }
    if include_closures:
        roof_envelope["gable_front"] = {"slots": [f"gable_front_{index + 1:02d}" for index in range(normalized.gable_infill_step_count)]}
        roof_envelope["gable_back"] = {"slots": [f"gable_back_{index + 1:02d}" for index in range(normalized.gable_infill_step_count)]}
    return roof_envelope


def _build_enclosed_structure_plan(spec: StructureSpec) -> dict[str, Any]:
    normalized = normalize_structure_spec(spec)
    t = normalized.wall_thickness_cm
    wall_h = normalized.wall_height_cm
    floor_t = normalized.floor_thickness_cm
    inner_w = normalized.width_cm
    inner_d = normalized.depth_cm
    outer_w = inner_w + (t * 2.0)
    outer_d = inner_d + (t * 2.0)
    floor_z = normalized.support_z + (floor_t / 2.0)
    wall_center_z = normalized.support_z + floor_t + (wall_h / 2.0)
    roof_base_z = normalized.support_z + floor_t + wall_h
    front_y = normalized.center_y - (inner_d / 2.0) - (t / 2.0)
    back_y = normalized.center_y + (inner_d / 2.0) + (t / 2.0)
    left_x = normalized.center_x - (inner_w / 2.0) - (t / 2.0)
    right_x = normalized.center_x + (inner_w / 2.0) + (t / 2.0)
    horizontal_span = inner_w if normalized.corner_join_style == "butt_join" else outer_w
    wide_opening_types = {"garage", "barn", "workshop", "warehouse", "hangar"}
    opening_width = normalized.opening_width_cm if normalized.structure_type in wide_opening_types else normalized.door_width_cm
    opening_height = normalized.opening_height_cm if normalized.structure_type in wide_opening_types else normalized.door_height_cm
    front_segment_length = max(20.0, (horizontal_span - opening_width) / 2.0)
    if normalized.corner_join_style == "butt_join" and normalized.grid_safe_joints and normalized.grid_snap_cm > 0.0:
        joint_unit = max(normalized.grid_snap_cm, 1.0) * 2.0
        snapped_segment_length = round(front_segment_length / joint_unit) * joint_unit
        front_segment_length = max(20.0, min(horizontal_span / 2.0, snapped_segment_length))
    effective_opening_width = max(80.0, horizontal_span - (front_segment_length * 2.0))
    front_left_center_x = normalized.center_x - (effective_opening_width / 2.0) - (front_segment_length / 2.0)
    front_right_center_x = normalized.center_x + (effective_opening_width / 2.0) + (front_segment_length / 2.0)
    header_height = max(20.0, wall_h - opening_height)
    header_center_z = normalized.support_z + floor_t + opening_height + (header_height / 2.0)

    segments: list[dict[str, Any]] = [
        _rect_segment(
            managed_slot="floor_base",
            spawn_label=f"{normalized.label_prefix}_FloorBase",
            center_x=normalized.center_x,
            center_y=normalized.center_y,
            center_z=floor_z,
            width_cm=outer_w,
            depth_cm=outer_d,
            height_cm=floor_t,
            mount_type="floor",
            structural_role="base_floor",
            structure_piece_role="floor_slab",
            support_fit_reference_z=normalized.support_z,
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        ),
        _rect_segment(
            managed_slot="wall_back",
            spawn_label=f"{normalized.label_prefix}_Back",
            center_x=normalized.center_x,
            center_y=back_y,
            center_z=wall_center_z,
            width_cm=horizontal_span,
            depth_cm=t,
            height_cm=wall_h,
            mount_type="wall",
            structural_role="wall_base",
            structure_piece_role="wall_span",
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        ),
        _rect_segment(
            managed_slot="wall_left",
            spawn_label=f"{normalized.label_prefix}_Left",
            center_x=left_x,
            center_y=normalized.center_y,
            center_z=wall_center_z,
            width_cm=t,
            depth_cm=outer_d,
            height_cm=wall_h,
            mount_type="wall",
            structural_role="wall_base",
            structure_piece_role="wall_span",
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        ),
        _rect_segment(
            managed_slot="wall_right",
            spawn_label=f"{normalized.label_prefix}_Right",
            center_x=right_x,
            center_y=normalized.center_y,
            center_z=wall_center_z,
            width_cm=t,
            depth_cm=outer_d,
            height_cm=wall_h,
            mount_type="wall",
            structural_role="wall_base",
            structure_piece_role="wall_span",
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        ),
        _rect_segment(
            managed_slot="wall_front_left",
            spawn_label=f"{normalized.label_prefix}_FrontLeft",
            center_x=front_left_center_x,
            center_y=front_y,
            center_z=wall_center_z,
            width_cm=front_segment_length,
            depth_cm=t,
            height_cm=wall_h,
            mount_type="wall",
            structural_role="wall_base",
            structure_piece_role="wall_span",
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        ),
        _rect_segment(
            managed_slot="wall_front_right",
            spawn_label=f"{normalized.label_prefix}_FrontRight",
            center_x=front_right_center_x,
            center_y=front_y,
            center_z=wall_center_z,
            width_cm=front_segment_length,
            depth_cm=t,
            height_cm=wall_h,
            mount_type="wall",
            structural_role="wall_base",
            structure_piece_role="wall_span",
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        ),
        _rect_segment(
            managed_slot="front_header",
            spawn_label=f"{normalized.label_prefix}_FrontHeader",
            center_x=normalized.center_x,
            center_y=front_y,
            center_z=header_center_z,
            width_cm=effective_opening_width,
            depth_cm=t,
            height_cm=header_height,
            mount_type="wall",
            structural_role="wall_header",
            structure_piece_role="wall_span",
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        ),
    ]
    roof_envelope: dict[str, Any] = {}
    if normalized.roof_style == "gable":
        roof_envelope = _add_gable_roof_segments(
            segments,
            normalized=normalized,
            roof_base_z=roof_base_z,
            footprint_width_cm=outer_w,
            footprint_depth_cm=outer_d,
            gable_front_y=front_y,
            gable_back_y=back_y,
            story_index=2,
            include_closures=True,
        )
    front_opening = _rect_volume(
        name="front_entry_opening",
        kind="door_opening",
        min_x=normalized.center_x - (effective_opening_width / 2.0),
        max_x=normalized.center_x + (effective_opening_width / 2.0),
        min_y=front_y - (t / 2.0),
        max_y=front_y + (t / 2.0),
        min_z=normalized.support_z + floor_t,
        max_z=normalized.support_z + floor_t + opening_height,
    )
    return {
        "structure_type": normalized.structure_type,
        "story_count": 1,
        "spec": normalized,
        "footprint": structure_footprint(normalized),
        "circulation_plan": {
            "entry_axis": "front",
            "entry_width_cm": round(effective_opening_width, 3),
        },
        "reserved_volumes": [front_opening],
        "functional_openings": [front_opening],
        "roof_envelope": roof_envelope,
        "landing_requirements": {},
        "clearance_requirements": {"entry_clear_height_cm": round(opening_height, 3)},
        "segments": segments,
    }


def _build_open_structure_plan(spec: StructureSpec) -> dict[str, Any]:
    normalized = normalize_structure_spec(spec)
    floor_t = normalized.floor_thickness_cm
    wall_h = normalized.wall_height_cm
    outer_w = normalized.width_cm + normalized.post_thickness_cm
    outer_d = normalized.depth_cm + normalized.post_thickness_cm
    floor_z = normalized.support_z + (floor_t / 2.0)
    post_height = wall_h
    post_center_z = normalized.support_z + floor_t + (post_height / 2.0)
    beam_center_z = normalized.support_z + floor_t + post_height - (normalized.beam_thickness_cm / 2.0)
    half_span_x = normalized.width_cm / 2.0
    half_span_y = normalized.depth_cm / 2.0
    post_x = half_span_x
    post_y = half_span_y
    segments: list[dict[str, Any]] = [
        _rect_segment(
            managed_slot="floor_base",
            spawn_label=f"{normalized.label_prefix}_FloorBase",
            center_x=normalized.center_x,
            center_y=normalized.center_y,
            center_z=floor_z,
            width_cm=outer_w,
            depth_cm=outer_d,
            height_cm=floor_t,
            mount_type="floor",
            structural_role="base_floor",
            structure_piece_role="floor_slab",
            support_fit_reference_z=normalized.support_z,
            structure_story=1,
            circulation_protected=True,
            opening_protected=True,
        )
    ]
    post_positions = [
        ("post_front_left", -post_x, -post_y),
        ("post_front_right", post_x, -post_y),
        ("post_back_left", -post_x, post_y),
        ("post_back_right", post_x, post_y),
    ]
    for slot, dx, dy in post_positions:
        segments.append(
            _rect_segment(
                managed_slot=slot,
                spawn_label=f"{normalized.label_prefix}_{slot.title().replace('_', '')}",
                center_x=normalized.center_x + dx,
                center_y=normalized.center_y + dy,
                center_z=post_center_z,
                width_cm=normalized.post_thickness_cm,
                depth_cm=normalized.post_thickness_cm,
                height_cm=post_height,
                mount_type="wall",
                structural_role="support_post",
                structure_piece_role="post",
                support_fit_reference_z=normalized.support_z + floor_t,
                structure_story=1,
                circulation_protected=True,
                opening_protected=True,
            )
        )
    beam_specs = [
        ("beam_front", normalized.center_x, normalized.center_y - post_y, normalized.width_cm + normalized.post_thickness_cm, normalized.beam_thickness_cm),
        ("beam_back", normalized.center_x, normalized.center_y + post_y, normalized.width_cm + normalized.post_thickness_cm, normalized.beam_thickness_cm),
    ]
    for slot, center_x, center_y, width_cm, depth_cm in beam_specs:
        segments.append(
            _rect_segment(
                managed_slot=slot,
                spawn_label=f"{normalized.label_prefix}_{slot.title().replace('_', '')}",
                center_x=center_x,
                center_y=center_y,
                center_z=beam_center_z,
                width_cm=width_cm,
                depth_cm=depth_cm,
                height_cm=normalized.beam_thickness_cm,
                mount_type="wall",
                structural_role="roof_beam",
                structure_piece_role="beam",
                support_fit_reference_z=normalized.support_z + floor_t + post_height - normalized.beam_thickness_cm,
                structure_story=1,
                circulation_protected=True,
                opening_protected=True,
            )
        )
    side_beam_specs = [
        ("beam_left", normalized.center_x - post_x, normalized.center_y, normalized.beam_thickness_cm, normalized.depth_cm + normalized.post_thickness_cm),
        ("beam_right", normalized.center_x + post_x, normalized.center_y, normalized.beam_thickness_cm, normalized.depth_cm + normalized.post_thickness_cm),
    ]
    for slot, center_x, center_y, width_cm, depth_cm in side_beam_specs:
        segments.append(
            _rect_segment(
                managed_slot=slot,
                spawn_label=f"{normalized.label_prefix}_{slot.title().replace('_', '')}",
                center_x=center_x,
                center_y=center_y,
                center_z=beam_center_z,
                width_cm=width_cm,
                depth_cm=depth_cm,
                height_cm=normalized.beam_thickness_cm,
                mount_type="wall",
                structural_role="roof_beam",
                structure_piece_role="beam",
                support_fit_reference_z=normalized.support_z + floor_t + post_height - normalized.beam_thickness_cm,
                structure_story=1,
                circulation_protected=True,
                opening_protected=True,
            )
        )
    roof_envelope: dict[str, Any] = {}
    if normalized.roof_style == "gable":
        roof_envelope = _add_gable_roof_segments(
            segments,
            normalized=normalized,
            roof_base_z=normalized.support_z + floor_t + post_height,
            footprint_width_cm=outer_w,
            footprint_depth_cm=outer_d,
            gable_front_y=None,
            gable_back_y=None,
            story_index=2,
            include_closures=False,
        )
    else:
        slat_count = 5 if normalized.structure_type == "pergola" else 3
        for index in range(slat_count):
            offset_ratio = 0.0 if slat_count == 1 else (index / float(slat_count - 1)) - 0.5
            segments.append(
                _rect_segment(
                    managed_slot=f"roof_slat_{index + 1:02d}",
                    spawn_label=f"{normalized.label_prefix}_RoofSlat_{index + 1:02d}",
                    center_x=normalized.center_x,
                    center_y=normalized.center_y + (offset_ratio * normalized.depth_cm * 0.85),
                    center_z=beam_center_z + normalized.beam_thickness_cm,
                    width_cm=normalized.width_cm + normalized.post_thickness_cm,
                    depth_cm=max(8.0, normalized.beam_thickness_cm * 0.8),
                    height_cm=normalized.beam_thickness_cm,
                    mount_type="roof",
                    structural_role="roof_slat",
                    structure_piece_role="roof_panel",
                    support_fit_reference_z=beam_center_z,
                    structure_story=2,
                    circulation_protected=True,
                    opening_protected=True,
                )
            )
    return {
        "structure_type": normalized.structure_type,
        "story_count": 1,
        "spec": normalized,
        "footprint": structure_footprint(normalized),
        "circulation_plan": {"open_sides": True},
        "reserved_volumes": [],
        "functional_openings": [],
        "roof_envelope": roof_envelope,
        "landing_requirements": {},
        "clearance_requirements": {},
        "segments": segments,
    }


def build_structure_plan(spec: StructureSpec) -> dict[str, Any]:
    normalized = normalize_structure_spec(spec)
    if normalized.structure_type in ENCLOSED_GENERATIVE_STRUCTURE_TYPES:
        return _build_enclosed_structure_plan(normalized)
    return _build_open_structure_plan(normalized)


def build_structure_actions(spec: StructureSpec) -> list[dict[str, Any]]:
    structure_plan = build_structure_plan(spec)
    normalized = structure_plan["spec"]
    support_hint = {
        "placement_phase": "initial_place",
        "snap_policy": "none",
        "support_reference_policy": normalized.support_reference_policy,
        "support_surface_kind": normalized.support_surface_kind,
        "support_level": normalized.support_level,
        "support_actor_label": normalized.support_actor_label,
        "parent_support_actor": normalized.parent_support_actor,
        "surface_anchor": [
            _snap(normalized.center_x, normalized.grid_snap_cm),
            _snap(normalized.center_y, normalized.grid_snap_cm),
            _snap(normalized.support_z, normalized.grid_snap_cm),
        ],
        "structure_type": structure_plan.get("structure_type"),
        "story_count": structure_plan.get("story_count"),
        "circulation_plan": dict(structure_plan.get("circulation_plan") or {}),
        "reserved_volumes": list(structure_plan.get("reserved_volumes") or []),
        "functional_openings": list(structure_plan.get("functional_openings") or []),
        "roof_envelope": dict(structure_plan.get("roof_envelope") or {}),
        "landing_requirements": dict(structure_plan.get("landing_requirements") or {}),
        "clearance_requirements": dict(structure_plan.get("clearance_requirements") or {}),
    }
    actions: list[dict[str, Any]] = []
    for segment in list(structure_plan.get("segments") or []):
        mount_type = str(segment.get("mount_type") or "wall")
        segment_hint = {
            **support_hint,
            "mount_type": mount_type,
            "expected_mount_type": mount_type,
            "structural_role": str(segment.get("structural_role") or ""),
            "structure_piece_role": str(segment.get("structure_piece_role") or ""),
            "support_fit_reference_z": segment.get("support_fit_reference_z"),
            "assembly_zone": normalized.zone_id,
            "assembly_group": normalized.label_prefix,
            "reserved_volume_relationship": str(segment.get("reserved_volume_relationship") or "must_not_overlap"),
            "allowed_reserved_volume_kinds": list(segment.get("allowed_reserved_volume_kinds") or []),
            "circulation_protected": bool(segment.get("circulation_protected", False)),
            "opening_protected": bool(segment.get("opening_protected", False)),
            "structure_story": int(segment.get("structure_story") or 0),
        }
        actions.append(
            {
                "action": "place_asset",
                "target_zone": normalized.zone_id,
                "managed_slot": segment["managed_slot"],
                "identity_policy": "reuse_or_create",
                "asset_path": normalized.asset_path,
                "spawn_label": segment["spawn_label"],
                "transform": {
                    "location": list(segment["location"]),
                    "rotation": list(segment["rotation"]),
                    "scale": list(segment["scale"]),
                },
                "placement_hint": segment_hint,
            }
        )
    return actions
