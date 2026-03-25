from __future__ import annotations

from typing import Any

from apps.orchestrator.state_store import SessionStateStore


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def build_rule_result(
    *,
    name: str,
    passed: bool,
    blocking: bool,
    issues: list[str] | None = None,
    warnings: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "blocking": blocking,
        "issues": issues or [],
        "warnings": warnings or [],
        "details": details or {},
    }


def build_validation_report(*, zone_id: str, rule_results: list[dict[str, Any]]) -> dict[str, Any]:
    blocking_failures: list[str] = []
    warnings: list[str] = []
    passed_rules = 0
    failed_rules = 0
    for result in rule_results:
        if result.get("passed", False):
            passed_rules += 1
        else:
            failed_rules += 1
        if not result.get("passed", False):
            issues = result.get("issues", [])
            if result.get("blocking", False):
                blocking_failures.extend(issues)
            else:
                warnings.extend(issues)
        warnings.extend(result.get("warnings", []))
    blocking_failures = _dedupe_preserve_order(blocking_failures)
    warnings = _dedupe_preserve_order(warnings)
    return {
        "zone_id": zone_id,
        "passed": len(blocking_failures) == 0,
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "blocking_failure_count": len(blocking_failures),
        "warning_count": len(warnings),
        "passed_rule_count": passed_rules,
        "failed_rule_count": failed_rules,
        "rule_results": rule_results,
        "timestamp_utc": SessionStateStore.utcnow_static(),
    }


def report_builder(results: dict) -> str:
    return f"Validation passed={results.get('passed', False)}"
