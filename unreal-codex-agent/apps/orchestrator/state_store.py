from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


class SessionStateStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    @staticmethod
    def utcnow_static() -> str:
        return utc_now_iso()

    def utcnow(self) -> str:
        return utc_now_iso()

    def initialize_session_layout(self, session_path: Path) -> None:
        (session_path / "scene_state").mkdir(parents=True, exist_ok=True)
        (session_path / "image_packets").mkdir(parents=True, exist_ok=True)
        (session_path / "developer_xray").mkdir(parents=True, exist_ok=True)
        (session_path / "uefn_bridge" / "placement_intents").mkdir(parents=True, exist_ok=True)
        (session_path / "uefn_bridge" / "apply_queue").mkdir(parents=True, exist_ok=True)
        (session_path / "uefn_bridge" / "layout_diffs").mkdir(parents=True, exist_ok=True)
        (session_path / "uefn_bridge" / "manifests").mkdir(parents=True, exist_ok=True)

    def _write_atomic_text(self, path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
                handle.write(payload)
                temp_path = Path(handle.name)
            temp_path.replace(path)
        finally:
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        self._write_atomic_text(path, json.dumps(payload, indent=2))

    def write_text(self, path: Path, payload: str) -> None:
        self._write_atomic_text(path, payload)

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def save_scene_state(self, session_path: Path, cycle_number: int, scene_state: dict[str, Any]) -> None:
        self.write_json(session_path / "scene_state" / f"cycle_{cycle_number:04d}.json", scene_state)
        self.write_json(session_path / "scene_state" / "current.json", scene_state)

    def save_capture_packet(
        self,
        session_path: Path,
        cycle_number: int,
        capture_packet: dict[str, Any],
    ) -> None:
        self.write_json(session_path / "image_packets" / f"cycle_{cycle_number:04d}.json", capture_packet)
        self.write_json(session_path / "image_packets" / "current.json", capture_packet)

    def append_action(self, session_path: Path, action_record: dict[str, Any]) -> None:
        self.append_jsonl(session_path / "action_history.jsonl", action_record)

    def append_score(self, session_path: Path, score: dict[str, Any]) -> None:
        self.append_jsonl(session_path / "score_history.jsonl", score)

    def write_completion_state(self, session_path: Path, payload: dict[str, Any]) -> None:
        self.write_json(session_path / "completion_state.json", payload)

    def load_completion_state(self, session_path: Path) -> dict[str, Any]:
        path = session_path / "completion_state.json"
        if not path.exists():
            return {
                "decision": "incomplete",
                "reason": "No completion state exists yet.",
                "updated_at_utc": self.utcnow(),
            }
        return self.read_json(path)

    def update_session_last_cycle(self, session_path: Path, cycle_number: int) -> None:
        session_file = session_path / "session.json"
        if not session_file.exists():
            return
        data = self.read_json(session_file)
        data["last_cycle_number"] = cycle_number
        self.write_json(session_file, data)
