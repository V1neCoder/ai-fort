from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_transform(transform: Any) -> dict[str, Any]:
    if not isinstance(transform, dict):
        return {}

    normalized: dict[str, Any] = {}
    for key, fallback in (("location", [0.0, 0.0, 0.0]), ("rotation", [0.0, 0.0, 0.0]), ("scale", [1.0, 1.0, 1.0])):
        value = transform.get(key)
        if isinstance(value, (list, tuple)):
            padded = list(value[:3]) + fallback[len(value[:3]) :]
            normalized[key] = [_safe_float(padded[0], fallback[0]), _safe_float(padded[1], fallback[1]), _safe_float(padded[2], fallback[2])]
        elif isinstance(value, dict):
            normalized[key] = [
                _safe_float(value.get("x"), fallback[0]),
                _safe_float(value.get("y"), fallback[1]),
                _safe_float(value.get("z"), fallback[2]),
            ]
    for key, value in transform.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


@dataclass
class Action:
    action: str
    target_zone: str
    reason: str = ""
    confidence: float = 0.0
    asset_path: str | None = None
    managed_slot: str = "primary"
    identity_policy: str = "reuse_or_create"
    transform: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Action":
        payload = dict(data) if isinstance(data, dict) else {}
        return cls(
            action=str(payload.get("action") or "no_op"),
            target_zone=str(payload.get("target_zone") or "unknown_zone"),
            reason=str(payload.get("reason") or ""),
            confidence=max(0.0, min(1.0, _safe_float(payload.get("confidence"), 0.0))),
            asset_path=str(payload.get("asset_path")) if payload.get("asset_path") is not None else None,
            managed_slot=str(payload.get("managed_slot") or "primary"),
            identity_policy=str(payload.get("identity_policy") or "reuse_or_create"),
            transform=_normalize_transform(payload.get("transform")),
            raw=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "action": self.action,
            "target_zone": self.target_zone,
            "reason": self.reason,
            "confidence": self.confidence,
            "asset_path": self.asset_path,
            "managed_slot": self.managed_slot,
            "identity_policy": self.identity_policy,
            "transform": self.transform,
            "raw": self.raw,
        }
        for key, value in self.raw.items():
            if key not in payload:
                payload[key] = value
        return payload


class ActionQueue:
    def __init__(self) -> None:
        self._queue: list[Action] = []

    def enqueue(self, action: Action) -> None:
        self._queue.append(action)

    def dequeue(self) -> Action | None:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def peek(self) -> Action | None:
        if not self._queue:
            return None
        return self._queue[0]

    def clear(self) -> None:
        self._queue.clear()

    def size(self) -> int:
        return len(self._queue)
