from __future__ import annotations

import json
import sys
from typing import Any


def validate_shell(
    *,
    shell_alignment: dict[str, Any],
    shell_sensitive: bool,
    require_inside_outside: bool = True,
) -> dict[str, Any]:
    if not shell_sensitive:
        return {
            "name": "validator_shell",
            "passed": True,
            "issues": [],
            "details": {"skipped": "zone_not_shell_sensitive"},
        }

    issues: list[str] = []
    warnings: list[str] = []
    if require_inside_outside and not shell_alignment.get("inside_checked", False):
        warnings.append("inside shell check missing")
    if require_inside_outside and not shell_alignment.get("outside_checked", False):
        warnings.append("outside shell check missing")
    if shell_alignment.get("is_consistent") is False:
        issues.append("inside/outside shell alignment mismatch detected")

    return {
        "name": "validator_shell",
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "details": shell_alignment,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "reason": "usage: validator_shell.py <shell_sensitive_bool> <shell_alignment_json>"}))
    else:
        shell_sensitive = sys.argv[1].strip().lower() in {"1", "true", "yes"}
        print(json.dumps(validate_shell(shell_alignment=json.loads(sys.argv[2]), shell_sensitive=shell_sensitive), indent=2))
