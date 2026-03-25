from __future__ import annotations

import json
import sys
from typing import Any


def validate_asset_trust(
    *,
    asset_record: dict[str, Any],
    min_trust_score: int = 70,
    allow_statuses: list[str] | None = None,
) -> dict[str, Any]:
    allow_statuses = allow_statuses or ["approved", "limited"]
    trust_score = int(asset_record.get("trust_score", 0))
    status = str(asset_record.get("status", "unknown"))
    issues: list[str] = []

    if trust_score < min_trust_score:
        issues.append(f"trust_score {trust_score} below minimum {min_trust_score}")
    if status not in allow_statuses:
        issues.append(f"status '{status}' is not in allowed statuses {allow_statuses}")

    return {
        "name": "validator_asset_trust",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": {
            "asset_id": asset_record.get("asset_id"),
            "asset_path": asset_record.get("asset_path"),
            "trust_score": trust_score,
            "status": status,
            "allow_statuses": allow_statuses,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "reason": "usage: validator_asset_trust.py <asset_record_json> [min_trust_score]"}))
    else:
        min_trust_score = int(sys.argv[2]) if len(sys.argv) > 2 else 70
        print(json.dumps(validate_asset_trust(asset_record=json.loads(sys.argv[1]), min_trust_score=min_trust_score), indent=2))
