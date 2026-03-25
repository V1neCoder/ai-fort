from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.codex_bridge.image_packet_builder import build_image_review_summary
from apps.integrations.uefn_backend import backend_summary, choose_action_backend, choose_scene_backend
from apps.integrations.prefabricator import prefabricator_settings, should_prefer_prefabs
from apps.integrations.uefn_toolbelt import toolbelt_source_inventory


class PromptBuilder:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.prompt_dir = repo_root / "config" / "codex_prompts"
        self._project_config: dict[str, Any] | None = None

    def _read_prompt_file(self, name: str) -> str:
        path = self.prompt_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Missing prompt file: {path}")
        return path.read_text(encoding="utf-8")

    def system_prompt(self) -> str:
        return self._read_prompt_file("system_prompt.md")

    def asset_selection_prompt(self) -> str:
        return self._read_prompt_file("asset_selection_prompt.md")

    def edit_review_prompt(self) -> str:
        return self._read_prompt_file("edit_review_prompt.md")

    def completion_prompt(self) -> str:
        return self._read_prompt_file("completion_prompt.md")

    def quality_grounding(self) -> str:
        try:
            return self._read_prompt_file("uefn_quality_grounding.md")
        except FileNotFoundError:
            return ""

    def _load_project_config(self) -> dict[str, Any]:
        if self._project_config is not None:
            return self._project_config
        project_path = self.repo_root / "config" / "project.json"
        if not project_path.exists():
            self._project_config = {}
            return self._project_config
        try:
            payload = json.loads(project_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        self._project_config = payload if isinstance(payload, dict) else {}
        return self._project_config

    def _placement_summary(self, scene_state: dict[str, Any]) -> dict[str, Any]:
        placement_context = dict(scene_state.get("placement_context") or {})
        placement_targets = dict(scene_state.get("placement_targets") or {})
        project_config = self._load_project_config()
        expected_mount_type = scene_state.get("expected_mount_type")
        prefab_config = prefabricator_settings(project_config)
        try:
            runtime_summary = backend_summary(self.repo_root)
        except Exception:
            runtime_summary = {
                "platform": "uefn",
                "scene_backend": choose_scene_backend(self.repo_root),
                "action_backend": choose_action_backend(self.repo_root),
            }
        return {
            "platform": "uefn",
            "expected_mount_type": expected_mount_type,
            "mount_type": placement_context.get("mount_type"),
            "compatible_mount_types": placement_context.get("compatible_mount_types", []),
            "anchor_preference": placement_context.get("anchor_preference"),
            "placement_phase": placement_context.get("placement_phase"),
            "snap_policy": placement_context.get("snap_policy"),
            "support_reference_policy": placement_context.get("support_reference_policy"),
            "snap_grid_cm": placement_context.get("snap_grid_cm"),
            "preferred_yaw_step_deg": placement_context.get("preferred_yaw_step_deg"),
            "preferred_pitch_step_deg": placement_context.get("preferred_pitch_step_deg"),
            "requires_uniform_scale": placement_context.get("requires_uniform_scale"),
            "reference_yaw_deg": placement_context.get("reference_yaw_deg"),
            "reference_pitch_deg": placement_context.get("reference_pitch_deg"),
            "placement_reference_quality": scene_state.get("placement_reference_quality"),
            "support_surface_kind": placement_targets.get("support_surface_kind"),
            "support_level": placement_targets.get("support_level"),
            "parent_support_actor": placement_targets.get("parent_support_actor"),
            "support_actor_label": placement_targets.get("support_actor_label"),
            "support_reference_source": placement_targets.get("support_reference_source"),
            "surface_anchor": placement_targets.get("surface_anchor"),
            "ground_anchor": placement_targets.get("ground_anchor"),
            "landscape_anchor": placement_targets.get("landscape_anchor"),
            "support_graph": scene_state.get("support_graph", []),
            "placement_targets": placement_targets,
            "scene_backend": runtime_summary.get("scene_backend"),
            "action_backend": runtime_summary.get("action_backend"),
            "scene_graph_enabled": runtime_summary.get("scene_graph_enabled", True),
            "fortnite_devices_enabled": runtime_summary.get("fortnite_devices_enabled", True),
            "prefabricator_enabled": bool(prefab_config.get("enabled", False)),
            "preferred_prefab_mount_types": prefab_config.get("prefer_prefabs_for_mount_types", []),
            "prefer_prefab_for_structural_mounts": should_prefer_prefabs(project_config, expected_mount_type),
        }

    def _build_scene_packet(
        self,
        *,
        build_goal: str,
        scene_state: dict[str, Any],
        dirty_zone: dict[str, Any],
        capture_packet: dict[str, Any],
        shortlist: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            runtime_summary = backend_summary(self.repo_root)
        except Exception:
            runtime_summary = {
                "platform": "uefn",
                "scene_backend": choose_scene_backend(self.repo_root),
                "action_backend": choose_action_backend(self.repo_root),
            }
        try:
            source_inventory = toolbelt_source_inventory(self.repo_root)
        except Exception:
            source_inventory = {"tool_count": 0, "workflow_count": 0, "sample_tools": []}
        return {
            "build_goal": build_goal,
            "scene_state": scene_state,
            "dirty_zone": dirty_zone,
            "placement_summary": self._placement_summary(scene_state),
            "runtime_summary": runtime_summary,
            "toolbelt_inventory": source_inventory,
            "quality_grounding": self.quality_grounding(),
            "capture_packet": {
                "packet_id": capture_packet.get("packet_id"),
                "zone_id": capture_packet.get("zone_id"),
                "profile": capture_packet.get("profile"),
            },
            "shortlist": shortlist,
        }

    def build_action_payload(
        self,
        *,
        build_goal: str,
        scene_state: dict[str, Any],
        dirty_zone: dict[str, Any],
        capture_packet: dict[str, Any],
        shortlist: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt(),
            "task_prompt": self.asset_selection_prompt(),
            "scene_packet": self._build_scene_packet(
                build_goal=build_goal,
                scene_state=scene_state,
                dirty_zone=dirty_zone,
                capture_packet=capture_packet,
                shortlist=shortlist or [],
            ),
            "capture_summary": build_image_review_summary(capture_packet),
        }

    def build_review_payload(
        self,
        *,
        build_goal: str,
        scene_state: dict[str, Any],
        dirty_zone: dict[str, Any],
        capture_packet: dict[str, Any],
        validation_report: dict[str, Any],
        previous_action: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt(),
            "task_prompt": self.edit_review_prompt(),
            "quality_grounding": self.quality_grounding(),
            "build_goal": build_goal,
            "scene_state": scene_state,
            "dirty_zone": dirty_zone,
            "placement_summary": self._placement_summary(scene_state),
            "capture_summary": build_image_review_summary(capture_packet),
            "validation_report": validation_report,
            "previous_action": previous_action,
        }

    def build_completion_payload(
        self,
        *,
        build_goal: str,
        scene_state: dict[str, Any],
        dirty_zone: dict[str, Any],
        capture_packet: dict[str, Any],
        validation_report: dict[str, Any],
        unresolved_issues: list[str],
    ) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt(),
            "task_prompt": self.completion_prompt(),
            "quality_grounding": self.quality_grounding(),
            "build_goal": build_goal,
            "scene_state": scene_state,
            "dirty_zone": dirty_zone,
            "placement_summary": self._placement_summary(scene_state),
            "capture_summary": build_image_review_summary(capture_packet),
            "validation_report": validation_report,
            "unresolved_issues": unresolved_issues,
        }
