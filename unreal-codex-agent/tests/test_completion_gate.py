from apps.orchestrator.completion_gate import CompletionGate
from apps.orchestrator.dirty_zone import DirtyZone


def make_dirty_zone() -> DirtyZone:
    return DirtyZone(
        zone_id="zone_0001",
        actor_ids=["Actor_A"],
        room_type="living_room",
        zone_type="room_local",
        shell_sensitive=False,
        capture_profile="default_room",
        bounds={},
    )


def test_completion_gate_blocks_when_validator_has_blocking_failures():
    gate = CompletionGate()
    result = gate.evaluate(
        validator_rules={
            "completion_gate": {
                "require_validator_pass": True,
                "require_visual_review_pass": True,
            }
        },
        validation_report={
            "blocking_failures": ["scale axis x outside safe range"],
            "warnings": [],
        },
        review={
            "decision": "keep",
        },
        score={
            "overall_score": 95,
        },
        dirty_zone=make_dirty_zone(),
    )

    assert result["decision"] == "blocked_by_validation"


def test_completion_gate_marks_complete_for_strong_keep_result():
    gate = CompletionGate()
    result = gate.evaluate(
        validator_rules={
            "completion_gate": {
                "require_validator_pass": True,
                "require_visual_review_pass": True,
            }
        },
        validation_report={
            "blocking_failures": [],
            "warnings": [],
        },
        review={
            "decision": "keep",
        },
        score={
            "overall_score": 91,
        },
        dirty_zone=make_dirty_zone(),
    )

    assert result["decision"] == "complete"


def test_completion_gate_requests_more_review_when_score_is_midrange():
    gate = CompletionGate()
    result = gate.evaluate(
        validator_rules={
            "completion_gate": {
                "require_validator_pass": True,
                "require_visual_review_pass": True,
            }
        },
        validation_report={
            "blocking_failures": [],
            "warnings": [],
        },
        review={
            "decision": "keep",
        },
        score={
            "overall_score": 74,
        },
        dirty_zone=make_dirty_zone(),
    )

    assert result["decision"] == "needs_more_review"
