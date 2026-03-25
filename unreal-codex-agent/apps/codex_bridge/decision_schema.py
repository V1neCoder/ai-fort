from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


DecisionType = Literal[
    "place_asset",
    "move_actor",
    "set_transform",
    "rotate_actor",
    "scale_actor",
    "replace_asset",
    "delete_actor",
    "request_more_views",
    "request_state_refresh",
    "no_op",
]

ReviewType = Literal[
    "keep",
    "revise",
    "replace",
    "undo",
    "request_more_views",
    "request_state_refresh",
]

CompletionType = Literal[
    "complete",
    "incomplete",
    "needs_more_review",
    "blocked_by_validation",
]


class TransformPayload(BaseModel):
    location: list[float] = Field(default_factory=list)
    rotation: list[float] = Field(default_factory=list)
    scale: list[float] = Field(default_factory=list)

    @field_validator("location", "rotation", "scale")
    @classmethod
    def _validate_triplet(cls, value: list[float]) -> list[float]:
        if value and len(value) != 3:
            raise ValueError("Transform vectors must have exactly 3 values when provided.")
        return value


class ActionDecision(BaseModel):
    action: DecisionType
    target_zone: str
    reason: str = ""
    confidence: float = 0.0
    asset_path: str | None = None
    managed_slot: str = "primary"
    identity_policy: str = "reuse_or_create"
    transform: TransformPayload = Field(default_factory=TransformPayload)
    placement_hint: dict[str, Any] = Field(default_factory=dict)
    expected_outcome: str | None = None
    alternatives: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def to_orchestrator_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target_zone": self.target_zone,
            "reason": self.reason,
            "confidence": self.confidence,
            "asset_path": self.asset_path,
            "managed_slot": self.managed_slot,
            "identity_policy": self.identity_policy,
            "transform": self.transform.model_dump(),
            "placement_hint": self.placement_hint,
            "expected_outcome": self.expected_outcome,
            "alternatives": self.alternatives,
        }


class ReviewDecision(BaseModel):
    decision: ReviewType
    target_zone: str
    reason: str = ""
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)
    suggested_next_action: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class CompletionDecision(BaseModel):
    decision: CompletionType
    target_zone: str
    reason: str = ""
    confidence: float = 0.0
    remaining_issues: list[str] = Field(default_factory=list)
    next_focus: str | None = None

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
