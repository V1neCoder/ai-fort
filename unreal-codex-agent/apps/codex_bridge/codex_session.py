from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from apps.codex_bridge.decision_schema import ActionDecision, CompletionDecision, ReviewDecision
from apps.integrations.prefabricator import is_prefab_asset
from apps.codex_bridge.prompt_builder import PromptBuilder
from apps.codex_bridge.response_parser import ResponseParseError, parse_action_response, parse_completion_response, parse_review_response
from apps.codex_bridge.retry_policy import RetryConfig, RetryPolicy
from apps.orchestrator.action_queue import Action
from apps.orchestrator.dirty_zone import DirtyZone


class CodexSession:
    """
    Starter bridge for Codex integration.

    Current behavior:
    - mock mode by default
    - optional external command mode if CODEX_BRIDGE_COMMAND is set
    """

    def __init__(self, repo_root: Path, mode: str | None = None) -> None:
        self.repo_root = repo_root
        self.prompt_builder = PromptBuilder(repo_root=repo_root)
        self.command = os.getenv("CODEX_BRIDGE_COMMAND", "").strip()
        resolved_mode = (mode or os.getenv("CODEX_BRIDGE_MODE", "")).strip().lower()
        if not resolved_mode:
            # Prefer external mode automatically when a bridge command is configured.
            resolved_mode = "external" if self.command else "mock"
        self.mode = resolved_mode
        self.retry_policy = RetryPolicy(
            RetryConfig(
                max_attempts=int(os.getenv("CODEX_MAX_RETRIES", "3")),
                base_delay_seconds=0.25,
                backoff_multiplier=2.0,
            )
        )

    def choose_action(
        self,
        *,
        build_goal: str,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
        shortlist: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload = self.prompt_builder.build_action_payload(
            build_goal=build_goal,
            scene_state=scene_state,
            dirty_zone=dirty_zone.to_dict(),
            capture_packet=capture_packet,
            shortlist=shortlist or [],
        )
        if self.mode == "mock":
            return self._mock_action_decision(
                dirty_zone=dirty_zone,
                shortlist=shortlist or [],
                scene_state=scene_state,
            )
        try:
            raw_response = self.retry_policy.run(lambda: self._invoke_external(payload, task="action"))
            return parse_action_response(raw_response).to_orchestrator_dict()
        except Exception as exc:  # noqa: BLE001
            fallback = self._mock_action_decision(
                dirty_zone=dirty_zone,
                shortlist=shortlist or [],
                scene_state=scene_state,
            )
            fallback["reason"] = f"{fallback.get('reason', '')} Fallback used because external bridge failed: {exc}".strip()
            fallback["bridge_fallback"] = True
            return fallback

    def review_edit(
        self,
        *,
        build_goal: str,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
        action: Action,
        validation_report: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.prompt_builder.build_review_payload(
            build_goal=build_goal,
            scene_state=scene_state,
            dirty_zone=dirty_zone.to_dict(),
            capture_packet=capture_packet,
            validation_report=validation_report,
            previous_action=action.to_dict(),
        )
        if self.mode == "mock":
            return self._mock_review_decision(
                dirty_zone=dirty_zone,
                validation_report=validation_report,
                action=action,
            ).to_dict()
        try:
            raw_response = self.retry_policy.run(lambda: self._invoke_external(payload, task="review"))
            return parse_review_response(raw_response).to_dict()
        except Exception as exc:  # noqa: BLE001
            fallback = self._mock_review_decision(
                dirty_zone=dirty_zone,
                validation_report=validation_report,
                action=action,
            ).to_dict()
            fallback["reason"] = f"{fallback.get('reason', '')} Fallback used because external bridge failed: {exc}".strip()
            fallback["bridge_fallback"] = True
            return fallback

    def completion_check(
        self,
        *,
        build_goal: str,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
        validation_report: dict[str, Any],
        unresolved_issues: list[str],
    ) -> dict[str, Any]:
        payload = self.prompt_builder.build_completion_payload(
            build_goal=build_goal,
            scene_state=scene_state,
            dirty_zone=dirty_zone.to_dict(),
            capture_packet=capture_packet,
            validation_report=validation_report,
            unresolved_issues=unresolved_issues,
        )
        if self.mode == "mock":
            return self._mock_completion_decision(
                dirty_zone=dirty_zone,
                validation_report=validation_report,
                unresolved_issues=unresolved_issues,
            ).to_dict()
        try:
            raw_response = self.retry_policy.run(lambda: self._invoke_external(payload, task="completion"))
            return parse_completion_response(raw_response).to_dict()
        except Exception as exc:  # noqa: BLE001
            fallback = self._mock_completion_decision(
                dirty_zone=dirty_zone,
                validation_report=validation_report,
                unresolved_issues=unresolved_issues,
            ).to_dict()
            fallback["reason"] = f"{fallback.get('reason', '')} Fallback used because external bridge failed: {exc}".strip()
            fallback["bridge_fallback"] = True
            return fallback

    def _invoke_external(self, payload: dict[str, Any], task: str) -> str:
        if not self.command:
            raise RuntimeError(
                "CODEX_BRIDGE_COMMAND is not configured. Set CODEX_BRIDGE_MODE=mock or provide a real bridge command."
            )
        completed = subprocess.run(
            self.command,
            input=json.dumps({"task": task, "payload": payload}),
            text=True,
            shell=True,
            capture_output=True,
            cwd=str(self.repo_root),
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"External Codex bridge command failed with exit code {completed.returncode}: {completed.stderr.strip()}"
            )
        response_text = completed.stdout.strip()
        if not response_text:
            raise ResponseParseError("External Codex bridge returned empty output.")
        return response_text

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_triplet(value: Any, default: list[float]) -> list[float]:
        if isinstance(value, dict):
            return [
                CodexSession._safe_float(value.get("x"), default[0]),
                CodexSession._safe_float(value.get("y"), default[1]),
                CodexSession._safe_float(value.get("z"), default[2]),
            ]
        if isinstance(value, (list, tuple)):
            padded = list(value[:3]) + default[len(value[:3]) :]
            return [
                CodexSession._safe_float(padded[0], default[0]),
                CodexSession._safe_float(padded[1], default[1]),
                CodexSession._safe_float(padded[2], default[2]),
            ]
        return list(default)

    @staticmethod
    def _slugify_label(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", value or "")
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned or "PlacedAsset"

    def _mock_transform(self, scene_state: dict[str, Any], best: dict[str, Any] | None) -> dict[str, Any]:
        placement_targets = dict(scene_state.get("placement_targets") or {})
        placement_context = dict(scene_state.get("placement_context") or {})
        bounds = dict(scene_state.get("dirty_bounds") or {})
        mount_type = str((best or {}).get("tags", {}).get("mount_type") or "").strip().lower()

        if mount_type in {"wall", "opening"} and placement_targets.get("plane_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("plane_anchor"), [0.0, 0.0, 0.0])
        elif mount_type == "corner" and placement_targets.get("corner_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("corner_anchor"), [0.0, 0.0, 0.0])
        elif mount_type in {"ceiling", "roof"} and placement_targets.get("surface_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("surface_anchor"), [0.0, 0.0, 0.0])
        elif mount_type in {"floor", "surface"} and placement_targets.get("surface_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("surface_anchor"), [0.0, 0.0, 0.0])
        elif mount_type in {"floor", "surface", "exterior_ground"} and placement_targets.get("ground_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("ground_anchor"), [0.0, 0.0, 0.0])
        elif mount_type in {"floor", "surface", "exterior_ground"} and placement_targets.get("landscape_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("landscape_anchor"), [0.0, 0.0, 0.0])
        elif placement_targets.get("surface_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("surface_anchor"), [0.0, 0.0, 0.0])
        elif placement_targets.get("plane_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("plane_anchor"), [0.0, 0.0, 0.0])
        elif placement_targets.get("corner_anchor") is not None:
            location = self._safe_triplet(placement_targets.get("corner_anchor"), [0.0, 0.0, 0.0])
        elif placement_targets.get("anchor_point") is not None:
            location = self._safe_triplet(placement_targets.get("anchor_point"), [0.0, 0.0, 0.0])
        else:
            location = self._safe_triplet(bounds.get("origin"), [0.0, 0.0, 0.0])

        rotation = [
            0.0,
            self._safe_float(placement_targets.get("reference_pitch_deg"), self._safe_float(placement_context.get("reference_pitch_deg"), 0.0)),
            self._safe_float(placement_targets.get("reference_yaw_deg"), self._safe_float(placement_context.get("reference_yaw_deg"), 0.0)),
        ]

        preferred_scale = 1.0
        if isinstance(best, dict):
            limits = dict(best.get("scale_limits") or {})
            preferred_scale = self._safe_float(limits.get("preferred"), 1.0)

        return {
            "location": [round(value, 3) for value in location],
            "rotation": [round(value, 3) for value in rotation],
            "scale": [round(preferred_scale, 3)] * 3,
        }

    def _mock_action_decision(
        self,
        *,
        dirty_zone: DirtyZone,
        shortlist: list[dict[str, Any]],
        scene_state: dict[str, Any],
    ) -> dict[str, Any]:
        if shortlist:
            best = shortlist[0]
            transform = self._mock_transform(scene_state, best)
            placement_quality = str(scene_state.get("placement_reference_quality") or "fallback_bounds")
            placement_targets = dict(scene_state.get("placement_targets") or {})
            placement_context = dict(scene_state.get("placement_context") or {})
            asset_name = str(best.get("asset_name") or best.get("asset_id") or "PlacedAsset")
            mount_type = str((best.get("tags") or {}).get("mount_type") or "").strip().lower()
            if mount_type in {"floor", "surface", "exterior_ground"}:
                label_suffix = dirty_zone.zone_id
            else:
                label_suffix = placement_targets.get("reference_actor_label") or dirty_zone.zone_id
            action_payload = ActionDecision(
                action="place_asset",
                target_zone=dirty_zone.zone_id,
                reason="Selected the top-ranked shortlisted asset using structural placement hints." if placement_quality != "fallback_bounds" else "Selected the top-ranked shortlisted asset in mock mode.",
                confidence=0.84 if placement_quality != "fallback_bounds" else 0.76,
                asset_path=best.get("asset_path"),
                managed_slot="primary",
                identity_policy="reuse_or_create",
                transform=transform,
                placement_hint={
                    "placement_phase": "initial_place",
                    "snap_policy": "initial_only",
                    "support_reference_policy": "selected_first",
                    "support_surface_kind": placement_targets.get("support_surface_kind") or placement_context.get("support_surface_kind"),
                },
                expected_outcome="Place the selected asset at the derived structural anchor with snapped orientation.",
                alternatives=[row.get("asset_path") for row in shortlist[1:3] if row.get("asset_path")],
            ).to_orchestrator_dict()
            action_payload["spawn_label"] = f"{self._slugify_label(asset_name)}_{self._slugify_label(str(label_suffix))}"
            action_payload["placement_strategy"] = "prefab_structural_anchor" if is_prefab_asset(best) else "asset_anchor_snap"
            action_payload["placement_reference_actor"] = placement_targets.get("reference_actor_label")
            return action_payload
        return ActionDecision(
            action="no_op",
            target_zone=dirty_zone.zone_id,
            reason="No shortlist was available in mock mode.",
            confidence=0.9,
            expected_outcome="No change until better context is available.",
        ).to_orchestrator_dict()

    def _mock_review_decision(
        self,
        *,
        dirty_zone: DirtyZone,
        validation_report: dict[str, Any],
        action: Action,
    ) -> ReviewDecision:
        blocking = validation_report.get("blocking_failures", [])
        warnings = validation_report.get("warnings", [])
        if blocking:
            return ReviewDecision(
                decision="undo",
                target_zone=dirty_zone.zone_id,
                reason="Blocking validation failures exist.",
                confidence=0.95,
                issues=blocking,
                suggested_next_action={"action": "undo_last_group"},
            )
        if action.action == "no_op":
            return ReviewDecision(
                decision="request_state_refresh",
                target_zone=dirty_zone.zone_id,
                reason="No real edit happened, so better scene state is needed.",
                confidence=0.7,
                issues=[],
                suggested_next_action={"action": "refresh_scene_state"},
            )
        if warnings:
            return ReviewDecision(
                decision="revise",
                target_zone=dirty_zone.zone_id,
                reason="Warnings remain after the edit.",
                confidence=0.72,
                issues=warnings,
                suggested_next_action={"action": "local_refine"},
            )
        return ReviewDecision(
            decision="keep",
            target_zone=dirty_zone.zone_id,
            reason="No blocking failures or warnings in mock review.",
            confidence=0.82,
            issues=[],
            suggested_next_action={},
        )

    def _mock_completion_decision(
        self,
        *,
        dirty_zone: DirtyZone,
        validation_report: dict[str, Any],
        unresolved_issues: list[str],
    ) -> CompletionDecision:
        blocking = validation_report.get("blocking_failures", [])
        if blocking:
            return CompletionDecision(
                decision="blocked_by_validation",
                target_zone=dirty_zone.zone_id,
                reason="Blocking validation failures remain.",
                confidence=0.97,
                remaining_issues=list(blocking),
                next_focus="resolve_validation_failures",
            )
        if unresolved_issues:
            return CompletionDecision(
                decision="incomplete",
                target_zone=dirty_zone.zone_id,
                reason="The zone still has unresolved issues.",
                confidence=0.84,
                remaining_issues=unresolved_issues,
                next_focus="resolve_remaining_issues",
            )
        return CompletionDecision(
            decision="complete",
            target_zone=dirty_zone.zone_id,
            reason="No blocking issues remain in mock completion check.",
            confidence=0.75,
            remaining_issues=[],
            next_focus=None,
        )
