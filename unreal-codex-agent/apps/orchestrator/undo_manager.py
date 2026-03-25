from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UndoGroup:
    undo_group_id: str
    zone_id: str
    cycle_number: int
    actions: list[dict[str, Any]] = field(default_factory=list)
    committed: bool = False


class UndoManager:
    def __init__(self) -> None:
        self._groups: dict[str, UndoGroup] = {}
        self._order: list[str] = []

    def begin_group(self, zone_id: str, cycle_number: int) -> str:
        group_id = f"{zone_id}_undo_{cycle_number:04d}"
        self._groups[group_id] = UndoGroup(
            undo_group_id=group_id,
            zone_id=zone_id,
            cycle_number=cycle_number,
        )
        self._order.append(group_id)
        return group_id

    def record_action(self, undo_group_id: str, action_payload: dict[str, Any]) -> None:
        group = self._groups.get(undo_group_id)
        if group is None:
            return
        group.actions.append(action_payload)

    def commit_group(self, undo_group_id: str) -> None:
        group = self._groups.get(undo_group_id)
        if group is None:
            return
        group.committed = True

    def pop_last_group(self) -> UndoGroup | None:
        if not self._order:
            return None
        group_id = self._order.pop()
        return self._groups.pop(group_id, None)
