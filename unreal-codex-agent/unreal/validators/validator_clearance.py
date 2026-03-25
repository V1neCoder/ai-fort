from __future__ import annotations

import json
import sys
from typing import Any


def validate_clearance(
    *,
    observed_clearance_cm: dict[str, Any],
    required_clearance_cm: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    for observed_key, required_key, label in (
        ("front_cm", "front_cm", "front"),
        ("side_cm", "side_cm", "side"),
        ("back_cm", "back_cm", "back"),
    ):
        required = required_clearance_cm.get(required_key)
        observed = observed_clearance_cm.get(observed_key)
        if required is None:
            continue
        if observed is None:
            warnings.append(f"{label} clearance observation missing")
            continue
        if float(observed) < float(required):
            issues.append(f"{label} clearance {float(observed):.1f}cm below required {float(required):.1f}cm")

    return {
        "name": "validator_clearance",
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "details": {
            "observed": observed_clearance_cm,
            "required": required_clearance_cm,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "reason": "usage: validator_clearance.py <observed_json> <required_json>"}))
    else:
        print(json.dumps(validate_clearance(observed_clearance_cm=json.loads(sys.argv[1]), required_clearance_cm=json.loads(sys.argv[2])), indent=2))
