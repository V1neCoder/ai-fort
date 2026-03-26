from __future__ import annotations

import math
import random
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
    variation_seed: int = 0
    story_count: int = 2
    inner_width_cm: float = 700.0
    inner_depth_cm: float = 600.0
    story_height_cm: float = 300.0
    wall_thickness_cm: float = 20.0
    floor_thickness_cm: float = 20.0
    door_width_cm: float = 160.0
    door_height_cm: float = 230.0
    roof_style: str = "gable"
    roof_pitch_deg: float = 30.0
    roof_thickness_cm: float = 18.0
    roof_overhang_cm: float = 25.0
    roof_rise_cm: float = 120.0
    window_width_cm: float = 130.0
    window_height_cm: float = 120.0
    window_sill_height_cm: float = 95.0
    window_columns_per_wall: int = 2
    entry_canopy_depth_cm: float = 0.0
    balcony_depth_cm: float = 0.0
    corner_column_diameter_cm: float = 0.0
    site_clearance_cm: float = 60.0
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
    residential_profile: str = "suburban"
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
    variation_seed = int(_safe_float(spec.variation_seed, 0.0))
    story_count = max(1, min(8, int(spec.story_count or 2)))
    inner_width = max(300.0, _safe_float(spec.inner_width_cm, 700.0))
    inner_depth = max(300.0, _safe_float(spec.inner_depth_cm, 600.0))
    story_height = max(220.0, _safe_float(spec.story_height_cm, 300.0))
    wall_thickness = max(10.0, _safe_float(spec.wall_thickness_cm, 20.0))
    floor_thickness = max(10.0, _safe_float(spec.floor_thickness_cm, 20.0))
    max_door_width = max(80.0, inner_width - (wall_thickness * 2.0) - 80.0)
    door_width = min(max_door_width, max(100.0, _safe_float(spec.door_width_cm, 160.0)))
    door_height = min(story_height - 30.0, max(120.0, _safe_float(spec.door_height_cm, 230.0)))
    roof_style = str(spec.roof_style or "gable").strip().lower()
    if roof_style not in {"gable", "parapet"}:
        roof_style = "gable"
    roof_pitch_deg = max(10.0, min(55.0, _safe_float(spec.roof_pitch_deg, 30.0)))
    roof_thickness = max(8.0, _safe_float(spec.roof_thickness_cm, 18.0))
    roof_overhang = max(0.0, _safe_float(spec.roof_overhang_cm, 25.0))
    roof_rise = max(40.0, _safe_float(spec.roof_rise_cm, 120.0))
    window_width = min(max(60.0, _safe_float(spec.window_width_cm, 130.0)), max(80.0, inner_width - 80.0))
    window_height = min(max(60.0, _safe_float(spec.window_height_cm, 120.0)), max(80.0, story_height - 80.0))
    window_sill_height = max(40.0, min(story_height - window_height - 20.0, _safe_float(spec.window_sill_height_cm, 95.0)))
    window_columns = max(1, min(4, int(spec.window_columns_per_wall or 2)))
    entry_canopy_depth = max(0.0, _safe_float(spec.entry_canopy_depth_cm, 0.0))
    if entry_canopy_depth <= 0.0:
        entry_canopy_depth = 120.0 if story_count >= 4 or roof_style == "parapet" else 90.0
    balcony_depth = max(0.0, _safe_float(spec.balcony_depth_cm, 0.0))
    corner_column_diameter = max(0.0, _safe_float(spec.corner_column_diameter_cm, 0.0))
    site_clearance = max(0.0, _safe_float(spec.site_clearance_cm, 60.0))
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
        variation_seed=variation_seed,
        story_count=story_count,
        inner_width_cm=inner_width,
        inner_depth_cm=inner_depth,
        story_height_cm=story_height,
        wall_thickness_cm=wall_thickness,
        floor_thickness_cm=floor_thickness,
        door_width_cm=door_width,
        door_height_cm=door_height,
        roof_style=roof_style,
        roof_pitch_deg=roof_pitch_deg,
        roof_thickness_cm=roof_thickness,
        roof_overhang_cm=roof_overhang,
        roof_rise_cm=roof_rise,
        window_width_cm=window_width,
        window_height_cm=window_height,
        window_sill_height_cm=window_sill_height,
        window_columns_per_wall=window_columns,
        entry_canopy_depth_cm=entry_canopy_depth,
        balcony_depth_cm=balcony_depth,
        corner_column_diameter_cm=corner_column_diameter,
        site_clearance_cm=site_clearance,
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
        residential_profile=str(spec.residential_profile or "suburban"),
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
    horizontal_buffer = max(
        normalized.roof_overhang_cm,
        normalized.balcony_depth_cm,
        normalized.entry_canopy_depth_cm,
        normalized.site_clearance_cm,
    )
    half_width = (outer_width / 2.0) + horizontal_buffer
    half_depth = (outer_depth / 2.0) + horizontal_buffer
    story_count = max(1, int(normalized.story_count))
    total_height = (normalized.story_height_cm * story_count) + (normalized.floor_thickness_cm * max(1, story_count - 1)) + normalized.roof_thickness_cm
    if normalized.roof_style == "gable":
        total_height += normalized.roof_rise_cm
    elif normalized.roof_style == "parapet":
        total_height += max(normalized.wall_thickness_cm + 20.0, 40.0)
    return {
        "center": [normalized.center_x, normalized.center_y, normalized.support_z],
        "outer_dimensions_cm": [outer_width, outer_depth, total_height],
        "min_xy": [round(normalized.center_x - half_width, 3), round(normalized.center_y - half_depth, 3)],
        "max_xy": [round(normalized.center_x + half_width, 3), round(normalized.center_y + half_depth, 3)],
        "support_z": normalized.support_z,
        "top_z": round(normalized.support_z + total_height, 3),
    }


def _house_variation_rng(normalized: HouseSpec) -> Any:
    return random.Random(int(normalized.variation_seed or 0))


def _stair_side_from_spec(normalized: HouseSpec) -> str:
    profile = str(normalized.residential_profile or "").strip().lower()
    if profile in {"townhouse", "apartment"}:
        return "left"
    rng = _house_variation_rng(normalized)
    return "right" if rng.random() >= 0.5 else "left"


def _balcony_edge_from_spec(normalized: HouseSpec) -> str:
    profile = str(normalized.residential_profile or "").strip().lower()
    if profile in {"townhouse", "suburban"}:
        return "front"
    rng = _house_variation_rng(normalized)
    return "back" if rng.random() >= 0.62 else "front"


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


def _axis_gap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    if a_max < b_min:
        return round(b_min - a_max, 3)
    if b_max < a_min:
        return round(a_min - b_max, 3)
    return 0.0


def _candidate_site_metrics(
    *,
    min_xy: list[float],
    max_xy: list[float],
    support_z: float,
    top_z: float,
    scene_actors: list[dict[str, Any]],
    ignore_actor_paths: set[str] | None = None,
    ignore_actor_labels: set[str] | None = None,
    near_distance_cm: float = 220.0,
) -> dict[str, Any]:
    ignore_paths = {str(value or "").strip().lower() for value in set(ignore_actor_paths or set()) if str(value or "").strip()}
    ignore_labels = {str(value or "").strip().lower() for value in set(ignore_actor_labels or set()) if str(value or "").strip()}
    nearest_clearance_cm: float | None = None
    nearby_actor_count = 0
    nearby_labels: list[str] = []

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
        gap_x = _axis_gap(min_xy[0], max_xy[0], actor_min_xy[0], actor_max_xy[0])
        gap_y = _axis_gap(min_xy[1], max_xy[1], actor_min_xy[1], actor_max_xy[1])
        if gap_x == 0.0 and gap_y == 0.0:
            clearance_cm = 0.0
        elif gap_x == 0.0:
            clearance_cm = gap_y
        elif gap_y == 0.0:
            clearance_cm = gap_x
        else:
            clearance_cm = round(math.sqrt((gap_x * gap_x) + (gap_y * gap_y)), 3)
        if nearest_clearance_cm is None or clearance_cm < nearest_clearance_cm:
            nearest_clearance_cm = clearance_cm
        if clearance_cm <= near_distance_cm:
            nearby_actor_count += 1
            nearby_labels.append(_safe_text(actor.get("label")) or _safe_text(actor.get("actor_path")))

    return {
        "nearest_clearance_cm": round(nearest_clearance_cm if nearest_clearance_cm is not None else 999999.0, 3),
        "nearby_actor_count": nearby_actor_count,
        "nearby_actors": nearby_labels[:12],
    }


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
    chosen_metrics = _candidate_site_metrics(
        min_xy=list(room_footprint(normalized)["min_xy"]),
        max_xy=list(room_footprint(normalized)["max_xy"]),
        support_z=float(room_footprint(normalized)["support_z"]),
        top_z=float(room_footprint(normalized)["top_z"]),
        scene_actors=scene_actors,
        ignore_actor_paths=ignore_actor_paths,
        ignore_actor_labels=ignore_actor_labels,
    )
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
                    "nearest_clearance_cm": chosen_metrics["nearest_clearance_cm"],
                    "nearby_actor_count": chosen_metrics["nearby_actor_count"],
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
        candidate_metrics = _candidate_site_metrics(
            min_xy=list(room_footprint(candidate)["min_xy"]),
            max_xy=list(room_footprint(candidate)["max_xy"]),
            support_z=float(room_footprint(candidate)["support_z"]),
            top_z=float(room_footprint(candidate)["top_z"]),
            scene_actors=scene_actors,
            ignore_actor_paths=ignore_actor_paths,
            ignore_actor_labels=ignore_actor_labels,
        )
        tried.append(
            {
                "center": [candidate.center_x, candidate.center_y],
                "offset_cm": [offset_x, offset_y],
                "conflict_count": len(conflicts),
                "nearest_clearance_cm": candidate_metrics["nearest_clearance_cm"],
                "nearby_actor_count": candidate_metrics["nearby_actor_count"],
            }
        )
        better_candidate = (
            len(conflicts) < len(chosen_conflicts)
            or (
                len(conflicts) == len(chosen_conflicts)
                and (
                    candidate_metrics["nearby_actor_count"] < chosen_metrics["nearby_actor_count"]
                    or (
                        candidate_metrics["nearby_actor_count"] == chosen_metrics["nearby_actor_count"]
                        and candidate_metrics["nearest_clearance_cm"] > chosen_metrics["nearest_clearance_cm"]
                    )
                )
            )
        )
        if better_candidate:
            chosen_spec = candidate
            chosen_conflicts = conflicts
            chosen_metrics = candidate_metrics

    return {
        "spec": chosen_spec,
        "relocated": chosen_spec.center_x != normalized.center_x or chosen_spec.center_y != normalized.center_y,
        "offset_cm": [round(chosen_spec.center_x - normalized.center_x, 3), round(chosen_spec.center_y - normalized.center_y, 3)],
        "conflict_count": len(chosen_conflicts),
        "blocking_conflicts": chosen_conflicts,
        "nearest_clearance_cm": chosen_metrics["nearest_clearance_cm"],
        "nearby_actor_count": chosen_metrics["nearby_actor_count"],
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
    chosen_metrics = _candidate_site_metrics(
        min_xy=list(footprint["min_xy"]),
        max_xy=list(footprint["max_xy"]),
        support_z=float(footprint["support_z"]),
        top_z=float(footprint["top_z"]),
        scene_actors=scene_actors,
        ignore_actor_paths=ignore_actor_paths,
        ignore_actor_labels=ignore_actor_labels,
    )
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
            "nearest_clearance_cm": chosen_metrics["nearest_clearance_cm"],
            "nearby_actor_count": chosen_metrics["nearby_actor_count"],
            "tried_positions": [{"center": [normalized.center_x, normalized.center_y], "conflict_count": 0, "nearest_clearance_cm": chosen_metrics["nearest_clearance_cm"], "nearby_actor_count": chosen_metrics["nearby_actor_count"]}],
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
        candidate_metrics = _candidate_site_metrics(
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
                "nearest_clearance_cm": candidate_metrics["nearest_clearance_cm"],
                "nearby_actor_count": candidate_metrics["nearby_actor_count"],
            }
        )
        better_candidate = (
            len(conflicts) < len(chosen_conflicts)
            or (
                len(conflicts) == len(chosen_conflicts)
                and (
                    candidate_metrics["nearby_actor_count"] < chosen_metrics["nearby_actor_count"]
                    or (
                        candidate_metrics["nearby_actor_count"] == chosen_metrics["nearby_actor_count"]
                        and candidate_metrics["nearest_clearance_cm"] > chosen_metrics["nearest_clearance_cm"]
                    )
                )
            )
        )
        if better_candidate:
            chosen_spec = candidate
            chosen_conflicts = conflicts
            chosen_metrics = candidate_metrics
    return {
        "spec": chosen_spec,
        "relocated": chosen_spec.center_x != normalized.center_x or chosen_spec.center_y != normalized.center_y,
        "offset_cm": [round(chosen_spec.center_x - normalized.center_x, 3), round(chosen_spec.center_y - normalized.center_y, 3)],
        "conflict_count": len(chosen_conflicts),
        "blocking_conflicts": chosen_conflicts,
        "nearest_clearance_cm": chosen_metrics["nearest_clearance_cm"],
        "nearby_actor_count": chosen_metrics["nearby_actor_count"],
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
    outer_min_x = normalized.center_x - (outer_w / 2.0)
    outer_max_x = normalized.center_x + (outer_w / 2.0)
    outer_min_y = normalized.center_y - (outer_d / 2.0)
    outer_max_y = normalized.center_y + (outer_d / 2.0)
    interior_min_x = normalized.center_x - (inner_w / 2.0)
    interior_max_x = normalized.center_x + (inner_w / 2.0)
    interior_min_y = normalized.center_y - (inner_d / 2.0)
    interior_max_y = normalized.center_y + (inner_d / 2.0)
    front_y = normalized.center_y - (inner_d / 2.0) - (t / 2.0)
    back_y = normalized.center_y + (inner_d / 2.0) + (t / 2.0)
    left_x = normalized.center_x - (inner_w / 2.0) - (t / 2.0)
    right_x = normalized.center_x + (inner_w / 2.0) + (t / 2.0)
    if normalized.corner_join_style == "butt_join":
        span_x_min = interior_min_x
        span_x_max = interior_max_x
        span_y_min = interior_min_y
        span_y_max = interior_max_y
        horizontal_span = inner_w
    else:
        span_x_min = outer_min_x
        span_x_max = outer_max_x
        span_y_min = outer_min_y
        span_y_max = outer_max_y
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
    asset_path: str = "/Engine/BasicShapes/Cube.Cube",
    material_role: str = "body",
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
        "asset_path": str(asset_path or "/Engine/BasicShapes/Cube.Cube"),
        "material_role": str(material_role or "body"),
    }


def _append_wall_face_with_openings(
    segments: list[dict[str, Any]],
    *,
    slot_prefix: str,
    label_prefix: str,
    orientation: str,
    fixed_axis: float,
    span_min: float,
    span_max: float,
    wall_bottom_z: float,
    wall_height_cm: float,
    thickness_cm: float,
    structure_story: int,
    openings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    wall_top_z = wall_bottom_z + wall_height_cm
    opening_items = sorted(
        [dict(item) for item in list(openings or []) if isinstance(item, dict)],
        key=lambda item: float(item.get("axis_min") or 0.0),
    )
    span_cursor = float(span_min)
    created_openings: list[dict[str, Any]] = []

    def add_segment(
        segment_slot: str,
        segment_label: str,
        axis_min: float,
        axis_max: float,
        min_z: float,
        max_z: float,
        *,
        structural_role: str = "wall_base",
        piece_role: str = "wall_span",
        material_role: str = "body",
        asset_path: str = "/Engine/BasicShapes/Cube.Cube",
    ) -> None:
        axis_size = round(max(0.0, axis_max - axis_min), 3)
        height_size = round(max(0.0, max_z - min_z), 3)
        if axis_size < 8.0 or height_size < 8.0:
            return
        center_axis = round((axis_min + axis_max) / 2.0, 3)
        center_z = round((min_z + max_z) / 2.0, 3)
        if orientation == "x":
            segments.append(
                _rect_segment(
                    managed_slot=segment_slot,
                    spawn_label=segment_label,
                    center_x=center_axis,
                    center_y=fixed_axis,
                    center_z=center_z,
                    width_cm=axis_size,
                    depth_cm=thickness_cm,
                    height_cm=height_size,
                    mount_type="wall",
                    structural_role=structural_role,
                    structure_piece_role=piece_role,
                    support_fit_reference_z=min_z,
                    structure_story=structure_story,
                    circulation_protected=True,
                    opening_protected=True,
                    asset_path=asset_path,
                    material_role=material_role,
                )
            )
        else:
            segments.append(
                _rect_segment(
                    managed_slot=segment_slot,
                    spawn_label=segment_label,
                    center_x=fixed_axis,
                    center_y=center_axis,
                    center_z=center_z,
                    width_cm=thickness_cm,
                    depth_cm=axis_size,
                    height_cm=height_size,
                    mount_type="wall",
                    structural_role=structural_role,
                    structure_piece_role=piece_role,
                    support_fit_reference_z=min_z,
                    structure_story=structure_story,
                    circulation_protected=True,
                    opening_protected=True,
                    asset_path=asset_path,
                    material_role=material_role,
                )
            )

    for opening_index, opening in enumerate(opening_items, start=1):
        axis_min = max(span_min, float(opening.get("axis_min") or span_min))
        axis_max = min(span_max, float(opening.get("axis_max") or span_max))
        opening_min_z = max(wall_bottom_z, float(opening.get("min_z") or wall_bottom_z))
        opening_max_z = min(wall_top_z, float(opening.get("max_z") or wall_top_z))
        if axis_max <= axis_min or opening_max_z <= opening_min_z:
            continue
        opening_name = str(opening.get("name") or f"opening_{opening_index:02d}")

        if axis_min > span_cursor:
            add_segment(
                f"{slot_prefix}_span_{opening_index:02d}_left",
                f"{label_prefix}_{opening_name.title()}Left",
                span_cursor,
                axis_min,
                wall_bottom_z,
                wall_top_z,
            )
        if opening_min_z > wall_bottom_z:
            add_segment(
                f"{slot_prefix}_{opening_name}_lower",
                f"{label_prefix}_{opening_name.title()}Lower",
                axis_min,
                axis_max,
                wall_bottom_z,
                opening_min_z,
                structural_role="wall_sill",
                piece_role="wall_span",
            )
        if wall_top_z > opening_max_z:
            add_segment(
                f"{slot_prefix}_{opening_name}_upper",
                f"{label_prefix}_{opening_name.title()}Upper",
                axis_min,
                axis_max,
                opening_max_z,
                wall_top_z,
                structural_role="wall_header",
                piece_role="wall_span",
            )
        if bool(opening.get("glazed", False)):
            pane_inset = max(2.0, thickness_cm * 0.18)
            pane_thickness = max(4.0, thickness_cm * 0.16)
            if orientation == "x":
                pane_center_y = fixed_axis + pane_inset
                segments.append(
                    _rect_segment(
                        managed_slot=f"{slot_prefix}_{opening_name}_glass",
                        spawn_label=f"{label_prefix}_{opening_name.title()}Glass",
                        center_x=round((axis_min + axis_max) / 2.0, 3),
                        center_y=round(pane_center_y, 3),
                        center_z=round((opening_min_z + opening_max_z) / 2.0, 3),
                        width_cm=max(20.0, axis_max - axis_min - 8.0),
                        depth_cm=pane_thickness,
                        height_cm=max(20.0, opening_max_z - opening_min_z - 8.0),
                        mount_type="wall",
                        structural_role="window_glass",
                        structure_piece_role="window_glass",
                        support_fit_reference_z=opening_min_z,
                        structure_story=structure_story,
                        circulation_protected=True,
                        opening_protected=True,
                        material_role="glass",
                    )
                )
            else:
                pane_center_x = fixed_axis + pane_inset
                segments.append(
                    _rect_segment(
                        managed_slot=f"{slot_prefix}_{opening_name}_glass",
                        spawn_label=f"{label_prefix}_{opening_name.title()}Glass",
                        center_x=round(pane_center_x, 3),
                        center_y=round((axis_min + axis_max) / 2.0, 3),
                        center_z=round((opening_min_z + opening_max_z) / 2.0, 3),
                        width_cm=pane_thickness,
                        depth_cm=max(20.0, axis_max - axis_min - 8.0),
                        height_cm=max(20.0, opening_max_z - opening_min_z - 8.0),
                        mount_type="wall",
                        structural_role="window_glass",
                        structure_piece_role="window_glass",
                        support_fit_reference_z=opening_min_z,
                        structure_story=structure_story,
                        circulation_protected=True,
                        opening_protected=True,
                        material_role="glass",
                    )
                )
        span_cursor = axis_max
        created_openings.append(
            {
                "name": opening_name,
                "kind": str(opening.get("kind") or "window_opening"),
                "min": [round(axis_min if orientation == "x" else fixed_axis - (thickness_cm / 2.0), 3), round(fixed_axis - (thickness_cm / 2.0) if orientation == "x" else axis_min, 3), round(opening_min_z, 3)],
                "max": [round(axis_max if orientation == "x" else fixed_axis + (thickness_cm / 2.0), 3), round(fixed_axis + (thickness_cm / 2.0) if orientation == "x" else axis_max, 3), round(opening_max_z, 3)],
                "protected": True,
            }
        )

    if span_max > span_cursor:
        add_segment(
            f"{slot_prefix}_span_tail",
            f"{label_prefix}_Tail",
            span_cursor,
            span_max,
            wall_bottom_z,
            wall_top_z,
        )

    return created_openings


def _append_corner_columns(
    segments: list[dict[str, Any]],
    *,
    normalized: HouseSpec,
    center_z: float,
    height_cm: float,
    outer_min_x: float,
    outer_max_x: float,
    outer_min_y: float,
    outer_max_y: float,
    slot_prefix: str,
    story_index: int,
) -> None:
    if normalized.corner_column_diameter_cm <= 0.0:
        return
    radius = normalized.corner_column_diameter_cm / 2.0
    positions = [
        (f"{slot_prefix}_front_left", outer_min_x + radius, outer_min_y + radius),
        (f"{slot_prefix}_front_right", outer_max_x - radius, outer_min_y + radius),
        (f"{slot_prefix}_back_left", outer_min_x + radius, outer_max_y - radius),
        (f"{slot_prefix}_back_right", outer_max_x - radius, outer_max_y - radius),
    ]
    for slot, center_x, center_y in positions:
        segments.append(
            _rect_segment(
                managed_slot=slot,
                spawn_label=f"{normalized.label_prefix}_{slot.title().replace('_', '')}",
                center_x=center_x,
                center_y=center_y,
                center_z=center_z,
                width_cm=normalized.corner_column_diameter_cm,
                depth_cm=normalized.corner_column_diameter_cm,
                height_cm=height_cm,
                mount_type="wall",
                structural_role="corner_column",
                structure_piece_role="trim",
                support_fit_reference_z=center_z - (height_cm / 2.0),
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                asset_path="/Engine/BasicShapes/Cylinder.Cylinder",
                material_role="trim",
            )
        )


def _window_openings_for_axis_span(
    *,
    name_prefix: str,
    axis_min: float,
    axis_max: float,
    sill_z: float,
    window_width_cm: float,
    window_height_cm: float,
    desired_columns: int,
    edge_margin_cm: float = 60.0,
) -> list[dict[str, Any]]:
    span = float(axis_max) - float(axis_min)
    min_required_span = max((window_width_cm + (edge_margin_cm * 2.0)), 180.0)
    if span < min_required_span or desired_columns <= 0:
        return []
    max_columns = max(1, int((span - (edge_margin_cm * 2.0) + 40.0) // max(window_width_cm + 40.0, 1.0)))
    column_count = max(1, min(int(desired_columns), max_columns))
    usable_min = float(axis_min) + edge_margin_cm + (window_width_cm / 2.0)
    usable_max = float(axis_max) - edge_margin_cm - (window_width_cm / 2.0)
    if usable_max <= usable_min:
        return []
    if column_count == 1:
        centers = [round((usable_min + usable_max) / 2.0, 3)]
    else:
        spacing = (usable_max - usable_min) / float(column_count - 1)
        centers = [round(usable_min + (spacing * index), 3) for index in range(column_count)]
    openings: list[dict[str, Any]] = []
    for index, center in enumerate(centers, start=1):
        openings.append(
            {
                "name": f"{name_prefix}_window_{index:02d}",
                "kind": "window_opening",
                "axis_min": round(center - (window_width_cm / 2.0), 3),
                "axis_max": round(center + (window_width_cm / 2.0), 3),
                "min_z": round(sill_z, 3),
                "max_z": round(sill_z + window_height_cm, 3),
                "glazed": True,
            }
        )
    return openings


def _front_entry_window_openings(
    *,
    axis_min: float,
    axis_max: float,
    door_axis_min: float,
    door_axis_max: float,
    sill_z: float,
    window_width_cm: float,
    window_height_cm: float,
    desired_columns: int,
    name_prefix: str,
) -> list[dict[str, Any]]:
    left_span = max(0.0, door_axis_min - axis_min)
    right_span = max(0.0, axis_max - door_axis_max)
    side_columns = max(1, min(2, int(desired_columns)))
    openings: list[dict[str, Any]] = []
    if left_span >= max(window_width_cm + 90.0, 180.0):
        openings.extend(
            _window_openings_for_axis_span(
                name_prefix=f"{name_prefix}_left",
                axis_min=axis_min,
                axis_max=door_axis_min,
                sill_z=sill_z,
                window_width_cm=window_width_cm,
                window_height_cm=window_height_cm,
                desired_columns=side_columns,
                edge_margin_cm=40.0,
            )
        )
    if right_span >= max(window_width_cm + 90.0, 180.0):
        openings.extend(
            _window_openings_for_axis_span(
                name_prefix=f"{name_prefix}_right",
                axis_min=door_axis_max,
                axis_max=axis_max,
                sill_z=sill_z,
                window_width_cm=window_width_cm,
                window_height_cm=window_height_cm,
                desired_columns=side_columns,
                edge_margin_cm=40.0,
            )
        )
    return openings


def _append_entry_canopy_segment(
    segments: list[dict[str, Any]],
    *,
    normalized: HouseSpec,
    center_x: float,
    front_y: float,
    canopy_bottom_z: float,
    canopy_width_cm: float,
    story_index: int,
) -> None:
    canopy_depth = max(0.0, normalized.entry_canopy_depth_cm)
    if canopy_depth <= 0.0:
        return
    canopy_thickness = max(8.0, normalized.wall_thickness_cm * 0.5)
    canopy_center_y = front_y - (normalized.wall_thickness_cm / 2.0) - (canopy_depth / 2.0)
    segments.append(
        _rect_segment(
            managed_slot=f"story{story_index}_entry_canopy",
            spawn_label=f"{normalized.label_prefix}_Story{story_index:02d}EntryCanopy",
            center_x=center_x,
            center_y=canopy_center_y,
            center_z=canopy_bottom_z + (canopy_thickness / 2.0),
            width_cm=max(canopy_width_cm, normalized.door_width_cm + 40.0),
            depth_cm=canopy_depth,
            height_cm=canopy_thickness,
            mount_type="roof",
            structural_role="entry_canopy",
            structure_piece_role="canopy",
            support_fit_reference_z=canopy_bottom_z,
            structure_story=story_index,
            circulation_protected=True,
            opening_protected=True,
            material_role="trim",
        )
    )


def _append_entry_portico_columns(
    segments: list[dict[str, Any]],
    *,
    normalized: HouseSpec,
    front_y: float,
    story_index: int,
    door_width_cm: float,
    floor_surface_z: float,
    wall_bottom_z: float,
) -> None:
    column_diameter = max(18.0, normalized.corner_column_diameter_cm * 0.8)
    canopy_depth = max(0.0, normalized.entry_canopy_depth_cm)
    if column_diameter <= 0.0 or canopy_depth <= 0.0:
        return
    if str(normalized.residential_profile or "").strip().lower() not in {"mansion", "villa"}:
        return
    height_cm = max(140.0, normalized.door_height_cm + 18.0)
    x_offset = max((door_width_cm / 2.0) - (column_diameter / 2.0) + 16.0, column_diameter)
    center_y = front_y - (normalized.wall_thickness_cm / 2.0) - max(column_diameter * 0.6, canopy_depth * 0.45)
    center_z = wall_bottom_z + (height_cm / 2.0)
    for side_name, center_x in (
        ("left", normalized.center_x - x_offset),
        ("right", normalized.center_x + x_offset),
    ):
        segments.append(
            _rect_segment(
                managed_slot=f"story{story_index}_portico_column_{side_name}",
                spawn_label=f"{normalized.label_prefix}_Story{story_index:02d}PorticoColumn{side_name.title()}",
                center_x=center_x,
                center_y=center_y,
                center_z=center_z,
                width_cm=column_diameter,
                depth_cm=column_diameter,
                height_cm=height_cm,
                mount_type="wall",
                structural_role="portico_column",
                structure_piece_role="trim",
                support_fit_reference_z=floor_surface_z,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                asset_path="/Engine/BasicShapes/Cylinder.Cylinder",
                material_role="trim",
            )
        )


def _append_story_balcony_segments(
    segments: list[dict[str, Any]],
    *,
    normalized: HouseSpec,
    story_index: int,
    span_x_min: float,
    span_x_max: float,
    front_y: float,
    back_y: float,
    floor_surface_z: float,
) -> None:
    balcony_depth = max(0.0, normalized.balcony_depth_cm)
    if story_index < 2 or balcony_depth <= 0.0:
        return
    profile = str(normalized.residential_profile or "").strip().lower()
    if profile not in {"apartment", "townhouse", "mansion", "villa"}:
        return

    width_ratio_by_profile = {
        "apartment": 0.82,
        "townhouse": 0.76,
        "mansion": 0.58,
        "villa": 0.62,
    }
    guard_height = max(72.0, normalized.stair_guard_height_cm)
    guard_thickness = max(4.0, normalized.stair_guard_thickness_cm)
    usable_width = max(140.0, (span_x_max - span_x_min) * width_ratio_by_profile.get(profile, 0.7))
    center_x = normalized.center_x
    edge = _balcony_edge_from_spec(normalized)
    wall_y = front_y if edge == "front" else back_y
    y_sign = -1.0 if edge == "front" else 1.0
    balcony_center_y = wall_y + (y_sign * ((normalized.wall_thickness_cm / 2.0) + (balcony_depth / 2.0)))
    slab_center_z = floor_surface_z + (normalized.floor_thickness_cm / 2.0)
    segments.append(
        _rect_segment(
            managed_slot=f"story{story_index}_balcony_slab",
            spawn_label=f"{normalized.label_prefix}_Story{story_index:02d}BalconySlab",
            center_x=center_x,
            center_y=balcony_center_y,
            center_z=slab_center_z,
            width_cm=usable_width,
            depth_cm=balcony_depth,
            height_cm=normalized.floor_thickness_cm,
            mount_type="floor",
            structural_role="balcony_slab",
            structure_piece_role="balcony",
            support_fit_reference_z=floor_surface_z,
            structure_story=story_index,
            circulation_protected=True,
            opening_protected=True,
            material_role="floor",
        )
    )
    rail_center_y = wall_y + (y_sign * ((normalized.wall_thickness_cm / 2.0) + balcony_depth + (guard_thickness / 2.0)))
    rail_center_z = floor_surface_z + normalized.floor_thickness_cm + (guard_height / 2.0)
    side_offset_x = (usable_width / 2.0) - (guard_thickness / 2.0)
    side_depth = max(20.0, balcony_depth + normalized.wall_thickness_cm * 0.35)
    segments.extend(
        [
            _rect_segment(
                managed_slot=f"story{story_index}_balcony_front_rail",
                spawn_label=f"{normalized.label_prefix}_Story{story_index:02d}BalconyFrontRail",
                center_x=center_x,
                center_y=rail_center_y,
                center_z=rail_center_z,
                width_cm=usable_width,
                depth_cm=guard_thickness,
                height_cm=guard_height,
                mount_type="wall",
                structural_role="balcony_guard",
                structure_piece_role="guardrail",
                support_fit_reference_z=floor_surface_z + normalized.floor_thickness_cm,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                material_role="trim",
            ),
            _rect_segment(
                managed_slot=f"story{story_index}_balcony_left_rail",
                spawn_label=f"{normalized.label_prefix}_Story{story_index:02d}BalconyLeftRail",
                center_x=center_x - side_offset_x,
                center_y=balcony_center_y + (y_sign * (balcony_depth / 2.0)),
                center_z=rail_center_z,
                width_cm=guard_thickness,
                depth_cm=side_depth,
                height_cm=guard_height,
                mount_type="wall",
                structural_role="balcony_guard",
                structure_piece_role="guardrail",
                support_fit_reference_z=floor_surface_z + normalized.floor_thickness_cm,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                material_role="trim",
            ),
            _rect_segment(
                managed_slot=f"story{story_index}_balcony_right_rail",
                spawn_label=f"{normalized.label_prefix}_Story{story_index:02d}BalconyRightRail",
                center_x=center_x + side_offset_x,
                center_y=balcony_center_y + (y_sign * (balcony_depth / 2.0)),
                center_z=rail_center_z,
                width_cm=guard_thickness,
                depth_cm=side_depth,
                height_cm=guard_height,
                mount_type="wall",
                structural_role="balcony_guard",
                structure_piece_role="guardrail",
                support_fit_reference_z=floor_surface_z + normalized.floor_thickness_cm,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                material_role="trim",
            ),
        ]
    )


def _append_house_story_walls(
    segments: list[dict[str, Any]],
    *,
    normalized: HouseSpec,
    story_prefix: str,
    story_index: int,
    wall_bottom_z: float,
    front_y: float,
    back_y: float,
    left_x: float,
    right_x: float,
    span_x_min: float,
    span_x_max: float,
    span_y_min: float,
    span_y_max: float,
    effective_door_width: float,
    front_has_door: bool,
    functional_openings: list[dict[str, Any]],
    outer_min_x: float,
    outer_max_x: float,
    outer_min_y: float,
    outer_max_y: float,
    floor_surface_z: float,
) -> None:
    story_h = normalized.story_height_cm
    t = normalized.wall_thickness_cm
    door_axis_min = normalized.center_x - (effective_door_width / 2.0)
    door_axis_max = normalized.center_x + (effective_door_width / 2.0)
    sill_z = wall_bottom_z + normalized.window_sill_height_cm
    front_openings: list[dict[str, Any]] = []
    if front_has_door:
        front_openings.append(
            {
                "name": "front_door",
                "kind": "door_opening",
                "axis_min": round(door_axis_min, 3),
                "axis_max": round(door_axis_max, 3),
                "min_z": round(wall_bottom_z, 3),
                "max_z": round(wall_bottom_z + normalized.door_height_cm, 3),
                "glazed": False,
            }
        )
        front_openings.extend(
            _front_entry_window_openings(
                axis_min=span_x_min,
                axis_max=span_x_max,
                door_axis_min=door_axis_min,
                door_axis_max=door_axis_max,
                sill_z=sill_z,
                window_width_cm=normalized.window_width_cm,
                window_height_cm=normalized.window_height_cm,
                desired_columns=max(1, normalized.window_columns_per_wall // 2),
                name_prefix=f"{story_prefix}_front",
            )
        )
    else:
        front_openings = _window_openings_for_axis_span(
            name_prefix=f"{story_prefix}_front",
            axis_min=span_x_min,
            axis_max=span_x_max,
            sill_z=sill_z,
            window_width_cm=normalized.window_width_cm,
            window_height_cm=normalized.window_height_cm,
            desired_columns=normalized.window_columns_per_wall,
        )
    back_openings = _window_openings_for_axis_span(
        name_prefix=f"{story_prefix}_back",
        axis_min=span_x_min,
        axis_max=span_x_max,
        sill_z=sill_z,
        window_width_cm=normalized.window_width_cm,
        window_height_cm=normalized.window_height_cm,
        desired_columns=normalized.window_columns_per_wall,
    )
    side_columns = 1 if normalized.story_count >= 3 else max(1, min(2, normalized.window_columns_per_wall - 1))
    left_openings = _window_openings_for_axis_span(
        name_prefix=f"{story_prefix}_left",
        axis_min=span_y_min,
        axis_max=span_y_max,
        sill_z=sill_z,
        window_width_cm=min(normalized.window_width_cm, max(90.0, (span_y_max - span_y_min) - 140.0)),
        window_height_cm=normalized.window_height_cm,
        desired_columns=side_columns,
    )
    right_openings = _window_openings_for_axis_span(
        name_prefix=f"{story_prefix}_right",
        axis_min=span_y_min,
        axis_max=span_y_max,
        sill_z=sill_z,
        window_width_cm=min(normalized.window_width_cm, max(90.0, (span_y_max - span_y_min) - 140.0)),
        window_height_cm=normalized.window_height_cm,
        desired_columns=side_columns,
    )
    functional_openings.extend(
        _append_wall_face_with_openings(
            segments,
            slot_prefix=f"{story_prefix}_wall_back",
            label_prefix=f"{normalized.label_prefix}_{story_prefix}_Back",
            orientation="x",
            fixed_axis=back_y,
            span_min=span_x_min,
            span_max=span_x_max,
            wall_bottom_z=wall_bottom_z,
            wall_height_cm=story_h,
            thickness_cm=t,
            structure_story=story_index,
            openings=back_openings,
        )
    )
    functional_openings.extend(
        _append_wall_face_with_openings(
            segments,
            slot_prefix=f"{story_prefix}_wall_left",
            label_prefix=f"{normalized.label_prefix}_{story_prefix}_Left",
            orientation="y",
            fixed_axis=left_x,
            span_min=span_y_min,
            span_max=span_y_max,
            wall_bottom_z=wall_bottom_z,
            wall_height_cm=story_h,
            thickness_cm=t,
            structure_story=story_index,
            openings=left_openings,
        )
    )
    functional_openings.extend(
        _append_wall_face_with_openings(
            segments,
            slot_prefix=f"{story_prefix}_wall_right",
            label_prefix=f"{normalized.label_prefix}_{story_prefix}_Right",
            orientation="y",
            fixed_axis=right_x,
            span_min=span_y_min,
            span_max=span_y_max,
            wall_bottom_z=wall_bottom_z,
            wall_height_cm=story_h,
            thickness_cm=t,
            structure_story=story_index,
            openings=right_openings,
        )
    )
    functional_openings.extend(
        _append_wall_face_with_openings(
            segments,
            slot_prefix=f"{story_prefix}_wall_front",
            label_prefix=f"{normalized.label_prefix}_{story_prefix}_Front",
            orientation="x",
            fixed_axis=front_y,
            span_min=span_x_min,
            span_max=span_x_max,
            wall_bottom_z=wall_bottom_z,
            wall_height_cm=story_h,
            thickness_cm=t,
            structure_story=story_index,
            openings=front_openings,
        )
    )
    if front_has_door:
        _append_entry_canopy_segment(
            segments,
            normalized=normalized,
            center_x=normalized.center_x,
            front_y=front_y,
            canopy_bottom_z=wall_bottom_z + normalized.door_height_cm + 8.0,
            canopy_width_cm=effective_door_width + max(40.0, normalized.window_width_cm * 0.25),
            story_index=story_index,
        )
        _append_entry_portico_columns(
            segments,
            normalized=normalized,
            front_y=front_y,
            story_index=story_index,
            door_width_cm=effective_door_width,
            floor_surface_z=floor_surface_z,
            wall_bottom_z=wall_bottom_z,
        )
    _append_corner_columns(
        segments,
        normalized=normalized,
        center_z=wall_bottom_z + (story_h / 2.0),
        height_cm=story_h,
        outer_min_x=outer_min_x,
        outer_max_x=outer_max_x,
        outer_min_y=outer_min_y,
        outer_max_y=outer_max_y,
        slot_prefix=f"{story_prefix}_corner",
        story_index=story_index,
    )


def _add_house_gable_roof_segments(
    segments: list[dict[str, Any]],
    *,
    normalized: HouseSpec,
    roof_base_z: float,
    outer_w: float,
    outer_d: float,
    horizontal_span: float,
    front_y: float,
    back_y: float,
    story_index: int,
) -> dict[str, Any]:
    roof_pitch_rad = math.radians(normalized.roof_pitch_deg)
    half_roof_width = (outer_w / 2.0) + normalized.roof_overhang_cm
    roof_depth = outer_d + (normalized.roof_overhang_cm * 2.0)
    roof_panel_width = max(40.0, half_roof_width / max(0.2, math.cos(roof_pitch_rad)))
    roof_panel_center_z = roof_base_z + (normalized.roof_rise_cm / 2.0)
    roof_center_x_offset = half_roof_width / 2.0
    ridge_z = roof_base_z + normalized.roof_rise_cm
    ridge_center_z = ridge_z + (normalized.roof_ridge_thickness_cm / 2.0)

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
                    depth_cm=normalized.wall_thickness_cm,
                    height_cm=max(10.0, band_max_z - band_min_z),
                    mount_type="wall",
                    structural_role="gable_infill",
                    structure_piece_role="roof_closure",
                    support_fit_reference_z=band_min_z,
                    structure_story=story_index,
                    circulation_protected=True,
                    opening_protected=True,
                    material_role="trim",
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
                "structure_story": story_index,
                "circulation_protected": True,
                "opening_protected": True,
                "asset_path": normalized.asset_path,
                "material_role": "roof",
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
                "structure_story": story_index,
                "circulation_protected": True,
                "opening_protected": True,
                "asset_path": normalized.asset_path,
                "material_role": "roof",
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
                "structure_story": story_index,
                "circulation_protected": True,
                "opening_protected": True,
                "asset_path": normalized.asset_path,
                "material_role": "trim",
            },
        ]
    )
    return {
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


def _add_parapet_roof_segments(
    segments: list[dict[str, Any]],
    *,
    normalized: HouseSpec,
    roof_base_z: float,
    outer_w: float,
    outer_d: float,
    story_index: int,
) -> dict[str, Any]:
    parapet_height = max(50.0, normalized.wall_thickness_cm + 30.0)
    parapet_thickness = max(12.0, normalized.wall_thickness_cm)
    roof_slab_thickness = max(12.0, normalized.roof_thickness_cm)
    roof_slab_z = roof_base_z + (roof_slab_thickness / 2.0)
    parapet_center_z = roof_base_z + roof_slab_thickness + (parapet_height / 2.0)
    front_y = normalized.center_y - (outer_d / 2.0) - (parapet_thickness / 2.0)
    back_y = normalized.center_y + (outer_d / 2.0) + (parapet_thickness / 2.0)
    left_x = normalized.center_x - (outer_w / 2.0) - (parapet_thickness / 2.0)
    right_x = normalized.center_x + (outer_w / 2.0) + (parapet_thickness / 2.0)

    segments.extend(
        [
            _rect_segment(
                managed_slot="roof_slab",
                spawn_label=f"{normalized.label_prefix}_RoofSlab",
                center_x=normalized.center_x,
                center_y=normalized.center_y,
                center_z=roof_slab_z,
                width_cm=outer_w,
                depth_cm=outer_d,
                height_cm=roof_slab_thickness,
                mount_type="roof",
                structural_role="roof_slab",
                structure_piece_role="roof_panel",
                support_fit_reference_z=roof_base_z,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                material_role="roof",
            ),
            _rect_segment(
                managed_slot="roof_parapet_front",
                spawn_label=f"{normalized.label_prefix}_RoofParapetFront",
                center_x=normalized.center_x,
                center_y=front_y,
                center_z=parapet_center_z,
                width_cm=outer_w,
                depth_cm=parapet_thickness,
                height_cm=parapet_height,
                mount_type="roof",
                structural_role="roof_parapet",
                structure_piece_role="roof_closure",
                support_fit_reference_z=roof_base_z + roof_slab_thickness,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                material_role="trim",
            ),
            _rect_segment(
                managed_slot="roof_parapet_back",
                spawn_label=f"{normalized.label_prefix}_RoofParapetBack",
                center_x=normalized.center_x,
                center_y=back_y,
                center_z=parapet_center_z,
                width_cm=outer_w,
                depth_cm=parapet_thickness,
                height_cm=parapet_height,
                mount_type="roof",
                structural_role="roof_parapet",
                structure_piece_role="roof_closure",
                support_fit_reference_z=roof_base_z + roof_slab_thickness,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                material_role="trim",
            ),
            _rect_segment(
                managed_slot="roof_parapet_left",
                spawn_label=f"{normalized.label_prefix}_RoofParapetLeft",
                center_x=left_x,
                center_y=normalized.center_y,
                center_z=parapet_center_z,
                width_cm=parapet_thickness,
                depth_cm=outer_d + (parapet_thickness * 2.0),
                height_cm=parapet_height,
                mount_type="roof",
                structural_role="roof_parapet",
                structure_piece_role="roof_closure",
                support_fit_reference_z=roof_base_z + roof_slab_thickness,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                material_role="trim",
            ),
            _rect_segment(
                managed_slot="roof_parapet_right",
                spawn_label=f"{normalized.label_prefix}_RoofParapetRight",
                center_x=right_x,
                center_y=normalized.center_y,
                center_z=parapet_center_z,
                width_cm=parapet_thickness,
                depth_cm=outer_d + (parapet_thickness * 2.0),
                height_cm=parapet_height,
                mount_type="roof",
                structural_role="roof_parapet",
                structure_piece_role="roof_closure",
                support_fit_reference_z=roof_base_z + roof_slab_thickness,
                structure_story=story_index,
                circulation_protected=True,
                opening_protected=True,
                material_role="trim",
            ),
        ]
    )
    return {
        "style": "parapet",
        "eave_z": round(roof_base_z, 3),
        "ridge_z": round(roof_base_z + roof_slab_thickness + parapet_height, 3),
        "slab": {
            "slot": "roof_slab",
            "expected_location": [round(normalized.center_x, 3), round(normalized.center_y, 3), round(roof_slab_z, 3)],
            "expected_rotation": [0.0, 0.0, 0.0],
            "expected_scale": [round(outer_w / CUBE_SIZE_CM, 3), round(outer_d / CUBE_SIZE_CM, 3), round(roof_slab_thickness / CUBE_SIZE_CM, 3)],
        },
        "parapets": [
            {"slot": "roof_parapet_front"},
            {"slot": "roof_parapet_back"},
            {"slot": "roof_parapet_left"},
            {"slot": "roof_parapet_right"},
        ],
    }


def build_house_structure_plan(spec: HouseSpec) -> dict[str, Any]:
    normalized = normalize_house_spec(spec)
    if normalized.story_count > 2:
        return _build_multi_story_house_structure_plan(normalized)
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
        span_x_min = interior_min_x
        span_x_max = interior_max_x
        span_y_min = interior_min_y
        span_y_max = interior_max_y
        horizontal_span = inner_w
    else:
        span_x_min = outer_min_x
        span_x_max = outer_max_x
        span_y_min = outer_min_y
        span_y_max = outer_max_y
        horizontal_span = outer_w

    front_segment_length = max(20.0, (horizontal_span - normalized.door_width_cm) / 2.0)
    if normalized.corner_join_style == "butt_join" and normalized.grid_safe_joints and normalized.grid_snap_cm > 0.0:
        joint_unit = max(normalized.grid_snap_cm, 1.0) * 2.0
        snapped_segment_length = round(front_segment_length / joint_unit) * joint_unit
        front_segment_length = max(20.0, min(horizontal_span / 2.0, snapped_segment_length))
    effective_door_width = max(80.0, horizontal_span - (front_segment_length * 2.0))

    stair_total_rise = story_h + slab_t
    step_rise = max(10.0, min(normalized.stair_step_rise_cm, stair_total_rise / max(1, normalized.stair_step_count)))
    step_count = max(1, int(round(stair_total_rise / step_rise)))
    step_rise = stair_total_rise / step_count
    step_run = normalized.stair_step_run_cm
    stair_side = _stair_side_from_spec(normalized)
    if stair_side == "right":
        stair_start_x = normalized.center_x + (inner_w / 2.0) - (normalized.stair_width_cm / 2.0) - 40.0
    else:
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
            material_role="floor",
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
                material_role="floor",
            )
        )

    functional_openings: list[dict[str, Any]] = []
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
                    material_role="trim",
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
                    material_role="trim",
                ),
            ]
        )

    _append_house_story_walls(
        segments,
        normalized=normalized,
        story_prefix="story1",
        story_index=1,
        wall_bottom_z=normalized.support_z + slab_t,
        front_y=front_y,
        back_y=back_y,
        left_x=left_x,
        right_x=right_x,
        span_x_min=span_x_min,
        span_x_max=span_x_max,
        span_y_min=span_y_min,
        span_y_max=span_y_max,
        effective_door_width=effective_door_width,
        front_has_door=True,
        functional_openings=functional_openings,
        outer_min_x=outer_min_x,
        outer_max_x=outer_max_x,
        outer_min_y=outer_min_y,
        outer_max_y=outer_max_y,
        floor_surface_z=normalized.support_z + slab_t,
    )
    _append_house_story_walls(
        segments,
        normalized=normalized,
        story_prefix="story2",
        story_index=2,
        wall_bottom_z=normalized.support_z + story_h + slab_t,
        front_y=front_y,
        back_y=back_y,
        left_x=left_x,
        right_x=right_x,
        span_x_min=span_x_min,
        span_x_max=span_x_max,
        span_y_min=span_y_min,
        span_y_max=span_y_max,
        effective_door_width=effective_door_width,
        front_has_door=False,
        functional_openings=functional_openings,
        outer_min_x=outer_min_x,
        outer_max_x=outer_max_x,
        outer_min_y=outer_min_y,
        outer_max_y=outer_max_y,
        floor_surface_z=normalized.support_z + story_h + slab_t,
    )

    _append_story_balcony_segments(
        segments,
        normalized=normalized,
        story_index=2,
        span_x_min=span_x_min,
        span_x_max=span_x_max,
        front_y=front_y,
        back_y=back_y,
        floor_surface_z=normalized.support_z + story_h + slab_t,
    )

    if normalized.roof_style == "parapet":
        roof_envelope = _add_parapet_roof_segments(
            segments,
            normalized=normalized,
            roof_base_z=roof_base_z,
            outer_w=outer_w,
            outer_d=outer_d,
            story_index=3,
        )
    else:
        roof_envelope = _add_house_gable_roof_segments(
            segments,
            normalized=normalized,
            roof_base_z=roof_base_z,
            outer_w=outer_w,
            outer_d=outer_d,
            horizontal_span=horizontal_span,
            front_y=front_y,
            back_y=back_y,
            story_index=3,
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
                material_role="trim",
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
            "side": stair_side,
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
    return {
        "structure_type": "house",
        "story_count": 2,
        "spec": normalized,
        "footprint": house_footprint(normalized),
        "circulation_plan": circulation_plan,
        "reserved_volumes": [stairwell_opening, stair_arrival, front_door_opening],
        "functional_openings": [stairwell_opening, front_door_opening, *functional_openings],
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


def _build_multi_story_house_structure_plan(normalized: HouseSpec) -> dict[str, Any]:
    t = normalized.wall_thickness_cm
    story_h = normalized.story_height_cm
    slab_t = normalized.floor_thickness_cm
    story_count = max(3, int(normalized.story_count))
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
    roof_base_z = normalized.support_z + (story_count * story_h) + ((story_count - 1) * slab_t)

    if normalized.corner_join_style == "butt_join":
        span_x_min = interior_min_x
        span_x_max = interior_max_x
        span_y_min = interior_min_y
        span_y_max = interior_max_y
        horizontal_span = inner_w
    else:
        span_x_min = outer_min_x
        span_x_max = outer_max_x
        span_y_min = outer_min_y
        span_y_max = outer_max_y
        horizontal_span = outer_w

    front_segment_length = max(20.0, (horizontal_span - normalized.door_width_cm) / 2.0)
    if normalized.corner_join_style == "butt_join" and normalized.grid_safe_joints and normalized.grid_snap_cm > 0.0:
        joint_unit = max(normalized.grid_snap_cm, 1.0) * 2.0
        snapped_segment_length = round(front_segment_length / joint_unit) * joint_unit
        front_segment_length = max(20.0, min(horizontal_span / 2.0, snapped_segment_length))
    effective_door_width = max(90.0, horizontal_span - (front_segment_length * 2.0))

    stair_total_rise = story_h + slab_t
    step_rise = max(10.0, min(normalized.stair_step_rise_cm, stair_total_rise / max(1, normalized.stair_step_count)))
    step_count = max(1, int(round(stair_total_rise / step_rise)))
    step_rise = stair_total_rise / step_count
    step_run = normalized.stair_step_run_cm
    stair_side = _stair_side_from_spec(normalized)
    if stair_side == "right":
        stair_start_x = normalized.center_x + (inner_w / 2.0) - (normalized.stair_width_cm / 2.0) - 40.0
    else:
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

    def rect_center(min_value: float, max_value: float) -> float:
        return round((min_value + max_value) / 2.0, 3)

    def rect_size(min_value: float, max_value: float) -> float:
        return round(max(0.0, max_value - min_value), 3)

    def floor_center_z(story_index: int) -> float:
        return normalized.support_z + ((story_index - 1) * (story_h + slab_t)) + (slab_t / 2.0)

    def wall_center_z(story_index: int) -> float:
        return normalized.support_z + ((story_index - 1) * (story_h + slab_t)) + slab_t + (story_h / 2.0)

    def floor_support_z(story_index: int) -> float:
        return normalized.support_z + ((story_index - 1) * (story_h + slab_t)) - slab_t

    functional_openings: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = [
        _rect_segment(
            managed_slot="floor_ground",
            spawn_label=f"{normalized.label_prefix}_FloorGround",
            center_x=normalized.center_x,
            center_y=normalized.center_y,
            center_z=floor_center_z(1),
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
            material_role="floor",
        )
    ]

    for story_index in range(2, story_count + 1):
        upper_floor_rects = [
            (f"floor_story{story_index}_left", f"{normalized.label_prefix}_FloorStory{story_index:02d}Left", outer_min_x, stair_x_min, outer_min_y, outer_max_y, "floor_slab"),
            (f"floor_story{story_index}_right", f"{normalized.label_prefix}_FloorStory{story_index:02d}Right", stair_x_max, outer_max_x, outer_min_y, outer_max_y, "floor_slab"),
            (f"floor_story{story_index}_front", f"{normalized.label_prefix}_FloorStory{story_index:02d}Front", stair_x_min, stair_x_max, outer_min_y, stair_opening_min_y, "floor_slab"),
            (f"landing_story{story_index}", f"{normalized.label_prefix}_LandingStory{story_index:02d}", stair_x_min, stair_x_max, landing_y_min, outer_max_y, "landing"),
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
                    center_z=floor_center_z(story_index),
                    width_cm=width_cm,
                    depth_cm=depth_cm,
                    height_cm=slab_t,
                    mount_type="floor",
                    structural_role="elevated_floor",
                    structure_piece_role=role_name,
                    support_fit_reference_z=floor_support_z(story_index),
                    structure_story=story_index,
                    allowed_reserved_volume_kinds=["landing_clearance"] if role_name == "landing" and story_index == story_count else [],
                    circulation_protected=True,
                    opening_protected=True,
                    material_role="floor",
                )
            )

        guard_depth = rect_size(stair_opening_min_y, landing_y_max)
        if guard_depth >= 20.0:
            upper_floor_surface_z = normalized.support_z + ((story_index - 1) * (story_h + slab_t)) + slab_t
            segments.extend(
                [
                    _rect_segment(
                        managed_slot=f"stair_guard_outer_story{story_index}",
                        spawn_label=f"{normalized.label_prefix}_StairGuardOuterStory{story_index:02d}",
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
                        structure_story=story_index,
                        circulation_protected=True,
                        opening_protected=True,
                    ),
                    _rect_segment(
                        managed_slot=f"stair_guard_front_story{story_index}",
                        spawn_label=f"{normalized.label_prefix}_StairGuardFrontStory{story_index:02d}",
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
                        structure_story=story_index,
                        circulation_protected=True,
                        opening_protected=True,
                    ),
                ]
            )

    for story_index in range(1, story_count + 1):
        _append_house_story_walls(
            segments,
            normalized=normalized,
            story_prefix=f"story{story_index}",
            story_index=story_index,
            wall_bottom_z=normalized.support_z + ((story_index - 1) * (story_h + slab_t)) + slab_t,
            front_y=front_y,
            back_y=back_y,
            left_x=left_x,
            right_x=right_x,
            span_x_min=span_x_min,
            span_x_max=span_x_max,
            span_y_min=span_y_min,
            span_y_max=span_y_max,
            effective_door_width=effective_door_width,
            front_has_door=story_index == 1,
            functional_openings=functional_openings,
            outer_min_x=outer_min_x,
            outer_max_x=outer_max_x,
            outer_min_y=outer_min_y,
            outer_max_y=outer_max_y,
            floor_surface_z=normalized.support_z + ((story_index - 1) * (story_h + slab_t)) + slab_t,
        )
        _append_story_balcony_segments(
            segments,
            normalized=normalized,
            story_index=story_index,
            span_x_min=span_x_min,
            span_x_max=span_x_max,
            front_y=front_y,
            back_y=back_y,
            floor_surface_z=normalized.support_z + ((story_index - 1) * (story_h + slab_t)) + slab_t,
        )

    if normalized.roof_style == "parapet":
        roof_envelope = _add_parapet_roof_segments(
            segments,
            normalized=normalized,
            roof_base_z=roof_base_z,
            outer_w=outer_w,
            outer_d=outer_d,
            story_index=story_count + 1,
        )
    else:
        roof_envelope = _add_house_gable_roof_segments(
            segments,
            normalized=normalized,
            roof_base_z=roof_base_z,
            outer_w=outer_w,
            outer_d=outer_d,
            horizontal_span=horizontal_span,
            front_y=front_y,
            back_y=back_y,
            story_index=story_count + 1,
        )

    for flight_index in range(1, story_count):
        flight_base_z = normalized.support_z + ((flight_index - 1) * (story_h + slab_t))
        for step_index in range(step_count):
            step_center_z = flight_base_z + ((step_index + 0.5) * step_rise)
            step_center_y = stair_start_y + (step_index * step_run)
            segments.append(
                _rect_segment(
                    managed_slot=f"stair_story{flight_index}_{step_index + 1:02d}",
                    spawn_label=f"{normalized.label_prefix}_StairStory{flight_index:02d}_{step_index + 1:02d}",
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
                    structure_story=flight_index,
                    circulation_protected=True,
                    opening_protected=True,
                    material_role="trim",
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
        max_z=normalized.support_z + ((story_count - 1) * (story_h + slab_t)) + slab_t + 5.0,
    )
    stair_arrival = _rect_volume(
        name="stair_arrival_clearance",
        kind="landing_clearance",
        min_x=stair_x_min,
        max_x=stair_x_max,
        min_y=landing_y_min,
        max_y=landing_y_max,
        min_z=normalized.support_z + ((story_count - 1) * (story_h + slab_t)) + 5.0,
        max_z=normalized.support_z + ((story_count - 1) * (story_h + slab_t)) + min(story_h - 20.0, 220.0),
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
        "stair_kind": "stacked_straight_runs",
        "stair_run": {
            "side": stair_side,
            "start": [round(stair_start_x, 3), round(stair_start_y, 3), round(normalized.support_z, 3)],
            "step_run_cm": round(step_run, 3),
            "step_rise_cm": round(step_rise, 3),
            "step_count": step_count,
            "flight_count": story_count - 1,
            "top_exit_y": round(top_step_back_y, 3),
        },
        "stairwell_opening": {
            "min": stairwell_opening["min"],
            "max": stairwell_opening["max"],
        },
        "landing_zone": {
            "min": [round(stair_x_min, 3), round(landing_y_min, 3), round(normalized.support_z + ((story_count - 1) * (story_h + slab_t)), 3)],
            "max": [round(stair_x_max, 3), round(outer_max_y, 3), round(normalized.support_z + ((story_count - 1) * (story_h + slab_t)) + slab_t, 3)],
        },
    }
    return {
        "structure_type": "house",
        "story_count": story_count,
        "spec": normalized,
        "footprint": house_footprint(normalized),
        "circulation_plan": circulation_plan,
        "reserved_volumes": [stairwell_opening, stair_arrival, front_door_opening],
        "functional_openings": [stairwell_opening, front_door_opening, *functional_openings],
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

    def add_story_wall_segments(story_prefix: str, wall_center_z_value: float, front_has_door: bool, story_index: int) -> None:
        segments.extend(
            [
                _rect_segment(
                    managed_slot=f"{story_prefix}_wall_back",
                    spawn_label=f"{normalized.label_prefix}_{story_prefix}_Back",
                    center_x=normalized.center_x,
                    center_y=back_y,
                    center_z=wall_center_z_value,
                    width_cm=horizontal_span,
                    depth_cm=t,
                    height_cm=story_h,
                    mount_type="wall",
                    structural_role="wall_base",
                    structure_piece_role="wall_span",
                    structure_story=story_index,
                    circulation_protected=True,
                    opening_protected=True,
                    material_role="trim",
                ),
                _rect_segment(
                    managed_slot=f"{story_prefix}_wall_left",
                    spawn_label=f"{normalized.label_prefix}_{story_prefix}_Left",
                    center_x=left_x,
                    center_y=normalized.center_y,
                    center_z=wall_center_z_value,
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
                    center_z=wall_center_z_value,
                    width_cm=t,
                    depth_cm=outer_d,
                    height_cm=story_h,
                    mount_type="wall",
                    structural_role="wall_base",
                    structure_piece_role="wall_span",
                    structure_story=story_index,
                    circulation_protected=True,
                    opening_protected=True,
                    material_role="trim",
                ),
            ]
        )
        if front_has_door:
            door_header_center_z = normalized.support_z + slab_t + normalized.door_height_cm + (door_header_height / 2.0)
            segments.extend(
                [
                    _rect_segment(
                        managed_slot=f"{story_prefix}_wall_front_left",
                        spawn_label=f"{normalized.label_prefix}_{story_prefix}_FrontLeft",
                        center_x=door_left_center_x,
                        center_y=front_y,
                        center_z=wall_center_z_value,
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
                        center_z=wall_center_z_value,
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
                    center_z=wall_center_z_value,
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

    for story_index in range(1, story_count + 1):
        add_story_wall_segments(
            f"story{story_index}",
            wall_center_z(story_index),
            story_index == 1,
            story_index,
        )

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
                    structure_story=story_count + 1,
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
                "structure_story": story_count + 1,
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
                "structure_story": story_count + 1,
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
                "structure_story": story_count + 1,
                "circulation_protected": True,
                "opening_protected": True,
            },
        ]
    )

    for flight_index in range(1, story_count):
        flight_base_z = normalized.support_z + ((flight_index - 1) * (story_h + slab_t))
        for step_index in range(step_count):
            step_center_z = flight_base_z + ((step_index + 0.5) * step_rise)
            step_center_y = stair_start_y + (step_index * step_run)
            segments.append(
                _rect_segment(
                    managed_slot=f"stair_story{flight_index}_{step_index + 1:02d}",
                    spawn_label=f"{normalized.label_prefix}_StairStory{flight_index:02d}_{step_index + 1:02d}",
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
                    structure_story=flight_index,
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
        max_z=normalized.support_z + ((story_count - 1) * (story_h + slab_t)) + slab_t + 5.0,
    )
    stair_arrival = _rect_volume(
        name="stair_arrival_clearance",
        kind="landing_clearance",
        min_x=stair_x_min,
        max_x=stair_x_max,
        min_y=landing_y_min,
        max_y=landing_y_max,
        min_z=normalized.support_z + ((story_count - 1) * (story_h + slab_t)) + 5.0,
        max_z=normalized.support_z + ((story_count - 1) * (story_h + slab_t)) + min(story_h - 20.0, 220.0),
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
        "stair_kind": "stacked_straight_runs",
        "stair_run": {
            "start": [round(stair_start_x, 3), round(stair_start_y, 3), round(normalized.support_z, 3)],
            "step_run_cm": round(step_run, 3),
            "step_rise_cm": round(step_rise, 3),
            "step_count": step_count,
            "flight_count": story_count - 1,
            "top_exit_y": round(top_step_back_y, 3),
        },
        "stairwell_opening": {
            "min": stairwell_opening["min"],
            "max": stairwell_opening["max"],
        },
        "landing_zone": {
            "min": [round(stair_x_min, 3), round(landing_y_min, 3), round(normalized.support_z + ((story_count - 1) * (story_h + slab_t)), 3)],
            "max": [round(stair_x_max, 3), round(outer_max_y, 3), round(normalized.support_z + ((story_count - 1) * (story_h + slab_t)) + slab_t, 3)],
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
        "story_count": story_count,
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
            "material_role": str(segment.get("material_role") or "body"),
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
                "asset_path": str(segment.get("asset_path") or normalized.asset_path),
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
    chosen_metrics = _candidate_site_metrics(
        min_xy=list(footprint["min_xy"]),
        max_xy=list(footprint["max_xy"]),
        support_z=float(footprint["support_z"]),
        top_z=float(footprint["top_z"]),
        scene_actors=scene_actors,
        ignore_actor_paths=ignore_actor_paths,
        ignore_actor_labels=ignore_actor_labels,
    )
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
            "nearest_clearance_cm": chosen_metrics["nearest_clearance_cm"],
            "nearby_actor_count": chosen_metrics["nearby_actor_count"],
            "tried_positions": [{"center": [normalized.center_x, normalized.center_y], "conflict_count": 0, "nearest_clearance_cm": chosen_metrics["nearest_clearance_cm"], "nearby_actor_count": chosen_metrics["nearby_actor_count"]}],
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
        candidate_metrics = _candidate_site_metrics(
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
                "nearest_clearance_cm": candidate_metrics["nearest_clearance_cm"],
                "nearby_actor_count": candidate_metrics["nearby_actor_count"],
            }
        )
        better_candidate = (
            len(conflicts) < len(chosen_conflicts)
            or (
                len(conflicts) == len(chosen_conflicts)
                and (
                    candidate_metrics["nearby_actor_count"] < chosen_metrics["nearby_actor_count"]
                    or (
                        candidate_metrics["nearby_actor_count"] == chosen_metrics["nearby_actor_count"]
                        and candidate_metrics["nearest_clearance_cm"] > chosen_metrics["nearest_clearance_cm"]
                    )
                )
            )
        )
        if better_candidate:
            chosen_spec = candidate
            chosen_conflicts = conflicts
            chosen_metrics = candidate_metrics
    return {
        "spec": chosen_spec,
        "relocated": chosen_spec.center_x != normalized.center_x or chosen_spec.center_y != normalized.center_y,
        "offset_cm": [round(chosen_spec.center_x - normalized.center_x, 3), round(chosen_spec.center_y - normalized.center_y, 3)],
        "conflict_count": len(chosen_conflicts),
        "blocking_conflicts": chosen_conflicts,
        "nearest_clearance_cm": chosen_metrics["nearest_clearance_cm"],
        "nearby_actor_count": chosen_metrics["nearby_actor_count"],
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
            "material_role": str(segment.get("material_role") or "body"),
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
                "asset_path": str(segment.get("asset_path") or normalized.asset_path),
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
