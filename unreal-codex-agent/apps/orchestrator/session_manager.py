from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apps.orchestrator.state_store import SessionStateStore, utc_timestamp_slug


@dataclass
class SessionRecord:
    session_id: str
    session_path: Path
    goal: str
    created_at_utc: str
    last_cycle_number: int = 0


class SessionManager:
    def __init__(self, session_root: Path, state_store: SessionStateStore) -> None:
        self.session_root = session_root
        self.state_store = state_store
        self.session_root.mkdir(parents=True, exist_ok=True)

    def create_session(self, goal: str, requested_name: str | None = None) -> SessionRecord:
        suffix = utc_timestamp_slug()
        base_name = self._sanitize_name(requested_name or "session")
        session_id = f"{base_name}_{suffix}"
        session_path = self.session_root / session_id

        record = SessionRecord(
            session_id=session_id,
            session_path=session_path,
            goal=goal,
            created_at_utc=self.state_store.utcnow(),
            last_cycle_number=0,
        )

        self.state_store.initialize_session_layout(session_path)
        self.state_store.write_json(
            session_path / "session.json",
            {
                "session_id": record.session_id,
                "session_path": str(record.session_path),
                "goal": record.goal,
                "created_at_utc": record.created_at_utc,
                "last_cycle_number": record.last_cycle_number,
            },
        )
        self.state_store.write_completion_state(
            session_path,
            {
                "decision": "incomplete",
                "reason": "Session created but no cycles have run yet.",
                "updated_at_utc": self.state_store.utcnow(),
            },
        )
        return record

    def get_session(self, session_id: str) -> SessionRecord | None:
        session_path = self.session_root / session_id
        session_file = session_path / "session.json"
        if not session_file.exists():
            return None

        try:
            data = self.state_store.read_json(session_file)
        except Exception:
            return SessionRecord(
                session_id=session_id,
                session_path=session_path,
                goal="Recovered session with unreadable metadata.",
                created_at_utc=self.state_store.utcnow(),
                last_cycle_number=0,
            )
        return SessionRecord(
            session_id=str(data.get("session_id") or session_id),
            session_path=Path(str(data.get("session_path") or session_path)),
            goal=str(data.get("goal") or "Recovered session"),
            created_at_utc=str(data.get("created_at_utc") or self.state_store.utcnow()),
            last_cycle_number=int(data.get("last_cycle_number", 0)),
        )

    def update_last_cycle(self, session_id: str, cycle_number: int) -> None:
        session = self.get_session(session_id)
        if session is None:
            return

        session.last_cycle_number = cycle_number
        self.state_store.write_json(
            session.session_path / "session.json",
            {
                "session_id": session.session_id,
                "session_path": str(session.session_path),
                "goal": session.goal,
                "created_at_utc": session.created_at_utc,
                "last_cycle_number": session.last_cycle_number,
            },
        )

    def _sanitize_name(self, value: str) -> str:
        cleaned = value.strip().lower().replace(" ", "_")
        return "".join(ch for ch in cleaned if ch.isalnum() or ch in {"_", "-"}).strip("_") or "session"
