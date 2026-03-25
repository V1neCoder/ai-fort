from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from apps.asset_ai.quarantine import REQUIRED_METADATA_KEYS
from apps.developer_overlay.settings import load_project_config
from apps.asset_ai.query_catalog import query_rows
from apps.orchestrator.state_store import SessionStateStore

IDENTIFIED_COLOR = "#33d17a"
UNDEFINED_COLOR = "#ff5a5f"
IGNORED_COLOR = "#7b8698"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_triplet(value: Any, default: list[float]) -> list[float]:
    if isinstance(value, dict):
        return [
            _safe_float(value.get("x"), default[0]),
            _safe_float(value.get("y"), default[1]),
            _safe_float(value.get("z"), default[2]),
        ]
    if isinstance(value, (list, tuple)):
        padded = list(value[:3]) + default[len(value[:3]) :]
        return [
            _safe_float(padded[0], default[0]),
            _safe_float(padded[1], default[1]),
            _safe_float(padded[2], default[2]),
        ]
    return list(default)


def _coerce_scene_state(scene_state: Any) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not isinstance(scene_state, dict):
        warnings.append("scene_state payload was not a JSON object; using an empty fallback scene.")
        scene_state = {}

    raw_actors = scene_state.get("actors")
    if raw_actors is None:
        raw_actors = []
    if not isinstance(raw_actors, list):
        warnings.append("scene_state.actors was not a list; ignoring actor payload.")
        raw_actors = []

    actors: list[dict[str, Any]] = []
    skipped = 0
    for raw_actor in raw_actors:
        if not isinstance(raw_actor, dict):
            skipped += 1
            continue
        actors.append(raw_actor)

    if skipped:
        warnings.append(f"Skipped {skipped} malformed actor entries while building the x-ray report.")

    return (
        {
            "map_name": scene_state.get("map_name") or "UnknownMap",
            "room_type": scene_state.get("room_type") or "unknown",
            "actors": actors,
        },
        warnings,
    )


def _load_catalog_records(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    project = load_project_config(repo_root)
    catalog_jsonl = repo_root / project.get("paths", {}).get("catalog_jsonl", "data/catalog/asset_catalog.jsonl")
    catalog_db = repo_root / project.get("paths", {}).get("catalog_db", "data/catalog/asset_catalog.sqlite")
    warnings: list[str] = []

    if catalog_jsonl.exists():
        records: list[dict[str, Any]] = []
        try:
            lines = catalog_jsonl.read_text(encoding="utf-8-sig").splitlines()
        except OSError as exc:
            warnings.append(f"Could not read catalog JSONL: {exc}")
            lines = []

        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                warnings.append(f"Skipped malformed catalog row at line {line_number}.")
                continue
            if isinstance(record, dict):
                records.append(record)
        return records, warnings

    try:
        rows = query_rows(catalog_db=catalog_db, limit=100000)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not query catalog database: {exc}")
        return [], warnings
    return rows, warnings


def _catalog_index_by_path(repo_root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records, warnings = _load_catalog_records(repo_root)
    return {
        str(record.get("asset_path")): record
        for record in records
        if record.get("asset_path")
    }, warnings


def _required_field_gaps(record: dict[str, Any]) -> list[str]:
    tags = record.get("tags", {}) or {}
    missing = [key for key in sorted(REQUIRED_METADATA_KEYS) if not tags.get(key)]
    if not record.get("dimensions_cm"):
        missing.append("dimensions_cm")
    return missing


def _status_for_actor(actor: dict[str, Any], record: dict[str, Any] | None) -> tuple[str, str, str, list[str]]:
    asset_path = actor.get("asset_path")
    if not asset_path:
        return "undefined", UNDEFINED_COLOR, "Scene actor has no resolved asset path.", list(sorted(REQUIRED_METADATA_KEYS))
    if record is None:
        return "undefined", UNDEFINED_COLOR, "Asset path is not present in the local catalog.", list(sorted(REQUIRED_METADATA_KEYS))

    missing_fields = _required_field_gaps(record)
    is_quarantined = bool((record.get("quarantine") or {}).get("is_quarantined", False))
    status = str(record.get("status") or "unknown")
    metadata_complete = bool((record.get("quality_flags") or {}).get("metadata_complete", False))

    if not missing_fields and metadata_complete and not is_quarantined and status != "quarantined":
        return "identified", IDENTIFIED_COLOR, "Catalog record and metadata are resolved.", []

    reasons: list[str] = []
    if missing_fields:
        reasons.append(f"Missing fields: {', '.join(missing_fields)}")
    if is_quarantined or status == "quarantined":
        reasons.append("Asset is quarantined.")
    if not metadata_complete:
        reasons.append("Metadata completeness flag is false.")
    return "undefined", UNDEFINED_COLOR, " ".join(reasons) or "Asset is not fully understood.", missing_fields


def _topdown_layout(actors: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    positions = []
    for actor in actors:
        location = actor.get("location", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0]
        x = _safe_float(location[0]) if len(location) > 0 else 0.0
        y = _safe_float(location[1]) if len(location) > 1 else 0.0
        positions.append((x, y))

    if not positions:
        return [], {"min_x": -100.0, "max_x": 100.0, "min_y": -100.0, "max_y": 100.0}

    min_x = min(x for x, _ in positions)
    max_x = max(x for x, _ in positions)
    min_y = min(y for _, y in positions)
    max_y = max(y for _, y in positions)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)

    markers: list[dict[str, Any]] = []
    for actor in actors:
        location = actor.get("location", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0]
        bounds = actor.get("bounds_cm", {}) or {}
        box_extent = bounds.get("box_extent") or [40.0, 40.0, 40.0]
        x = _safe_float(location[0]) if len(location) > 0 else 0.0
        y = _safe_float(location[1]) if len(location) > 1 else 0.0
        width_cm = _safe_float(box_extent[0], 40.0) * 2.0 if len(box_extent) > 0 else 80.0
        depth_cm = _safe_float(box_extent[1], 40.0) * 2.0 if len(box_extent) > 1 else 80.0
        markers.append(
            {
                "label": actor.get("label") or actor.get("actor_name") or "UnknownActor",
                "normalized_x": round((x - min_x) / span_x, 4),
                "normalized_y": round((y - min_y) / span_y, 4),
                "normalized_width": round(min(max(width_cm / max(span_x, 100.0), 0.03), 0.3), 4),
                "normalized_depth": round(min(max(depth_cm / max(span_y, 100.0), 0.03), 0.3), 4),
            }
        )

    return markers, {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y}


def _tool_capabilities() -> list[dict[str, str]]:
    return [
        {
            "name": "Scene Identification Scan",
            "description": "Color the current scene by whether each actor is fully understood by the local asset catalog.",
        },
        {
            "name": "Undefined Actor Triage",
            "description": "Show why an actor is still red, including missing tags, missing dimensions, or quarantine state.",
        },
        {
            "name": "Top-Down X-Ray Map",
            "description": "Render an editor-style overhead map so you can spot unclassified actors and placement gaps quickly.",
        },
        {
            "name": "Per-Cycle Snapshots",
            "description": "Write current and per-cycle JSON and HTML artifacts into the active session for debugging and replay.",
        },
        {
            "name": "Tool List Visibility",
            "description": "Hide the capability list when you want a cleaner built-in review panel and show it again when needed.",
        },
    ]


def build_scene_xray_report(
    *,
    repo_root: Path,
    scene_state: dict[str, Any],
    viewer_settings: dict[str, Any] | None = None,
    session_id: str | None = None,
    cycle_number: int | None = None,
    zone_id: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    normalized_scene_state, scene_warnings = _coerce_scene_state(scene_state)
    catalog_index, catalog_warnings = _catalog_index_by_path(repo_root)
    report_warnings = list(warnings or [])
    report_warnings.extend(scene_warnings)
    report_warnings.extend(catalog_warnings)
    scene_actors = list(normalized_scene_state.get("actors") or [])
    xray_actors: list[dict[str, Any]] = []

    identified_count = 0
    undefined_count = 0

    for actor in scene_actors:
        actor_copy = dict(actor)
        record = catalog_index.get(str(actor_copy.get("asset_path") or ""))
        status, color, reason, missing_fields = _status_for_actor(actor_copy, record)
        if status == "identified":
            identified_count += 1
        else:
            undefined_count += 1

        tags = (record or {}).get("tags", {}) or {}
        xray_actors.append(
            {
                "label": actor_copy.get("label") or actor_copy.get("actor_name") or "UnknownActor",
                "actor_name": actor_copy.get("actor_name"),
                "asset_path": actor_copy.get("asset_path"),
                "class_name": actor_copy.get("class_name"),
                "location": _safe_triplet(actor_copy.get("location"), [0.0, 0.0, 0.0]),
                "rotation": _safe_triplet(actor_copy.get("rotation"), [0.0, 0.0, 0.0]),
                "scale": _safe_triplet(actor_copy.get("scale"), [1.0, 1.0, 1.0]),
                "bounds_cm": actor_copy.get("bounds_cm") if isinstance(actor_copy.get("bounds_cm"), dict) else {},
                "room_type": actor_copy.get("room_type") or normalized_scene_state.get("room_type") or "unknown",
                "status": status,
                "color": color,
                "reason": reason,
                "missing_fields": missing_fields,
                "identified": status == "identified",
                "catalog_asset_id": (record or {}).get("asset_id"),
                "category": tags.get("category"),
                "function_names": tags.get("function") or [],
                "mount_type": tags.get("mount_type"),
                "styles": tags.get("styles") or [],
                "trust_score": (record or {}).get("trust_score"),
                "trust_level": (record or {}).get("trust_level"),
                "quarantined": bool(((record or {}).get("quarantine") or {}).get("is_quarantined", False)),
                "metadata_complete": bool(((record or {}).get("quality_flags") or {}).get("metadata_complete", False)),
                "baseline_key": (record or {}).get("baseline_key"),
                "scan_state": "understood" if status == "identified" else "undefined",
            }
        )

    markers, extents = _topdown_layout(xray_actors)
    marker_by_label = {marker["label"]: marker for marker in markers}
    for actor in xray_actors:
        actor["topdown"] = marker_by_label.get(actor["label"], {})

    return {
        "report_type": "developer_scene_xray",
        "generated_at_utc": SessionStateStore.utcnow_static(),
        "session_id": session_id,
        "cycle_number": cycle_number,
        "zone_id": zone_id,
        "map_name": normalized_scene_state.get("map_name") or "UnknownMap",
        "room_type": normalized_scene_state.get("room_type") or "unknown",
        "viewer_settings": viewer_settings or {},
        "tool_capabilities": _tool_capabilities(),
        "warnings": report_warnings,
        "summary": {
            "total_actors": len(scene_actors),
            "identified_count": identified_count,
            "undefined_count": undefined_count,
            "identified_ratio": round((identified_count / max(len(scene_actors), 1)) * 100.0, 1) if scene_actors else 0.0,
            "warning_count": len(report_warnings),
        },
        "topdown_extents": extents,
        "actors": xray_actors,
    }


def build_scene_xray_error_report(
    *,
    repo_root: Path,
    error_message: str,
    viewer_settings: dict[str, Any] | None = None,
    session_id: str | None = None,
    cycle_number: int | None = None,
    zone_id: str | None = None,
) -> dict[str, Any]:
    return build_scene_xray_report(
        repo_root=repo_root,
        scene_state={"map_name": "Unavailable", "room_type": "unknown", "actors": []},
        viewer_settings=viewer_settings,
        session_id=session_id,
        cycle_number=cycle_number,
        zone_id=zone_id,
        warnings=[f"Developer x-ray entered failsafe mode: {error_message}"],
    )


def render_scene_xray_html(report: dict[str, Any]) -> str:
    report_json = json.dumps(report)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Developer Scene X-Ray</title>
  <style>
    :root {{
      --bg: #07111a;
      --bg-2: #0b1824;
      --panel: rgba(9, 20, 31, 0.8);
      --panel-strong: rgba(13, 27, 42, 0.94);
      --panel-soft: rgba(255,255,255,0.04);
      --text: #eef4ff;
      --muted: #9fb2ca;
      --muted-2: #6f8199;
      --green: {IDENTIFIED_COLOR};
      --red: {UNDEFINED_COLOR};
      --gray: {IGNORED_COLOR};
      --amber: #ffcc73;
      --line: rgba(255,255,255,0.08);
      --line-strong: rgba(255,255,255,0.13);
      --glow-green: rgba(51, 209, 122, 0.3);
      --glow-red: rgba(255, 90, 95, 0.26);
      --shadow: 0 24px 80px rgba(0,0,0,0.38);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Space Grotesk", "Aptos", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(51, 209, 122, 0.09), transparent 26%),
        radial-gradient(circle at 80% 0%, rgba(255, 90, 95, 0.1), transparent 24%),
        radial-gradient(circle at 50% 110%, rgba(94, 145, 255, 0.09), transparent 30%),
        linear-gradient(180deg, var(--bg), var(--bg-2));
      color: var(--text);
      min-height: 100vh;
    }}
    .shell {{
      max-width: 1460px;
      margin: 0 auto;
      padding: 26px;
      display: grid;
      gap: 20px;
    }}
    .hero, .panel {{
      position: relative;
      overflow: hidden;
      background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.015));
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 20px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .hero {{
      padding: 28px;
      min-height: 220px;
      background:
        radial-gradient(circle at 15% 20%, rgba(51, 209, 122, 0.14), transparent 26%),
        radial-gradient(circle at 78% 18%, rgba(255, 90, 95, 0.15), transparent 24%),
        linear-gradient(150deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
    }}
    .hero::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(transparent 95%, rgba(255,255,255,0.06) 96%, transparent 97%),
        linear-gradient(90deg, transparent 95%, rgba(255,255,255,0.06) 96%, transparent 97%);
      background-size: 100% 44px, 44px 100%;
      opacity: 0.15;
      pointer-events: none;
    }}
    .hero-top {{
      position: relative;
      z-index: 1;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 18px;
      flex-wrap: wrap;
      margin-bottom: 28px;
    }}
    .hero-kicker {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.09);
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .hero-grid {{
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: minmax(320px, 1.3fr) minmax(260px, 0.9fr);
      gap: 26px;
      align-items: end;
    }}
    .hero-copy h1 {{
      margin: 0 0 10px;
      font-size: clamp(2.1rem, 4vw, 3.8rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
      max-width: 11ch;
    }}
    .hero-copy p {{
      margin: 0;
      max-width: 58ch;
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.6;
    }}
    .hero-legend {{
      display: grid;
      gap: 12px;
      justify-items: end;
    }}
    .legend-card {{
      width: min(100%, 320px);
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(7, 16, 26, 0.6);
      border: 1px solid rgba(255,255,255,0.08);
    }}
    .legend-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .legend-row + .legend-row {{
      margin-top: 10px;
    }}
    .legend-swatch {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
      margin-right: 10px;
      box-shadow: 0 0 18px currentColor;
    }}
    .hero-meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .stat {{
      padding: 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.02));
      border: 1px solid var(--line);
      min-height: 118px;
      display: grid;
      align-content: space-between;
    }}
    .stat .value {{
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -0.04em;
    }}
    .stat .context {{
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}
    .controls button, .controls label {{
      background: rgba(255,255,255,0.04);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 10px 14px;
      cursor: pointer;
      transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
      user-select: none;
    }}
    .controls button:hover, .controls label:hover {{
      transform: translateY(-1px);
      border-color: var(--line-strong);
      background: rgba(255,255,255,0.065);
    }}
    .controls input[type="checkbox"] {{
      margin-right: 8px;
    }}
    .controls .primary {{
      background: linear-gradient(180deg, rgba(51,209,122,0.22), rgba(51,209,122,0.1));
      border-color: rgba(51,209,122,0.36);
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(320px, 0.95fr) minmax(460px, 1.4fr) minmax(280px, 0.85fr);
      gap: 18px;
      align-items: start;
    }}
    .map {{
      position: relative;
      min-height: 620px;
      overflow: hidden;
      background:
        radial-gradient(circle at center, rgba(94,145,255,0.12), transparent 42%),
        linear-gradient(transparent 49%, rgba(255,255,255,0.035) 50%, transparent 51%),
        linear-gradient(90deg, transparent 49%, rgba(255,255,255,0.035) 50%, transparent 51%),
        linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.01)),
        #0a131d;
      background-size: auto, 28px 28px, 28px 28px, auto, auto;
      border-radius: 22px;
      border: 1px solid var(--line);
      padding-top: 54px;
    }}
    .map::after {{
      content: "X-Ray Top View";
      position: absolute;
      top: 16px;
      left: 18px;
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 12px;
    }}
    .map::before {{
      content: "";
      position: absolute;
      inset: 50% auto auto 50%;
      width: 84px;
      height: 84px;
      transform: translate(-50%, -50%);
      border-radius: 999px;
      border: 1px dashed rgba(255,255,255,0.1);
      box-shadow: 0 0 0 26px rgba(255,255,255,0.02), 0 0 0 58px rgba(255,255,255,0.015);
      pointer-events: none;
    }}
    .actor-dot {{
      position: absolute;
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,0.16);
      transform: translate(-50%, -50%);
      padding: 8px 10px;
      min-width: 48px;
      min-height: 48px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: transform 140ms ease, box-shadow 140ms ease, filter 140ms ease, opacity 140ms ease;
      color: #081018;
      backdrop-filter: blur(8px);
    }}
    .actor-dot:hover {{
      transform: translate(-50%, -50%) scale(1.05);
      box-shadow: 0 0 0 1px rgba(255,255,255,0.18), 0 14px 28px rgba(0,0,0,0.34);
    }}
    body.xray-on .actor-dot.identified {{
      box-shadow: 0 0 0 1px rgba(255,255,255,0.12), 0 0 26px var(--glow-green);
    }}
    body.xray-on .actor-dot.undefined {{
      box-shadow: 0 0 0 1px rgba(255,255,255,0.12), 0 0 30px var(--glow-red);
    }}
    .cards {{
      display: grid;
      gap: 12px;
      max-height: 720px;
      overflow: auto;
      padding-right: 4px;
    }}
    .tool-panel {{
      display: grid;
      gap: 12px;
      align-content: start;
      max-height: 720px;
      overflow: auto;
      position: sticky;
      top: 18px;
    }}
    .panel-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .panel-header h2 {{
      margin: 0;
      font-size: 18px;
    }}
    .tool-list {{
      display: grid;
      gap: 10px;
    }}
    .tool-item {{
      padding: 14px;
      border-radius: 18px;
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(255,255,255,0.06);
      display: grid;
      gap: 6px;
    }}
    .tool-item strong {{
      font-size: 14px;
    }}
    .tool-actions {{
      display: grid;
      gap: 10px;
    }}
    .tool-actions a {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      background: rgba(255,255,255,0.04);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px;
    }}
    .card {{
      padding: 18px;
      border-radius: 20px;
      background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.02));
      border: 1px solid var(--line);
      display: grid;
      gap: 12px;
      transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
    }}
    .card:hover {{
      transform: translateY(-2px);
      border-color: var(--line-strong);
    }}
    .card.identified {{
      border-color: rgba(51, 209, 122, 0.34);
      background: linear-gradient(180deg, rgba(51,209,122,0.08), rgba(255,255,255,0.02));
    }}
    .card.undefined {{
      border-color: rgba(255, 90, 95, 0.36);
      background: linear-gradient(180deg, rgba(255,90,95,0.08), rgba(255,255,255,0.02));
    }}
    .row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 12px;
      letter-spacing: 0.02em;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
    }}
    .pill.ghost {{
      color: var(--muted);
    }}
    .muted {{ color: var(--muted); }}
    .muted-2 {{ color: var(--muted-2); }}
    .stack {{
      display: grid;
      gap: 8px;
    }}
    .card-title {{
      display: grid;
      gap: 4px;
    }}
    .card-title strong {{
      font-size: 1.02rem;
      letter-spacing: -0.02em;
    }}
    .card-path {{
      word-break: break-all;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.5;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
    }}
    .meta {{
      padding: 12px 13px;
      border-radius: 16px;
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .tiny {{
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }}
    .reason {{
      color: #d9e4f5;
      line-height: 1.6;
    }}
    .actor-flags {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .empty-state {{
      display: grid;
      place-items: center;
      min-height: 320px;
      color: var(--muted);
      text-align: center;
      padding: 24px;
    }}
    .hidden {{ display: none !important; }}
    body.tools-hidden #toolPanel {{
      display: none;
    }}
    .warning-list {{
      display: grid;
      gap: 10px;
    }}
    .warning-item {{
      padding: 14px;
      border-radius: 18px;
      border: 1px solid rgba(255, 181, 71, 0.25);
      background: rgba(255, 181, 71, 0.08);
      color: #ffd69a;
    }}
    .footer-note {{
      color: var(--muted-2);
      font-size: 0.85rem;
      line-height: 1.5;
    }}
    @media (max-width: 1080px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .hero-grid {{ grid-template-columns: 1fr; }}
      .hero-legend {{ justify-items: start; }}
      .map {{ min-height: 460px; }}
      .tool-panel {{ position: static; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-top">
        <div class="hero-kicker">Developer Scene X-Ray</div>
        <div class="hero-meta">
          <span class="pill ghost">Room <span id="roomType">-</span></span>
          <span class="pill ghost">Zone <span id="zoneId">-</span></span>
          <span class="pill ghost">Generated <span id="generatedAt">-</span></span>
        </div>
      </div>
      <div class="hero-grid">
        <div class="hero-copy">
          <h1>Understand what the scene actually knows.</h1>
          <p>Green actors are cataloged, trusted, and structurally understood. Red actors still need metadata, classification, or placement context before the loop should trust them.</p>
        </div>
        <div class="hero-legend">
          <div class="legend-card">
            <div class="legend-row"><span><span class="legend-swatch" style="color:{IDENTIFIED_COLOR};background:{IDENTIFIED_COLOR};"></span>Identified</span><strong id="identifiedRatio">0%</strong></div>
            <div class="legend-row"><span><span class="legend-swatch" style="color:{UNDEFINED_COLOR};background:{UNDEFINED_COLOR};"></span>Undefined</span><strong id="warningCount">0 notes</strong></div>
          </div>
        </div>
      </div>
    </section>

    <section class="stats">
      <div class="stat">
        <div class="tiny">Map</div>
        <div class="value" id="mapName">-</div>
        <div class="context">Live x-ray target</div>
      </div>
      <div class="stat">
        <div class="tiny">Actors</div>
        <div class="value" id="totalActors">0</div>
        <div class="context">Tracked scene instances</div>
      </div>
      <div class="stat">
        <div class="tiny">Identified</div>
        <div class="value" id="identifiedCount">0</div>
        <div class="context">Ready for trusted edits</div>
      </div>
      <div class="stat">
        <div class="tiny">Undefined</div>
        <div class="value" id="undefinedCount">0</div>
        <div class="context">Needs triage or metadata</div>
      </div>
    </section>

    <section class="panel">
      <div class="controls">
        <button class="primary" id="toggleXray" type="button">Toggle X-Ray Glow</button>
        <button id="toggleToolList" type="button">Hide Tool List</button>
        <button id="resetControls" type="button">Reset Controls</button>
        <label><input id="showIdentified" type="checkbox" checked />Show Identified</label>
        <label><input id="showUndefined" type="checkbox" checked />Show Undefined</label>
        <label><input id="showLabels" type="checkbox" checked />Show Labels</label>
      </div>
    </section>

    <section class="panel hidden" id="warningPanel">
      <div class="panel-header">
        <h2>Failsafe Notes</h2>
        <span class="pill">Non-blocking</span>
      </div>
      <div class="warning-list" id="warningList"></div>
    </section>

    <section class="layout">
      <div class="map panel" id="topdownMap"></div>
      <div class="cards" id="actorCards"></div>
      <aside class="panel tool-panel" id="toolPanel">
        <div class="panel-header">
          <h2>Developer Tool List</h2>
          <span class="pill">Experimental UI</span>
        </div>
        <div class="muted">This panel is meant to feel like an Unreal editor tool drawer. Hide it when you want a cleaner review surface.</div>
        <div class="tool-actions">
          <a href="#" id="openCurrentJson">Open Current JSON Path</a>
          <a href="#" id="openCurrentHtml">Open Current HTML Path</a>
        </div>
        <div class="tool-list" id="toolList"></div>
        <div class="footer-note">This view is a generated diagnostic surface. It should stay readable even when the session data is incomplete or partially broken.</div>
      </aside>
    </section>
  </div>

  <script>
    const report = {report_json};
    const mapEl = document.getElementById("topdownMap");
    const cardsEl = document.getElementById("actorCards");
    const showIdentifiedEl = document.getElementById("showIdentified");
    const showUndefinedEl = document.getElementById("showUndefined");
    const showLabelsEl = document.getElementById("showLabels");
    const toggleXrayEl = document.getElementById("toggleXray");
    const toggleToolListEl = document.getElementById("toggleToolList");
    const resetControlsEl = document.getElementById("resetControls");
    const toolListEl = document.getElementById("toolList");
    const openCurrentJsonEl = document.getElementById("openCurrentJson");
    const openCurrentHtmlEl = document.getElementById("openCurrentHtml");
    const warningPanelEl = document.getElementById("warningPanel");
    const warningListEl = document.getElementById("warningList");
    const storageKey = "uca.developerTools.sceneXray";
    const defaultPrefs = {{
      xrayOn: Boolean(report.viewer_settings?.default_xray_on ?? true),
      showIdentified: Boolean(report.viewer_settings?.default_show_identified ?? true),
      showUndefined: Boolean(report.viewer_settings?.default_show_undefined ?? true),
      showLabels: Boolean(report.viewer_settings?.default_show_labels ?? true),
      showToolList: Boolean(report.viewer_settings?.default_show_tool_list ?? true),
    }};

    document.getElementById("mapName").textContent = report.map_name || "UnknownMap";
    document.getElementById("totalActors").textContent = report.summary.total_actors;
    document.getElementById("identifiedCount").textContent = report.summary.identified_count;
    document.getElementById("undefinedCount").textContent = report.summary.undefined_count;
    document.getElementById("roomType").textContent = report.room_type || "unknown";
    document.getElementById("zoneId").textContent = report.zone_id || "n/a";
    document.getElementById("generatedAt").textContent = report.generated_at_utc || "n/a";
    document.getElementById("identifiedRatio").textContent = `${{report.summary.identified_ratio ?? 0}}%`;
    document.getElementById("warningCount").textContent = `${{report.summary.warning_count ?? 0}} note${{(report.summary.warning_count ?? 0) === 1 ? "" : "s"}}`;

    function renderWarnings() {{
      const warnings = Array.isArray(report.warnings) ? report.warnings.filter(Boolean) : [];
      warningListEl.innerHTML = "";
      warningPanelEl.classList.toggle("hidden", warnings.length === 0);
      warnings.forEach((warning) => {{
        const item = document.createElement("div");
        item.className = "warning-item";
        item.textContent = String(warning);
        warningListEl.appendChild(item);
      }});
    }}

    function loadPrefs() {{
      try {{
        const raw = window.localStorage.getItem(storageKey);
        if (!raw) return {{ ...defaultPrefs }};
        const saved = JSON.parse(raw);
        return {{ ...defaultPrefs, ...saved }};
      }} catch (_error) {{
        return {{ ...defaultPrefs }};
      }}
    }}

    let prefs = loadPrefs();

    function savePrefs() {{
      try {{
        window.localStorage.setItem(storageKey, JSON.stringify(prefs));
      }} catch (_error) {{
      }}
    }}

    function applyPrefs() {{
      document.body.classList.toggle("xray-on", Boolean(prefs.xrayOn));
      document.body.classList.toggle("labels-off", !prefs.showLabels);
      document.body.classList.toggle("tools-hidden", !prefs.showToolList);
      showIdentifiedEl.checked = Boolean(prefs.showIdentified);
      showUndefinedEl.checked = Boolean(prefs.showUndefined);
      showLabelsEl.checked = Boolean(prefs.showLabels);
      toggleToolListEl.textContent = prefs.showToolList ? "Hide Tool List" : "Show Tool List";
    }}

    function visibleFor(actor) {{
      if (actor.status === "identified" && !showIdentifiedEl.checked) return false;
      if (actor.status !== "identified" && !showUndefinedEl.checked) return false;
      return true;
    }}

    function renderToolList() {{
      toolListEl.innerHTML = "";
      (report.tool_capabilities || []).forEach((tool) => {{
        const item = document.createElement("section");
        item.className = "tool-item";
        item.innerHTML = `
          <strong>${{tool.name}}</strong>
          <div class="muted">${{tool.description}}</div>
        `;
        toolListEl.appendChild(item);
      }});
    }}

    function render() {{
      mapEl.querySelectorAll(".actor-dot").forEach((node) => node.remove());
      cardsEl.innerHTML = "";

      const visibleActors = report.actors.filter((actor) => visibleFor(actor));
      if (visibleActors.length === 0) {{
        cardsEl.innerHTML = `<div class="empty-state">No actors match the current filters.<br /><span class="muted-2">Adjust the visibility toggles to bring them back.</span></div>`;
      }}

      report.actors.forEach((actor, index) => {{
        const isVisible = visibleFor(actor);
        const topdown = actor.topdown || {{}};

        const marker = document.createElement("button");
        marker.type = "button";
        marker.className = `actor-dot ${{actor.status}}${{isVisible ? "" : " hidden"}}`;
        marker.style.left = `${{(topdown.normalized_x ?? 0.5) * 100}}%`;
        marker.style.top = `${{(topdown.normalized_y ?? 0.5) * 100}}%`;
        marker.style.width = `${{Math.max((topdown.normalized_width ?? 0.06) * 100, 6)}}%`;
        marker.style.height = `${{Math.max((topdown.normalized_depth ?? 0.06) * 100, 6)}}%`;
        marker.style.background = actor.color;
        marker.textContent = showLabelsEl.checked ? actor.label : "";
        marker.title = actor.label;
        marker.addEventListener("click", () => {{
          const card = document.getElementById(`card-${{index}}`);
          if (card) card.scrollIntoView({{ behavior: "smooth", block: "center" }});
        }});
        mapEl.appendChild(marker);

        const card = document.createElement("article");
        card.id = `card-${{index}}`;
        card.className = `card ${{actor.status}}${{isVisible ? "" : " hidden"}}`;
        card.innerHTML = `
          <div class="row">
            <div class="card-title">
              <strong>${{actor.label}}</strong>
              <div class="card-path">${{actor.asset_path || "No resolved asset path"}}</div>
            </div>
            <span class="pill" style="border-color:${{actor.color}}66;color:${{actor.color}}">${{actor.status.toUpperCase()}}</span>
          </div>
          <div class="reason">${{actor.reason}}</div>
          <div class="actor-flags">
            <span class="pill ghost">${{actor.category || "unknown category"}}</span>
            <span class="pill ghost">${{actor.mount_type || "unknown mount"}}</span>
            <span class="pill ghost">${{actor.trust_score ?? "?"}} / ${{actor.trust_level || "unknown"}}</span>
          </div>
          <div class="meta-grid">
            <div class="meta"><div class="tiny">Location</div><div>${{(actor.location || []).join(", ")}}</div></div>
            <div class="meta"><div class="tiny">Rotation</div><div>${{(actor.rotation || []).join(", ")}}</div></div>
            <div class="meta"><div class="tiny">Function</div><div>${{(actor.function_names || []).join(", ") || "Unknown"}}</div></div>
            <div class="meta"><div class="tiny">Room</div><div>${{actor.room_type || "Unknown"}}</div></div>
            <div class="meta"><div class="tiny">Baseline</div><div>${{actor.baseline_key || "None"}}</div></div>
            <div class="meta"><div class="tiny">Missing</div><div>${{(actor.missing_fields || []).join(", ") || "None"}}</div></div>
          </div>
        `;
        cardsEl.appendChild(card);
      }});
    }}

    toggleXrayEl.addEventListener("click", () => {{
      prefs.xrayOn = !prefs.xrayOn;
      applyPrefs();
      savePrefs();
    }});

    toggleToolListEl.addEventListener("click", () => {{
      prefs.showToolList = !prefs.showToolList;
      applyPrefs();
      savePrefs();
    }});

    resetControlsEl.addEventListener("click", () => {{
      prefs = {{ ...defaultPrefs }};
      applyPrefs();
      savePrefs();
      render();
      renderToolList();
    }});

    showIdentifiedEl.addEventListener("change", () => {{
      prefs.showIdentified = showIdentifiedEl.checked;
      savePrefs();
      render();
    }});
    showUndefinedEl.addEventListener("change", () => {{
      prefs.showUndefined = showUndefinedEl.checked;
      savePrefs();
      render();
    }});
    showLabelsEl.addEventListener("change", () => {{
      prefs.showLabels = showLabelsEl.checked;
      savePrefs();
      render();
    }});
    openCurrentJsonEl.addEventListener("click", (event) => {{
      event.preventDefault();
      window.alert("Current JSON artifact is stored beside the active session x-ray report.");
    }});
    openCurrentHtmlEl.addEventListener("click", (event) => {{
      event.preventDefault();
      window.alert("Current HTML artifact is this live x-ray view.");
    }});
    applyPrefs();
    renderWarnings();
    renderToolList();
    render();
  </script>
</body>
</html>"""


def write_scene_xray_artifacts(
    *,
    session_path: Path,
    cycle_number: int,
    report: dict[str, Any],
) -> dict[str, str]:
    output_dir = session_path / "developer_xray"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"cycle_{cycle_number:04d}.json"
    html_path = output_dir / f"cycle_{cycle_number:04d}.html"
    current_json = output_dir / "current.json"
    current_html = output_dir / "current.html"

    def _write_atomic(path: Path, payload: str) -> None:
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

    _write_atomic(json_path, json.dumps(report, indent=2))
    html = render_scene_xray_html(report)
    _write_atomic(html_path, html)
    _write_atomic(current_json, json.dumps(report, indent=2))
    _write_atomic(current_html, html)

    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "current_json": str(current_json),
        "current_html": str(current_html),
    }
