from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from ue_runtime import load_unreal

import ue_apply_edit  # noqa: E402

unreal = load_unreal(("ScopedEditorTransaction",))


def run_action_in_transaction(
    action_payload: dict[str, Any],
    transaction_name: str = "Unreal Codex Agent Edit",
) -> dict[str, Any]:
    if unreal is None:
        return {"status": "error", "reason": "Unreal Python API is not available in this environment."}
    try:
        with unreal.ScopedEditorTransaction(transaction_name):
            result = ue_apply_edit.apply_action_payload(action_payload)
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "transaction_name": transaction_name}
    return {"status": "ok", "transaction_name": transaction_name, "result": result}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "reason": "usage: ue_undo_group.py <action_json>"}))
    else:
        try:
            action_payload = json.loads(sys.argv[1])
            result = run_action_in_transaction(action_payload)
        except Exception as exc:
            result = {"status": "error", "reason": str(exc)}
        print(json.dumps(result, indent=2))
