from __future__ import annotations

import json
from typing import Any

from ue_runtime import load_unreal

unreal = load_unreal(("EditorLevelLibrary",))


def _vector_to_list(value: Any) -> list[float]:
    try:
        return [float(value.x), float(value.y), float(value.z)]
    except Exception:
        return [0.0, 0.0, 0.0]


def _rotator_to_list(value: Any) -> list[float]:
    try:
        return [float(value.roll), float(value.pitch), float(value.yaw)]
    except Exception:
        try:
            return [float(value.x), float(value.y), float(value.z)]
        except Exception:
            return [0.0, 0.0, 0.0]


def _actor_asset_path(actor: Any) -> str | None:
    try:
        smc = actor.get_editor_property("static_mesh_component")
        if smc:
            mesh = smc.get_editor_property("static_mesh")
            if mesh:
                return str(mesh.get_path_name())
    except Exception:
        pass
    try:
        class_obj = actor.get_class()
        if class_obj:
            return str(class_obj.get_path_name())
    except Exception:
        pass
    return None


def _actor_category(actor: Any) -> str | None:
    try:
        tags = actor.tags
        for tag in tags:
            tag_text = str(tag)
            if tag_text.startswith("category="):
                return tag_text.split("=", 1)[1]
    except Exception:
        pass
    return None


def export_scene_state() -> dict[str, Any]:
    if unreal is None:
        raise RuntimeError("Unreal Python API is not available in this environment.")
    map_name = ""
    actors_out: list[dict[str, Any]] = []
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        if world is not None:
            map_name = str(world.get_name())
    except Exception:
        map_name = ""
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        actors = []
    for actor in actors:
        try:
            label = actor.get_actor_label()
        except Exception:
            label = str(actor)
        try:
            actor_name = actor.get_name()
        except Exception:
            actor_name = label
        try:
            actor_class = actor.get_class().get_name()
        except Exception:
            actor_class = "Unknown"
        try:
            location = _vector_to_list(actor.get_actor_location())
        except Exception:
            location = [0.0, 0.0, 0.0]
        try:
            rotation = _rotator_to_list(actor.get_actor_rotation())
        except Exception:
            rotation = [0.0, 0.0, 0.0]
        try:
            scale = _vector_to_list(actor.get_actor_scale3d())
        except Exception:
            scale = [1.0, 1.0, 1.0]
        try:
            bounds_origin, bounds_extent = actor.get_actor_bounds(False)
            bounds_cm = {"origin": _vector_to_list(bounds_origin), "box_extent": _vector_to_list(bounds_extent)}
        except Exception:
            bounds_cm = {}
        actors_out.append(
            {
                "label": label,
                "actor_name": actor_name,
                "class_name": actor_class,
                "asset_path": _actor_asset_path(actor),
                "category": _actor_category(actor),
                "location": location,
                "rotation": rotation,
                "scale": scale,
                "bounds_cm": bounds_cm,
                "room_type": "unknown",
            }
        )
    return {
        "map_name": map_name or "UnknownMap",
        "actors": actors_out,
        "dirty_actor_ids": [],
        "dirty_bounds": {},
        "room_type": "unknown",
        "shell_sensitive": False,
        "clearance_observations": {},
        "shell_alignment": {"inside_checked": False, "outside_checked": False, "is_consistent": None},
        "collision_issues": [],
    }


if __name__ == "__main__":
    try:
        result = export_scene_state()
    except Exception as exc:
        result = {"status": "error", "reason": str(exc)}
    print(json.dumps(result, indent=2))
