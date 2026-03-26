"""Build validation criteria from an AssetSpec."""

from __future__ import annotations

from .models import AssetSpec


def build_profile(spec: AssetSpec) -> dict:
    """Generate a validation profile with weighted criteria."""
    checks = [
        {
            "name": "identity_match",
            "description": f"Does this clearly look like a {spec.category}?",
            "weight": 0.25,
            "threshold": 0.6,
        },
        {
            "name": "structural_completeness",
            "description": f"Are these components present: {', '.join(spec.required_components)}?",
            "weight": 0.20,
            "threshold": 0.5,
        },
        {
            "name": "proportion_accuracy",
            "description": "Are the proportions realistic and reasonable?",
            "weight": 0.15,
            "threshold": 0.5,
        },
        {
            "name": "geometry_quality",
            "description": "No floating parts, broken surfaces, overlapping geometry?",
            "weight": 0.15,
            "threshold": 0.5,
        },
        {
            "name": "silhouette_readability",
            "description": "Would a person recognize what this is from the silhouette?",
            "weight": 0.15,
            "threshold": 0.5,
        },
        {
            "name": "scale_consistency",
            "description": "Does it look the right size for its type?",
            "weight": 0.10,
            "threshold": 0.4,
        },
    ]

    if spec.interior_required:
        checks.append({
            "name": "interior_validity",
            "description": "Is the interior space valid, accessible, and coherent?",
            "weight": 0.15,
            "threshold": 0.5,
        })
        # Re-normalize weights
        total = sum(c["weight"] for c in checks)
        for c in checks:
            c["weight"] /= total

    return {
        "asset_name": spec.asset_name,
        "category": spec.category,
        "prompt": spec.prompt,
        "required_components": spec.required_components,
        "scale_range_cm": spec.scale_range_cm,
        "interior_required": spec.interior_required,
        "failure_conditions": spec.failure_conditions,
        "style": spec.style,
        "checks": checks,
        "pass_threshold": 0.65,
    }
