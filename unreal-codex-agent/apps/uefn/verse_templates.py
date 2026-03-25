from __future__ import annotations

import json
import re
from typing import Any


def sanitize_verse_identifier(value: str, fallback: str = "UCA_GeneratedDevice") -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", value or "").strip("_")
    if not text:
        text = fallback
    if not text[0].isalpha() and text[0] != "_":
        text = f"_{text}"
    return text


def _comment_block(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    lines = rendered.splitlines() or ["{}"]
    return "\n".join(f"# {line}" for line in lines)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_triplet(value: Any) -> list[float] | None:
    if isinstance(value, dict):
        return [
            _safe_float(value.get("x")),
            _safe_float(value.get("y")),
            _safe_float(value.get("z")),
        ]
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return [
            _safe_float(value[0]),
            _safe_float(value[1]),
            _safe_float(value[2]),
        ]
    return None


def _float_literal(value: Any) -> str:
    number = _safe_float(value)
    rounded = round(number, 3)
    if abs(rounded - int(rounded)) < 0.0005:
        return f"{int(rounded)}.0"
    return f"{rounded:.3f}".rstrip("0").rstrip(".") + ("" if "." in f"{rounded:.3f}" else ".0")


def _vector_literal(value: Any) -> str:
    vector = _safe_triplet(value) or [0.0, 0.0, 0.0]
    return (
        f"vector3{{X:={_float_literal(vector[0])}, "
        f"Y:={_float_literal(vector[1])}, "
        f"Z:={_float_literal(vector[2])}}}"
    )


def _offset_vector(value: Any, *, z: float = 0.0) -> str:
    vector = _safe_triplet(value) or [0.0, 0.0, 0.0]
    vector[2] += z
    return _vector_literal(vector)


def _build_draw_statements(debug_name: str, debug_overlay: dict[str, Any]) -> list[str]:
    target_location = _safe_triplet(debug_overlay.get("target_location"))
    ground_anchor = _safe_triplet(debug_overlay.get("ground_anchor"))
    landscape_anchor = _safe_triplet(debug_overlay.get("landscape_anchor"))
    plane_anchor = _safe_triplet(debug_overlay.get("plane_anchor"))
    corner_anchor = _safe_triplet(debug_overlay.get("corner_anchor"))
    surface_anchor = _safe_triplet(debug_overlay.get("surface_anchor"))
    dirty_bounds = dict(debug_overlay.get("dirty_bounds") or {})
    bounds_origin = _safe_triplet(dirty_bounds.get("origin"))
    bounds_extent = _safe_triplet(dirty_bounds.get("box_extent"))
    lines: list[str] = []
    has_structural_context = any(
        anchor is not None
        for anchor in (ground_anchor, landscape_anchor, plane_anchor, corner_anchor, surface_anchor)
    ) or (bounds_origin is not None and bounds_extent is not None)

    if bounds_origin and bounds_extent:
        lines.append(
            f"        {debug_name}.DrawBox({_vector_literal(bounds_origin)}, rotation{{}}, "
            f"?Extent := {_vector_literal(bounds_extent)}, "
            "?Color := MakeColorFromSRGBValues(96, 125, 139), "
            "?Thickness := 4.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )

    if ground_anchor:
        lines.append(
            f"        {debug_name}.DrawPoint(Position := {_vector_literal(ground_anchor)}, "
            "?Color := MakeColorFromSRGBValues(64, 220, 96), "
            "?Thickness := 45.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )
        lines.append(
            f"        {debug_name}.DrawSphere(Center := {_vector_literal(ground_anchor)}, "
            "?Radius := 50.0, "
            "?Color := MakeColorFromSRGBValues(64, 220, 96), "
            "?Thickness := 3.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )

    if landscape_anchor and landscape_anchor != ground_anchor:
        lines.append(
            f"        {debug_name}.DrawPoint(Position := {_vector_literal(landscape_anchor)}, "
            "?Color := MakeColorFromSRGBValues(0, 191, 255), "
            "?Thickness := 40.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )

    if target_location and has_structural_context:
        lines.append(
            f"        {debug_name}.DrawSphere(Center := {_vector_literal(target_location)}, "
            "?Radius := 70.0, "
            "?Color := MakeColorFromSRGBValues(255, 215, 0), "
            "?Thickness := 5.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )
        lines.append(
            f"        {debug_name}.DrawPoint(Position := {_vector_literal(target_location)}, "
            "?Color := MakeColorFromSRGBValues(255, 255, 255), "
            "?Thickness := 60.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )

    if ground_anchor and target_location and target_location != ground_anchor:
        lines.append(
            f"        {debug_name}.DrawArrow({_vector_literal(ground_anchor)}, {_vector_literal(target_location)}, "
            "?ArrowSize := 70.0, "
            "?Color := MakeColorFromSRGBValues(255, 215, 0), "
            "?Thickness := 6.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )

    if plane_anchor:
        lines.append(
            f"        {debug_name}.DrawPoint(Position := {_vector_literal(plane_anchor)}, "
            "?Color := MakeColorFromSRGBValues(255, 99, 71), "
            "?Thickness := 36.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )

    if corner_anchor:
        lines.append(
            f"        {debug_name}.DrawPoint(Position := {_vector_literal(corner_anchor)}, "
            "?Color := MakeColorFromSRGBValues(186, 85, 211), "
            "?Thickness := 36.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )

    if surface_anchor:
        lines.append(
            f"        {debug_name}.DrawPoint(Position := {_vector_literal(surface_anchor)}, "
            "?Color := MakeColorFromSRGBValues(255, 140, 0), "
            "?Thickness := 36.0, "
            "?DrawDurationPolicy := debug_draw_duration_policy.Persistent)"
        )
    return lines


def render_placement_coordinator(
    *,
    project_name: str,
    zone_id: str,
    cycle_number: int,
    action_payload: dict[str, Any],
    placement_summary: dict[str, Any],
    debug_overlay: dict[str, Any],
) -> str:
    class_name = sanitize_verse_identifier(f"UCA_PlacementCoordinator_{zone_id}")
    channel_name = sanitize_verse_identifier(f"UCA_DebugDraw_{zone_id}")
    debug_name = sanitize_verse_identifier(f"DebugDraw_{zone_id}", "DebugDraw_UCA")
    support_label = str(debug_overlay.get("support_actor_label") or "none")
    support_kind = str(debug_overlay.get("support_surface_kind") or "unknown")
    draw_lines = _build_draw_statements(debug_name, debug_overlay)
    lines = [
        f"using {{ /Fortnite.com/Devices }}",
        f"using {{ /Verse.org/Simulation }}",
        f"using {{ /Verse.org/SceneGraph }}",
        f"using {{ /UnrealEngine.com/Temporary/Diagnostics }}",
        "",
        "# Generated by unreal-codex-agent for a UEFN-first workflow.",
        "# This version includes a live Verse Debug Draw overlay so the",
        "# latest placement target, support surface, and dirty zone show up",
        "# during playtest when Verse Debug Draw is enabled.",
        "",
        "# Placement intent summary",
        _comment_block(
            {
                "project_name": project_name,
                "zone_id": zone_id,
                "cycle_number": cycle_number,
                "action": action_payload,
                "placement_summary": placement_summary,
                "debug_overlay": debug_overlay,
            }
        ),
        "",
        f"{class_name} := class(creative_device):",
        "    OnBegin<override>() : void =",
        f'        Print("UCA placement coordinator ready for zone {zone_id} (cycle {cycle_number}).")',
        f'        Print("Support surface: {support_label} ({support_kind}).")',
    ]
    if draw_lines:
        lines.insert(3, "using { /Verse.org/Colors }")
        class_index = lines.index(f"{class_name} := class(creative_device):")
        lines[class_index:class_index] = [
            f"{channel_name} := class(debug_draw_channel) {{}}",
            f"{debug_name}:debug_draw = debug_draw{{Channel := {channel_name}}}",
            "",
        ]
        lines.append('        Print("Enable Verse Debug Draw to see the placement overlay markers.")')
        lines.extend(draw_lines)
    else:
        lines.append('        Print("No exported placement overlay is available yet. Re-run the local export and sync this Verse file.")')
    lines.append("")
    return "\n".join(lines)


def render_scene_monitor(
    *,
    project_name: str,
    room_type: str,
    scene_backend: str,
) -> str:
    class_name = sanitize_verse_identifier(f"UCA_SceneMonitor_{room_type}")
    return f"""using {{ /Fortnite.com/Devices }}
using {{ /Verse.org/Simulation }}
using {{ /Verse.org/SceneGraph }}
using {{ /UnrealEngine.com/Temporary/Diagnostics }}

# Generated by unreal-codex-agent for a UEFN-first workflow.
# Use this device as the handoff point between your island's authored devices,
# Scene Graph entities, and the local orchestrator export contract.

{class_name} := class(creative_device):
    OnBegin<override>() : void =
        Print("UCA scene monitor ready for room type {room_type}.")
        Print("Expected scene backend: {scene_backend}.")
        Print("Use the placement coordinator device for live debug markers.")
"""
