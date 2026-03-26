"""Pre-import approval checks for generated assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import AssetRecord


def check_approval(record: AssetRecord) -> dict[str, Any]:
    """Run pre-import approval checks on a generated asset.

    Returns:
        Dict with keys: approved (bool), reasons (list), warnings (list).
    """
    reasons = []
    warnings = []

    # Must have a GLB file
    if not record.glb_path:
        reasons.append("No GLB file generated")
    elif not Path(record.glb_path).exists():
        reasons.append(f"GLB file missing: {record.glb_path}")

    # Must have at least one validation
    if not record.validation_results:
        reasons.append("No validation results")
    else:
        latest = record.latest_validation
        if latest:
            score = latest.get("overall_score", 0)
            if score < 0.50:
                reasons.append(f"Validation score too low: {score:.2f} (minimum 0.50)")
            elif score < 0.65:
                warnings.append(f"Validation score below ideal: {score:.2f} (target 0.65)")

    # Check vertex count
    if record.vertex_count > 50000:
        warnings.append(f"High vertex count: {record.vertex_count}")

    if record.vertex_count == 0:
        reasons.append("No geometry data (0 vertices)")

    # Must have preview screenshots
    if not record.preview_screenshots:
        warnings.append("No preview screenshots")

    approved = len(reasons) == 0
    return {
        "approved": approved,
        "reasons": reasons,
        "warnings": warnings,
    }
