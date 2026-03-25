from __future__ import annotations

from typing import Any

from apps.orchestrator.dirty_zone import DirtyZone
from apps.orchestrator.state_store import SessionStateStore


class CompletionGate:
    def evaluate(
        self,
        validator_rules: dict[str, Any],
        validation_report: dict[str, Any],
        review: dict[str, Any],
        score: dict[str, Any],
        dirty_zone: DirtyZone,
    ) -> dict[str, Any]:
        completion_cfg = validator_rules.get("completion_gate", {})
        require_validator_pass = completion_cfg.get("require_validator_pass", True)
        require_visual_review_pass = completion_cfg.get("require_visual_review_pass", True)

        blocking_failures = validation_report.get("blocking_failures", [])
        warnings = validation_report.get("warnings", [])
        review_decision = review.get("decision", "keep")
        overall_score = int(score.get("overall_score", 0))

        if require_validator_pass and blocking_failures:
            return {
                "decision": "blocked_by_validation",
                "target_zone": dirty_zone.zone_id,
                "reason": "Blocking validator failures remain.",
                "updated_at_utc": SessionStateStore.utcnow_static(),
            }

        if require_visual_review_pass and review_decision in {"undo", "replace", "revise"}:
            return {
                "decision": "incomplete",
                "target_zone": dirty_zone.zone_id,
                "reason": f"Visual review result was '{review_decision}', so the zone is not complete.",
                "updated_at_utc": SessionStateStore.utcnow_static(),
            }

        if review_decision in {"request_more_views", "request_state_refresh"}:
            return {
                "decision": "needs_more_review",
                "target_zone": dirty_zone.zone_id,
                "reason": f"Review requested '{review_decision}', so more evidence is needed before completion.",
                "updated_at_utc": SessionStateStore.utcnow_static(),
            }

        if overall_score >= 85 and review_decision == "keep" and not warnings:
            return {
                "decision": "complete",
                "target_zone": dirty_zone.zone_id,
                "reason": "Validators passed and review accepted the current zone state.",
                "updated_at_utc": SessionStateStore.utcnow_static(),
            }

        if overall_score >= 70 or warnings:
            return {
                "decision": "needs_more_review",
                "target_zone": dirty_zone.zone_id,
                "reason": "The zone is promising but still needs another pass before completion.",
                "updated_at_utc": SessionStateStore.utcnow_static(),
            }

        return {
            "decision": "incomplete",
            "target_zone": dirty_zone.zone_id,
            "reason": "Zone score is below the completion threshold.",
            "updated_at_utc": SessionStateStore.utcnow_static(),
        }
