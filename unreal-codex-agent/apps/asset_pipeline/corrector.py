"""Analyze validation failures and build correction context for retry."""

from __future__ import annotations

from typing import Any

from .models import AssetSpec, ValidationResult


def build_correction_context(
    spec: AssetSpec,
    validation: ValidationResult,
    previous_code: str,
    attempt: int,
) -> str:
    """Analyze validation failures and produce a correction prompt.

    Args:
        spec: The asset specification.
        validation: The failed validation result.
        previous_code: The code from the failed attempt.
        attempt: Current attempt number.

    Returns:
        Error context string to pass to code_generator for retry.
    """
    lines = []

    # Overall score
    lines.append(f"Overall validation score: {validation.overall_score:.2f} (needed: 0.65)")

    # Failed checks
    failed_checks = [c for c in validation.checks if not c.passed]
    if failed_checks:
        lines.append("\nFailed checks:")
        for c in failed_checks:
            lines.append(f"  - {c.name} (score: {c.score:.2f}): {c.description}")

    # Issues found
    if validation.issues:
        lines.append("\nSpecific issues detected:")
        for issue in validation.issues:
            lines.append(f"  - {issue}")

    # Recommendations
    if validation.recommendations:
        lines.append("\nRecommendations:")
        for rec in validation.recommendations:
            lines.append(f"  - {rec}")

    # Attempt-specific guidance
    if attempt == 2:
        lines.append("\nFocus on fixing the specific issues above.")
        lines.append("Add more structural detail to make the asset recognizable.")
    elif attempt >= 3:
        lines.append("\nThis is the final attempt. Simplify the geometry if needed,")
        lines.append("but ensure the asset is clearly recognizable and complete.")
        lines.append("Prioritize: correct proportions, all required components present,")
        lines.append("proper colors, no floating parts.")

    return "\n".join(lines)


def should_retry(validation: ValidationResult, attempt: int, max_attempts: int = 3) -> bool:
    """Decide whether to retry generation.

    Returns True if the asset failed validation and we haven't exceeded max attempts.
    """
    if validation.passed:
        return False
    if attempt >= max_attempts:
        return False
    # Don't retry if score is catastrophically low (AI probably can't fix it)
    if validation.overall_score < 0.15 and attempt > 1:
        return False
    return True
