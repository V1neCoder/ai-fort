from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PYTHON_DIR = CURRENT_DIR.parent / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import ue_write_metadata  # noqa: E402


def validate_metadata(
    *,
    asset_path: str,
    required_keys: list[str],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if metadata is None:
        try:
            result = ue_write_metadata.get_metadata(asset_path, required_keys)
        except Exception as exc:
            result = {
                "status": "error",
                "asset_path": asset_path,
                "reason": str(exc),
                "metadata": {},
            }
        metadata = result.get("metadata", {})
        if result.get("status") == "error":
            return {
                "name": "validator_metadata",
                "passed": False,
                "issues": [f"metadata lookup failed: {result.get('reason', 'unknown error')}"],
                "details": {
                    "asset_path": asset_path,
                    "metadata": metadata,
                },
            }

    issues = [f"missing metadata key: {key}" for key in required_keys if not metadata.get(key)]
    return {
        "name": "validator_metadata",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": {
            "asset_path": asset_path,
            "metadata": metadata,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "reason": "usage: validator_metadata.py <asset_path> <required_keys_json>"}))
    else:
        print(json.dumps(validate_metadata(asset_path=sys.argv[1], required_keys=json.loads(sys.argv[2])), indent=2))
