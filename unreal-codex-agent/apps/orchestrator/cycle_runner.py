from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from apps.orchestrator.action_queue import Action, ActionQueue
from apps.orchestrator.completion_gate import CompletionGate
from apps.developer_overlay.scene_xray import (
    build_scene_xray_error_report,
    build_scene_xray_report,
    write_scene_xray_artifacts,
)
from apps.developer_overlay.settings import scene_xray_auto_generate, scene_xray_settings
from apps.placement.managed_registry import get_slot_record, registry_layout_snapshot
from apps.placement.support_fit import derive_support_surface_fit
from apps.orchestrator.dirty_zone import DirtyZone, DirtyZoneDetector
from apps.orchestrator.scoring import ScoreCalculator
from apps.orchestrator.state_store import SessionStateStore
from apps.orchestrator.undo_manager import UndoManager
from apps.uefn.verse_export import export_cycle_artifacts
from apps.validation.report_builder import build_rule_result, build_validation_report


@dataclass
class CycleContext:
    repo_root: Path
    session_id: str
    session_path: Path
    build_goal: str
    project_config: dict[str, Any]
    validator_rules: dict[str, Any]


class SceneStateProvider(Protocol):
    def get_scene_state(self, context: CycleContext) -> dict[str, Any]:
        ...


class CaptureService(Protocol):
    def build_capture_packet(self, context: CycleContext, dirty_zone: DirtyZone) -> dict[str, Any]:
        ...


class CodexBridge(Protocol):
    def choose_action(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def review_edit(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
        action: Action,
        validation_report: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class Validator(Protocol):
    def validate(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        action: Action,
    ) -> dict[str, Any]:
        ...


class ActionExecutor(Protocol):
    def execute_action(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        action: Action,
    ) -> dict[str, Any]:
        ...


class NullSceneStateProvider:
    def get_scene_state(self, context: CycleContext) -> dict[str, Any]:
        return {
            "map_name": "UnknownMap",
            "actors": [],
            "dirty_actor_ids": [],
            "timestamp_utc": SessionStateStore.utcnow_static(),
        }


class NullCaptureService:
    def build_capture_packet(self, context: CycleContext, dirty_zone: DirtyZone) -> dict[str, Any]:
        return {
            "packet_id": f"{dirty_zone.zone_id}_packet",
            "zone_id": dirty_zone.zone_id,
            "profile": dirty_zone.capture_profile,
            "images": [],
            "shell_crosscheck": dirty_zone.shell_sensitive,
            "timestamp_utc": SessionStateStore.utcnow_static(),
        }


class NullCodexBridge:
    def choose_action(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "action": "no_op",
            "target_zone": dirty_zone.zone_id,
            "reason": "No external Codex bridge configured yet.",
            "confidence": 1.0,
        }

    def review_edit(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
        action: Action,
        validation_report: dict[str, Any],
    ) -> dict[str, Any]:
        if validation_report.get("blocking_failures"):
            return {
                "decision": "undo",
                "reason": "Blocking validator failure detected.",
                "confidence": 0.95,
                "issues": validation_report.get("blocking_failures", []),
            }

        return {
            "decision": "keep",
            "reason": "No-op action and no blocking validator failures.",
            "confidence": 0.75,
            "issues": validation_report.get("warnings", []),
        }


class NullValidator:
    def validate(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        action: Action,
    ) -> dict[str, Any]:
        return {
            "zone_id": dirty_zone.zone_id,
            "passed": True,
            "blocking_failures": [],
            "warnings": [],
            "timestamp_utc": SessionStateStore.utcnow_static(),
        }


class NullActionExecutor:
    def execute_action(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        action: Action,
    ) -> dict[str, Any]:
        del context, scene_state, dirty_zone
        return {
            "status": "skipped",
            "backend": "plan_only",
            "applied": False,
            "reason": "No live action executor is configured.",
            "action": action.action,
        }


class CycleRunner:
    def __init__(
        self,
        state_store: SessionStateStore,
        scene_state_provider: SceneStateProvider,
        capture_service: CaptureService,
        codex_bridge: CodexBridge,
        validator: Validator,
        action_executor: ActionExecutor,
    ) -> None:
        self.state_store = state_store
        self.scene_state_provider = scene_state_provider
        self.capture_service = capture_service
        self.codex_bridge = codex_bridge
        self.validator = validator
        self.action_executor = action_executor
        self.action_queue = ActionQueue()
        self.undo_manager = UndoManager()
        self.score_calculator = ScoreCalculator()
        self.completion_gate = CompletionGate()

    @staticmethod
    def _with_note(payload: dict[str, Any], message: str) -> dict[str, Any]:
        updated = dict(payload or {})
        notes = list(updated.get("notes") or [])
        notes.append(message)
        updated["notes"] = notes
        return updated

    def _capture_with_fallback(
        self,
        *,
        context: CycleContext,
        dirty_zone: DirtyZone,
        fallback_packet: dict[str, Any] | None,
        warning_prefix: str,
    ) -> dict[str, Any]:
        try:
            return self.capture_service.build_capture_packet(context, dirty_zone)
        except Exception as exc:  # noqa: BLE001
            if fallback_packet is not None:
                return self._with_note(fallback_packet, f"{warning_prefix}: {exc}")
            return {
                "packet_id": f"{dirty_zone.zone_id}_packet",
                "zone_id": dirty_zone.zone_id,
                "profile": dirty_zone.capture_profile,
                "images": [],
                "shell_crosscheck": dirty_zone.shell_sensitive,
                "timestamp_utc": SessionStateStore.utcnow_static(),
                "notes": [f"{warning_prefix}: {exc}"],
            }

    def _build_xray_report(
        self,
        *,
        context: CycleContext,
        cycle_number: int,
        scene_state: dict[str, Any],
        zone_id: str,
    ) -> dict[str, Any] | None:
        if not scene_xray_auto_generate(context.project_config):
            return None
        try:
            report = build_scene_xray_report(
                repo_root=context.repo_root,
                scene_state=scene_state,
                viewer_settings=scene_xray_settings(context.project_config),
                session_id=context.session_id,
                cycle_number=cycle_number,
                zone_id=zone_id,
            )
        except Exception as exc:  # noqa: BLE001
            report = build_scene_xray_error_report(
                repo_root=context.repo_root,
                error_message=str(exc),
                viewer_settings=scene_xray_settings(context.project_config),
                session_id=context.session_id,
                cycle_number=cycle_number,
                zone_id=zone_id,
            )

        try:
            write_scene_xray_artifacts(
                session_path=context.session_path,
                cycle_number=cycle_number,
                report=report,
            )
        except Exception as exc:  # noqa: BLE001
            report = build_scene_xray_error_report(
                repo_root=context.repo_root,
                error_message=f"Could not write x-ray artifacts: {exc}",
                viewer_settings=scene_xray_settings(context.project_config),
                session_id=context.session_id,
                cycle_number=cycle_number,
                zone_id=zone_id,
            )
        return report

    def _merge_execution_result(
        self,
        *,
        validation_report: dict[str, Any],
        execution_result: dict[str, Any],
        dirty_zone: DirtyZone,
        action: Action,
    ) -> dict[str, Any]:
        rule_results = list(validation_report.get("rule_results") or [])
        execution_status = str(execution_result.get("status") or "").lower()
        execution_reason = str(
            execution_result.get("reason")
            or execution_result.get("error")
            or ""
        ).strip()
        execution_warnings = [
            str(value).strip()
            for value in list(execution_result.get("warnings") or [])
            if str(value).strip()
        ]

        if execution_status == "error":
            rule_results.append(
                build_rule_result(
                    name="live_action_execution",
                    passed=False,
                    blocking=True,
                    issues=[f"Live action execution failed: {execution_reason or 'unknown error'}"],
                    warnings=execution_warnings,
                    details={"execution_result": execution_result},
                )
            )
        elif execution_status == "skipped" and action.action not in {"", "no_op"}:
            rule_results.append(
                build_rule_result(
                    name="live_action_execution",
                    passed=False,
                    blocking=False,
                    issues=[f"Live action was not applied: {execution_reason or 'execution skipped'}"],
                    warnings=execution_warnings,
                    details={"execution_result": execution_result},
                )
            )
        else:
            rule_results.append(
                build_rule_result(
                    name="live_action_execution",
                    passed=True,
                    blocking=False,
                    warnings=execution_warnings,
                    details={"execution_result": execution_result},
                )
            )

        return build_validation_report(zone_id=dirty_zone.zone_id, rule_results=rule_results)

    @staticmethod
    def _value_present(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) > 0
        return True

    @staticmethod
    def _derive_support_fit(scene_state: dict[str, Any], active_actor: dict[str, Any]) -> dict[str, Any]:
        return derive_support_surface_fit(scene_state=scene_state, active_actor=active_actor)

    @staticmethod
    def _attach_active_asset_record(
        scene_state: dict[str, Any],
        action: Action,
        execution_result: dict[str, Any],
    ) -> dict[str, Any]:
        asset_record = action.raw.get("asset_record") if isinstance(action.raw, dict) else None
        enriched = dict(scene_state)
        actors = [actor for actor in list(enriched.get("actors") or []) if isinstance(actor, dict)]
        actor_payload = dict(execution_result.get("actor") or {}) if isinstance(execution_result, dict) else {}
        actor_path = str(actor_payload.get("actor_path") or "").strip()
        actor_label = str(actor_payload.get("label") or action.raw.get("spawn_label") or "").strip() if isinstance(action.raw, dict) else str(actor_payload.get("label") or "").strip()

        active_actor = None
        for actor in actors:
            if actor_path and str(actor.get("actor_path") or "") == actor_path:
                active_actor = actor
                break
        if active_actor is None and actor_label:
            for actor in actors:
                if str(actor.get("label") or "") == actor_label:
                    active_actor = actor
                    break
        if active_actor is None and action.asset_path:
            selected_matches = [
                actor
                for actor in actors
                if bool(actor.get("selected", False)) and str(actor.get("asset_path") or "") == str(action.asset_path or "")
            ]
            if selected_matches:
                active_actor = selected_matches[0]

        if actor_payload:
            if active_actor is None:
                active_actor = dict(actor_payload)
            else:
                merged_actor = dict(active_actor)
                for key, value in actor_payload.items():
                    if not CycleRunner._value_present(merged_actor.get(key)) and CycleRunner._value_present(value):
                        merged_actor[key] = value
                active_actor = merged_actor

        if active_actor is not None:
            fit_details = CycleRunner._derive_support_fit(enriched, active_actor)
            if fit_details:
                active_actor = {**active_actor, **fit_details}
            enriched["active_actor"] = dict(active_actor)

        if not isinstance(asset_record, dict) or not asset_record:
            return enriched
        by_path = dict(enriched.get("asset_records_by_path") or {})
        asset_path = str(action.asset_path or asset_record.get("asset_path") or "").strip()
        updated_record = dict(asset_record)
        if active_actor is not None:
            quality_flags = dict(updated_record.get("quality_flags") or {})
            collision_enabled = active_actor.get("collision_enabled")
            if isinstance(collision_enabled, bool):
                quality_flags["collision_verified"] = collision_enabled
            if quality_flags:
                updated_record["quality_flags"] = quality_flags
            material_paths = list(active_actor.get("material_paths") or [])
            if material_paths:
                updated_record["material_paths"] = material_paths
                updated_record["material_count"] = int(active_actor.get("material_count") or len(material_paths))
            bounds = dict(active_actor.get("bounds_cm") or {})
            if bounds:
                extent = list(bounds.get("box_extent") or [0.0, 0.0, 0.0])
                if len(extent) >= 3:
                    updated_record["dimensions_cm"] = {
                        "width": round(float(extent[0]) * 2.0, 3),
                        "depth": round(float(extent[1]) * 2.0, 3),
                        "height": round(float(extent[2]) * 2.0, 3),
                    }
            updated_record["scene_actor"] = {
                "label": active_actor.get("label"),
                "actor_path": active_actor.get("actor_path"),
                "class_name": active_actor.get("class_name"),
                "managed_slot": execution_result.get("managed_slot"),
                "registry_status": execution_result.get("registry_status"),
                "reconciliation_status": execution_result.get("reconciliation_status"),
                "drift_status": execution_result.get("drift_status"),
                "collision_enabled": active_actor.get("collision_enabled"),
                "query_collision_enabled": active_actor.get("query_collision_enabled"),
                "physics_collision_enabled": active_actor.get("physics_collision_enabled"),
                "collision_mode": active_actor.get("collision_mode"),
                "collision_profile_name": active_actor.get("collision_profile_name"),
                "material_count": active_actor.get("material_count"),
                "support_surface_delta_cm": active_actor.get("support_surface_delta_cm"),
                "support_surface_fit_ok": active_actor.get("support_surface_fit_ok"),
                "support_surface_fit_state": active_actor.get("support_surface_fit_state"),
                "support_surface_kind": active_actor.get("support_surface_kind"),
                "support_anchor_type": active_actor.get("support_anchor_type"),
                "support_surface_adjustment_cm": active_actor.get("support_surface_adjustment_cm"),
                "orientation_candidate": active_actor.get("orientation_candidate"),
                "orientation_height_cm": active_actor.get("orientation_height_cm"),
            }
        if asset_path:
            by_path[asset_path] = updated_record
        enriched["asset_records_by_path"] = by_path
        enriched["active_asset_record"] = updated_record
        return enriched

    def run_once(self, context: CycleContext, cycle_number: int) -> dict[str, Any]:
        planning_scene_state = self.scene_state_provider.get_scene_state(context)
        planning_dirty_zone = DirtyZoneDetector().detect(scene_state=planning_scene_state, cycle_number=cycle_number)
        planning_capture_packet = self._capture_with_fallback(
            context=context,
            dirty_zone=planning_dirty_zone,
            fallback_packet=None,
            warning_prefix="Could not build planning capture packet",
        )

        raw_action = self.codex_bridge.choose_action(
            context=context,
            scene_state=planning_scene_state,
            dirty_zone=planning_dirty_zone,
            capture_packet=planning_capture_packet,
        )
        action = Action.from_dict(raw_action)
        self.action_queue.enqueue(action)

        undo_group_id = self.undo_manager.begin_group(
            zone_id=planning_dirty_zone.zone_id,
            cycle_number=cycle_number,
        )
        self.undo_manager.record_action(undo_group_id, action.to_dict())

        execution_result = self.action_executor.execute_action(
            context=context,
            scene_state=planning_scene_state,
            dirty_zone=planning_dirty_zone,
            action=action,
        )

        final_scene_state = planning_scene_state
        final_dirty_zone = planning_dirty_zone
        execution_warnings = [
            str(value).strip()
            for value in list(execution_result.get("warnings") or [])
            if str(value).strip()
        ]

        if bool(execution_result.get("applied", False)):
            try:
                final_scene_state = self.scene_state_provider.get_scene_state(context)
            except Exception as exc:  # noqa: BLE001
                execution_warnings.append(f"Post-action scene refresh failed, used pre-action state: {exc}")
                final_scene_state = planning_scene_state
            try:
                final_dirty_zone = DirtyZoneDetector().detect(scene_state=final_scene_state, cycle_number=cycle_number)
            except Exception as exc:  # noqa: BLE001
                execution_warnings.append(f"Post-action dirty-zone detection failed, used planning zone: {exc}")
                final_dirty_zone = planning_dirty_zone

        if execution_warnings:
            execution_result = dict(execution_result)
            execution_result["warnings"] = execution_warnings

        final_scene_state = self._attach_active_asset_record(final_scene_state, action, execution_result)
        if context.session_path.exists():
            final_scene_state["managed_registry"] = registry_layout_snapshot(context.session_path)
            managed_record = get_slot_record(
                context.session_path,
                action.target_zone,
                str(execution_result.get("managed_slot") or action.managed_slot or "primary"),
            )
            if managed_record:
                final_scene_state["active_managed_record"] = managed_record

        self.state_store.save_scene_state(context.session_path, cycle_number, final_scene_state)

        xray_report = self._build_xray_report(
            context=context,
            cycle_number=cycle_number,
            scene_state=final_scene_state,
            zone_id=final_dirty_zone.zone_id,
        )

        capture_packet = self._capture_with_fallback(
            context=context,
            dirty_zone=final_dirty_zone,
            fallback_packet=planning_capture_packet,
            warning_prefix="Could not build post-action capture packet",
        )
        self.state_store.save_capture_packet(context.session_path, cycle_number, capture_packet)

        validation_report = self.validator.validate(
            context=context,
            scene_state=final_scene_state,
            dirty_zone=final_dirty_zone,
            action=action,
        )
        validation_report = self._merge_execution_result(
            validation_report=validation_report,
            execution_result=execution_result,
            dirty_zone=final_dirty_zone,
            action=action,
        )

        try:
            uefn_artifacts = export_cycle_artifacts(
                repo_root=context.repo_root,
                session_path=context.session_path,
                cycle_number=cycle_number,
                scene_state=final_scene_state,
                dirty_zone=final_dirty_zone.to_dict(),
                action_payload=action.to_dict(),
                placement_summary=dict(final_scene_state.get("placement_context") or {}),
            )
        except Exception as exc:  # noqa: BLE001
            uefn_artifacts = {
                "status": "warning",
                "reason": f"Could not export UEFN artifacts: {exc}",
            }
        self.state_store.append_jsonl(
            context.session_path / "validation_history.jsonl",
            validation_report,
        )

        review = self.codex_bridge.review_edit(
            context=context,
            scene_state=final_scene_state,
            dirty_zone=final_dirty_zone,
            capture_packet=capture_packet,
            action=action,
            validation_report=validation_report,
        )

        score = self.score_calculator.calculate(
            validation_report=validation_report,
            review=review,
            action=action,
            dirty_zone=final_dirty_zone,
        )
        self.state_store.append_score(context.session_path, score)

        completion = self.completion_gate.evaluate(
            validator_rules=context.validator_rules,
            validation_report=validation_report,
            review=review,
            score=score,
            dirty_zone=final_dirty_zone,
        )
        self.state_store.write_completion_state(context.session_path, completion)

        action_record = {
            "cycle_number": cycle_number,
            "zone_id": final_dirty_zone.zone_id,
            "action": action.to_dict(),
            "execution_result": execution_result,
            "review": review,
            "validation_report": validation_report,
            "score": score,
            "completion": completion,
            "uefn_artifacts": uefn_artifacts,
        }
        self.state_store.append_action(context.session_path, action_record)

        self.undo_manager.commit_group(undo_group_id)
        self.state_store.update_session_last_cycle(context.session_path, cycle_number)

        return {
            "cycle_number": cycle_number,
            "dirty_zone": final_dirty_zone.to_dict(),
            "action": action.to_dict(),
            "execution_result": execution_result,
            "developer_xray": xray_report,
            "uefn_artifacts": uefn_artifacts,
            "validation_report": validation_report,
            "review_decision": review["decision"],
            "score": score,
            "completion": completion,
        }
