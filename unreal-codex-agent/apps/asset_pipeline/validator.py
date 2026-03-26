"""AI-powered visual validation of generated 3D assets using Gemini Vision."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import AssetSpec, ValidationResult, ValidationCheck
from .result_profile import build_profile
from .ai_client import vision_analyze, detect_vision_provider


def validate_asset(
    screenshot_dir: Path | str,
    screenshot_names: list[str],
    spec: AssetSpec,
    build_stats: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate a generated asset using vision AI + geometric checks.

    Args:
        screenshot_dir: Directory containing screenshot PNGs.
        screenshot_names: List of screenshot filenames.
        spec: The original asset specification.
        build_stats: Dict from mesh_builder (vertex_count, face_count, bounds).

    Returns:
        ValidationResult with per-check scores, issues, and pass/fail.
    """
    screenshot_dir = Path(screenshot_dir)
    profile = build_profile(spec)

    # Run geometric validation (no AI needed)
    geo_checks = _geometric_checks(build_stats or {}, spec)

    # Try vision validation
    vision_checks = _vision_validate(screenshot_dir, screenshot_names, spec, profile)

    # Merge results
    all_checks = []
    issues = []
    recommendations = []

    # Process vision checks
    if vision_checks:
        all_checks.extend(vision_checks.get("checks", []))
        issues.extend(vision_checks.get("issues", []))
        recommendations.extend(vision_checks.get("recommendations", []))

    # Process geometric checks
    all_checks.extend(geo_checks.get("checks", []))
    issues.extend(geo_checks.get("issues", []))

    # Calculate overall score
    if all_checks:
        total_weight = sum(c.weight for c in all_checks)
        if total_weight > 0:
            overall = sum(c.score * c.weight for c in all_checks) / total_weight
        else:
            overall = 0.0
    else:
        overall = 0.5  # No checks ran — uncertain

    passed = overall >= profile["pass_threshold"]

    return ValidationResult(
        passed=passed,
        overall_score=round(overall, 3),
        checks=all_checks,
        issues=issues,
        recommendations=recommendations,
        vision_provider=vision_checks.get("provider", "none") if vision_checks else "none",
    )


def _vision_validate(
    screenshot_dir: Path,
    screenshot_names: list[str],
    spec: AssetSpec,
    profile: dict,
) -> dict[str, Any] | None:
    """Send screenshots to vision AI for structural analysis."""
    provider, _ = detect_vision_provider()
    if not provider:
        return None

    # Collect existing screenshot paths
    image_paths = []
    for name in screenshot_names:
        p = screenshot_dir / name
        if p.exists():
            image_paths.append(p)

    if not image_paths:
        return None

    # Limit to 4 images to stay within free tier limits
    if len(image_paths) > 4:
        # Pick front, perspective, top, three_quarter
        priority = ["front", "perspective", "top", "three_quarter"]
        selected = []
        for pname in priority:
            for ip in image_paths:
                if pname in ip.stem:
                    selected.append(ip)
                    break
        image_paths = selected or image_paths[:4]

    # Build check descriptions for the prompt
    check_descs = "\n".join(
        f"  {i+1}. {c['name']}: {c['description']} (weight: {c['weight']:.2f})"
        for i, c in enumerate(profile["checks"])
    )

    prompt = f"""Analyze these screenshots of a 3D model that should be: "{spec.prompt}"
Category: {spec.category}
Required components: {', '.join(spec.required_components)}
Expected style: {spec.style or 'any'}

Score each criterion from 0.0 to 1.0:
{check_descs}

Also identify:
- Any structural issues (floating parts, missing components, wrong proportions)
- Recommendations for improvement

Respond ONLY as JSON:
{{
  "scores": {{"check_name": 0.0-1.0, ...}},
  "issues": ["issue 1", "issue 2"],
  "recommendations": ["rec 1", "rec 2"]
}}"""

    try:
        response = vision_analyze(prompt, [str(p) for p in image_paths])
    except Exception:
        return None

    # Parse response
    return _parse_vision_response(response, profile, provider)


def _parse_vision_response(
    response: str, profile: dict, provider: str,
) -> dict[str, Any]:
    """Parse vision AI response into structured checks."""
    # Extract JSON
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    text = json_match.group(1) if json_match else response

    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"checks": [], "issues": ["Vision AI response could not be parsed"], "recommendations": [], "provider": provider}

    scores = data.get("scores", {})
    issues = data.get("issues", [])
    recommendations = data.get("recommendations", [])

    checks = []
    for check_def in profile["checks"]:
        name = check_def["name"]
        score = scores.get(name, 0.5)
        # Clamp to 0-1
        score = max(0.0, min(1.0, float(score)))
        checks.append(ValidationCheck(
            name=name,
            description=check_def["description"],
            score=score,
            weight=check_def["weight"],
            passed=score >= check_def["threshold"],
        ))

    return {
        "checks": checks,
        "issues": issues if isinstance(issues, list) else [],
        "recommendations": recommendations if isinstance(recommendations, list) else [],
        "provider": provider,
    }


def _geometric_checks(
    build_stats: dict[str, Any], spec: AssetSpec,
) -> dict[str, Any]:
    """Run non-AI geometric validation checks."""
    checks = []
    issues = []

    vertex_count = build_stats.get("vertex_count", 0)
    face_count = build_stats.get("face_count", 0)
    bounds = build_stats.get("bounds", {})

    # Check vertex count is reasonable
    if vertex_count > 0:
        if vertex_count < 12:
            checks.append(ValidationCheck(
                name="geometry_minimum",
                description="Mesh has minimum geometric complexity",
                score=0.1,
                weight=0.05,
                passed=False,
            ))
            issues.append(f"Very low vertex count ({vertex_count}) — asset may be too simple")
        elif vertex_count > 50000:
            checks.append(ValidationCheck(
                name="geometry_budget",
                description="Vertex count within budget",
                score=0.4,
                weight=0.05,
                passed=False,
            ))
            issues.append(f"High vertex count ({vertex_count}) — may be too complex for game use")
        else:
            checks.append(ValidationCheck(
                name="geometry_budget",
                description="Vertex count within budget",
                score=0.9,
                weight=0.05,
                passed=True,
            ))

    # Check scale against spec
    if bounds and spec.scale_range_cm:
        size = bounds.get("size", [0, 0, 0])
        sr = spec.scale_range_cm
        width, depth, height = size[0], size[1], size[2]

        scale_ok = True
        if sr.get("max_width") and width > sr["max_width"] * 2:
            issues.append(f"Width {width:.0f}cm exceeds expected max {sr['max_width']}cm")
            scale_ok = False
        if sr.get("max_height") and height > sr["max_height"] * 2:
            issues.append(f"Height {height:.0f}cm exceeds expected max {sr['max_height']}cm")
            scale_ok = False

        checks.append(ValidationCheck(
            name="scale_check",
            description="Asset dimensions match expected scale range",
            score=0.85 if scale_ok else 0.3,
            weight=0.05,
            passed=scale_ok,
        ))

    return {"checks": checks, "issues": issues}
