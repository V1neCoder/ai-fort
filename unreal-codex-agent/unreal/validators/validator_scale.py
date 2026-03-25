from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PYTHON_DIR = CURRENT_DIR.parent / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import ue_measure_asset  # noqa: E402


def validate_scale(
    *,
    asset_path: str,
    expected_dimensions_cm: dict[str, float],
) -> dict[str, Any]:
    try:
        measurement = ue_measure_asset.measure_asset(asset_path)
    except Exception as exc:
        measurement = {
            "status": "error",
            "asset_path": asset_path,
            "reason": str(exc),
        }
    if measurement.get("status") != "ok":
        return {
            "name": "validator_scale",
            "passed": False,
            "issues": [f"asset measurement failed: {measurement.get('reason', measurement.get('status'))}"],
            "details": measurement,
        }

    dims = measurement.get("dimensions_cm", {})
    width = float(dims.get("width", 0))
    depth = float(dims.get("depth", 0))
    height = float(dims.get("height", 0))
    issues: list[str] = []

    if width < float(expected_dimensions_cm.get("width_min", 0)) or width > float(expected_dimensions_cm.get("width_max", 999999)):
        issues.append(f"width {width:.1f}cm outside expected range")
    if depth < float(expected_dimensions_cm.get("depth_min", 0)) or depth > float(expected_dimensions_cm.get("depth_max", 999999)):
        issues.append(f"depth {depth:.1f}cm outside expected range")
    if height < float(expected_dimensions_cm.get("height_min", 0)) or height > float(expected_dimensions_cm.get("height_max", 999999)):
        issues.append(f"height {height:.1f}cm outside expected range")

    return {
        "name": "validator_scale",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": {
            "asset_path": asset_path,
            "dimensions_cm": dims,
            "expected_dimensions_cm": expected_dimensions_cm,
            "measurement_method": measurement.get("method"),
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "reason": "usage: validator_scale.py <asset_path> <expected_dimensions_json>"}))
    else:
        print(json.dumps(validate_scale(asset_path=sys.argv[1], expected_dimensions_cm=json.loads(sys.argv[2])), indent=2))
