from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import typer

from apps.orchestrator.action_queue import Action
from apps.orchestrator.dirty_zone import DirtyZone
from apps.validation.report_builder import build_validation_report
from apps.validation.rules.clearance_rules import validate_clearance_rules
from apps.validation.rules.collision_expectations import validate_collision_expectations
from apps.validation.rules.orientation_fit import validate_orientation_fit
from apps.validation.rules.placement_interference import validate_placement_interference
from apps.validation.rules.registry_integrity import validate_registry_integrity
from apps.validation.rules.repetition_rules import validate_repetition_rules
from apps.validation.rules.room_fit import validate_room_fit
from apps.validation.rules.scale_sanity import validate_scale_sanity
from apps.validation.rules.shell_alignment import validate_shell_alignment
from apps.validation.rules.structure_functionality import validate_structure_functionality
from apps.validation.rules.support_ownership import validate_support_ownership
from apps.validation.rules.support_surface_fit import validate_support_surface_fit


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def _find_asset_record_from_sqlite(catalog_db: Path, asset_path: str | None) -> dict[str, Any] | None:
    if not asset_path or not catalog_db.exists():
        return None
    conn = sqlite3.connect(catalog_db)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT payload_json FROM asset_catalog WHERE asset_path = ?", (asset_path,))
        row = cur.fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
    finally:
        conn.close()


def _find_asset_record_from_scene_state(scene_state: dict[str, Any], asset_path: str | None) -> dict[str, Any] | None:
    if not asset_path:
        return None
    by_path = scene_state.get("asset_records_by_path", {}) or {}
    if asset_path in by_path:
        return by_path[asset_path]
    active = scene_state.get("active_asset_record")
    if active and active.get("asset_path") == asset_path:
        return active
    return None


def resolve_asset_record(*, repo_root: Path, scene_state: dict[str, Any], action: Action) -> dict[str, Any] | None:
    record = _find_asset_record_from_scene_state(scene_state, action.asset_path)
    if record is not None:
        return record
    try:
        project_cfg = _load_json(repo_root / "config" / "project.json")
    except Exception:
        project_cfg = {"paths": {}}
    paths_cfg = project_cfg.get("paths", {})
    catalog_db_rel = paths_cfg.get("catalog_db", "data/catalog/asset_catalog.sqlite")
    return _find_asset_record_from_sqlite(repo_root / catalog_db_rel, action.asset_path)


class LocalValidator:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        try:
            self.validator_rules = _load_json(repo_root / "config" / "validator_rules.json")
        except Exception:
            self.validator_rules = {}
        self.validator_rules.setdefault("validators", {})

    def validate(self, context: Any, scene_state: dict[str, Any], dirty_zone: DirtyZone, action: Action) -> dict[str, Any]:
        rules_cfg = self.validator_rules.get("validators", {})
        dirty_zone_dict = dirty_zone.to_dict()
        asset_record = resolve_asset_record(repo_root=self.repo_root, scene_state=scene_state, action=action)
        default_clearance_min = float(self.validator_rules.get("default", {}).get("clearance_min_cm", 45))
        if asset_record and not asset_record.get("placement_rules"):
            asset_record["placement_rules"] = {"min_front_clearance_cm": default_clearance_min}
        rule_results = [
            validate_scale_sanity(
                action=action.to_dict(),
                asset_record=asset_record,
                enabled=bool(rules_cfg.get("scale_sanity", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("scale_sanity", {}).get("fail_hard", True)),
            ),
            validate_clearance_rules(
                scene_state=scene_state,
                asset_record=asset_record,
                enabled=bool(rules_cfg.get("clearance_rules", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("clearance_rules", {}).get("fail_hard", True)),
            ),
            validate_shell_alignment(
                scene_state=scene_state,
                dirty_zone=dirty_zone_dict,
                enabled=bool(rules_cfg.get("shell_alignment", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("shell_alignment", {}).get("fail_hard", True)),
                check_inside_outside_consistency=bool(rules_cfg.get("shell_alignment", {}).get("check_inside_outside_consistency", True)),
            ),
            validate_repetition_rules(
                scene_state=scene_state,
                asset_record=asset_record,
                enabled=bool(rules_cfg.get("repetition_rules", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("repetition_rules", {}).get("fail_hard", False)),
                max_same_focal_asset_per_room=int(rules_cfg.get("repetition_rules", {}).get("max_same_focal_asset_per_room", 2)),
                max_same_support_asset_per_room=int(rules_cfg.get("repetition_rules", {}).get("max_same_support_asset_per_room", 4)),
            ),
            validate_collision_expectations(
                scene_state=scene_state,
                asset_record=asset_record,
                enabled=bool(rules_cfg.get("collision_expectations", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("collision_expectations", {}).get("fail_hard", True)),
            ),
            validate_support_surface_fit(
                scene_state=scene_state,
                action=action,
                enabled=bool(rules_cfg.get("support_surface_fit", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("support_surface_fit", {}).get("fail_hard", True)),
            ),
            validate_support_ownership(
                scene_state=scene_state,
                action=action,
                enabled=bool(rules_cfg.get("support_ownership", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("support_ownership", {}).get("fail_hard", True)),
            ),
            validate_orientation_fit(
                repo_root=self.repo_root,
                scene_state=scene_state,
                action=action,
                enabled=bool(rules_cfg.get("orientation_fit", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("orientation_fit", {}).get("fail_hard", True)),
                roll_pitch_tolerance_deg=float(rules_cfg.get("orientation_fit", {}).get("roll_pitch_tolerance_deg", 5.0)),
            ),
            validate_registry_integrity(
                scene_state=scene_state,
                action=action,
                enabled=bool(rules_cfg.get("registry_integrity", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("registry_integrity", {}).get("fail_hard", True)),
            ),
            validate_structure_functionality(
                scene_state=scene_state,
                action=action,
                enabled=bool(rules_cfg.get("structure_functionality", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("structure_functionality", {}).get("fail_hard", True)),
            ),
            validate_placement_interference(
                scene_state=scene_state,
                action=action,
                enabled=bool(rules_cfg.get("placement_interference", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("placement_interference", {}).get("fail_hard", True)),
            ),
            validate_room_fit(
                scene_state=scene_state,
                dirty_zone=dirty_zone_dict,
                asset_record=asset_record,
                enabled=bool(rules_cfg.get("room_fit", {}).get("enabled", True)),
                fail_hard=bool(rules_cfg.get("room_fit", {}).get("fail_hard", True)),
                require_room_type_match=bool(rules_cfg.get("room_fit", {}).get("require_room_type_match", True)),
                require_mount_type_match=bool(rules_cfg.get("room_fit", {}).get("require_mount_type_match", True)),
            ),
        ]
        return build_validation_report(zone_id=dirty_zone.zone_id, rule_results=rule_results)


app = typer.Typer(help="Run validators against scene state and an action payload.")


@app.command()
def main(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    scene_state_path: Path = typer.Option(..., help="Path to scene_state.json"),
    dirty_zone_path: Path = typer.Option(..., help="Path to dirty_zone.json"),
    action_path: Path = typer.Option(..., help="Path to action.json"),
) -> None:
    scene_state = _load_json(scene_state_path)
    dirty_zone_payload = _load_json(dirty_zone_path)
    action_payload = _load_json(action_path)
    dirty_zone = DirtyZone(
        zone_id=dirty_zone_payload["zone_id"],
        actor_ids=dirty_zone_payload.get("actor_ids", []),
        room_type=dirty_zone_payload.get("room_type", "unknown"),
        zone_type=dirty_zone_payload.get("zone_type", "generic"),
        shell_sensitive=bool(dirty_zone_payload.get("shell_sensitive", False)),
        capture_profile=dirty_zone_payload.get("capture_profile", "default_room"),
        bounds=dirty_zone_payload.get("bounds", {}),
    )
    action = Action.from_dict(action_payload)
    validator = LocalValidator(repo_root=repo_root)
    report = validator.validate(context=None, scene_state=scene_state, dirty_zone=dirty_zone, action=action)
    typer.echo(json.dumps(report, indent=2))


def run_validators() -> dict[str, Any]:
    return {"passed": True, "issues": []}


if __name__ == "__main__":
    app()
