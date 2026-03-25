from __future__ import annotations

from typing import Any

from apps.orchestrator.action_queue import Action
from apps.orchestrator.dirty_zone import DirtyZone
from apps.orchestrator.state_store import SessionStateStore


class ScoreCalculator:
    @staticmethod
    def _action_quality(action: Action) -> int:
        if action.action == "no_op":
            return 55
        score = 72
        if action.confidence >= 0.8:
            score += 4
        elif action.confidence >= 0.65:
            score += 2
        if action.raw.get("placement_strategy"):
            score += 4
        if action.raw.get("placement_reference_actor"):
            score += 3
        transform = action.transform or {}
        location = transform.get("location")
        if isinstance(location, list) and any(abs(float(value)) > 0.001 for value in location):
            score += 2
        return min(score, 85)

    def calculate(
        self,
        validation_report: dict[str, Any],
        review: dict[str, Any],
        action: Action,
        dirty_zone: DirtyZone,
    ) -> dict[str, Any]:
        blocking_failures = validation_report.get("blocking_failures", [])
        warnings = validation_report.get("warnings", [])

        validator_score = 100
        validator_score -= len(blocking_failures) * 35
        validator_score -= len(warnings) * 8
        validator_score = max(0, validator_score)

        decision = review.get("decision", "keep")
        review_score = {
            "keep": 88,
            "revise": 62,
            "replace": 54,
            "undo": 20,
            "request_more_views": 45,
            "request_state_refresh": 40,
        }.get(decision, 50)

        action_score = self._action_quality(action)
        overall_score = round((validator_score * 0.45) + (review_score * 0.40) + (action_score * 0.15))

        return {
            "zone_id": dirty_zone.zone_id,
            "validator_score": validator_score,
            "review_score": review_score,
            "action_score": action_score,
            "overall_score": overall_score,
            "decision": decision,
            "updated_at_utc": SessionStateStore.utcnow_static(),
        }
