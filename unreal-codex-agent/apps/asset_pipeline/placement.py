"""Placement intelligence — AI-driven scene-aware asset placement via MCP."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from .models import AssetRecord
from .ai_client import chat


# Default MCP bridge URL (UEFN Toolbelt — POST to root, no /execute path)
DEFAULT_MCP_URL = "http://127.0.0.1:8765"


def query_scene_context(mcp_url: str = DEFAULT_MCP_URL) -> dict[str, Any]:
    """Query UEFN scene via MCP to understand current level layout.

    Returns a dict with actors, terrain info, building footprints, etc.
    """
    try:
        # Get all actors in the current level
        payload = json.dumps({
            "command": "get_all_actors",
            "params": {}
        }).encode()
        req = urllib.request.Request(
            mcp_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            actors_data = json.loads(resp.read().decode())
    except Exception:
        actors_data = {"actors": [], "error": "Could not query scene"}

    # Categorize actors for placement intelligence
    buildings = []
    terrain = []
    props = []
    devices = []

    for actor in actors_data.get("actors", []):
        name = (actor.get("name") or "").lower()
        actor_class = (actor.get("class") or "").lower()
        location = actor.get("location", {})

        entry = {
            "name": actor.get("name"),
            "class": actor.get("class"),
            "location": location,
        }

        if any(kw in name or kw in actor_class for kw in ("building", "house", "wall", "roof", "floor", "structure")):
            buildings.append(entry)
        elif any(kw in name or kw in actor_class for kw in ("landscape", "terrain", "ground")):
            terrain.append(entry)
        elif any(kw in name or kw in actor_class for kw in ("device", "trigger", "spawner", "zone")):
            devices.append(entry)
        else:
            props.append(entry)

    return {
        "total_actors": len(actors_data.get("actors", [])),
        "buildings": buildings[:20],  # Limit for context window
        "terrain": terrain[:5],
        "props": props[:30],
        "devices": devices[:10],
        "raw_error": actors_data.get("error"),
    }


def suggest_placement(
    record: AssetRecord,
    scene_context: dict[str, Any],
) -> dict[str, Any]:
    """Use AI to determine the best placement for an asset in the scene.

    Args:
        record: The asset to place.
        scene_context: Result from query_scene_context().

    Returns:
        Dict with suggested position, rotation, reasoning.
    """
    buildings_text = ""
    if scene_context.get("buildings"):
        buildings_text = "\nBuildings in scene:\n" + "\n".join(
            f"  - {b['name']} at ({b['location'].get('x', 0):.0f}, {b['location'].get('y', 0):.0f}, {b['location'].get('z', 0):.0f})"
            for b in scene_context["buildings"][:10]
        )

    props_text = ""
    if scene_context.get("props"):
        props_text = "\nExisting props:\n" + "\n".join(
            f"  - {p['name']} at ({p['location'].get('x', 0):.0f}, {p['location'].get('y', 0):.0f}, {p['location'].get('z', 0):.0f})"
            for p in scene_context["props"][:15]
        )

    prompt = f"""You are a UEFN level designer AI. Given a scene with {scene_context['total_actors']} actors and
a new asset to place, suggest the best location.

Asset: "{record.name}" (category: {record.category})
Original prompt: "{record.prompt}"
{buildings_text}
{props_text}

Rules:
- Furniture goes INSIDE buildings (between walls, on floors)
- Rocks/nature go on terrain, near edges or paths
- Vehicles go on roads or flat ground
- Weapons/pickups go on tables, shelves, or ground near spawn points
- Decorations go on walls or near buildings
- Characters go at spawn points or patrol paths

Respond as JSON:
{{"position": {{"x": 0, "y": 0, "z": 0}}, "rotation": {{"yaw": 0}}, "scale": 1.0, "reasoning": "explanation", "placement_type": "interior|exterior|terrain|elevated"}}"""

    try:
        raw = chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
        )
    except Exception as e:
        return {
            "position": {"x": 0, "y": 0, "z": 100},
            "rotation": {"yaw": 0},
            "scale": 1.0,
            "reasoning": f"AI placement failed ({e}), using default position",
            "placement_type": "terrain",
        }

    import re
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {
                "position": data.get("position", {"x": 0, "y": 0, "z": 100}),
                "rotation": data.get("rotation", {"yaw": 0}),
                "scale": data.get("scale", 1.0),
                "reasoning": data.get("reasoning", "AI suggestion"),
                "placement_type": data.get("placement_type", "terrain"),
            }
        except json.JSONDecodeError:
            pass

    return {
        "position": {"x": 0, "y": 0, "z": 100},
        "rotation": {"yaw": 0},
        "scale": 1.0,
        "reasoning": raw.strip()[:200],
        "placement_type": "terrain",
    }


def place_asset(
    record: AssetRecord,
    position: dict[str, float],
    rotation: dict[str, float] | None = None,
    scale: float = 1.0,
    mcp_url: str = DEFAULT_MCP_URL,
) -> dict[str, Any]:
    """Place an asset in UEFN at the specified position via MCP.

    Args:
        record: The asset to place (must have uefn_path set).
        position: {"x": float, "y": float, "z": float}
        rotation: Optional {"yaw": float, "pitch": float, "roll": float}
        scale: Uniform scale factor.
        mcp_url: MCP bridge URL.

    Returns:
        Dict with success status and placed actor info.
    """
    if not record.uefn_import_path:
        return {"success": False, "error": "Asset not imported to UEFN yet — no uefn_path set."}

    rot = rotation or {"yaw": 0, "pitch": 0, "roll": 0}

    payload = json.dumps({
        "command": "spawn_actor",
        "params": {
            "asset_path": record.uefn_import_path,
            "location": [position.get("x", 0), position.get("y", 0), position.get("z", 0)],
            "rotation": [rot.get("pitch", 0), rot.get("yaw", 0), rot.get("roll", 0)],
        }
    }).encode()

    try:
        req = urllib.request.Request(
            mcp_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
    except Exception as e:
        return {"success": False, "error": f"MCP placement failed: {e}"}

    return {
        "success": True,
        "actor_name": result.get("actor_name", record.name),
        "position": position,
        "rotation": rot,
        "scale": scale,
    }
