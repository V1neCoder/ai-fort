"""Data models for the AI asset generation pipeline."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class AssetSpec:
    """Structured specification parsed from a user prompt."""

    prompt: str
    asset_name: str = ""
    category: str = "prop"  # furniture, architecture, terrain, prop, vegetation, vehicle
    purpose: str = ""
    required_components: list[str] = field(default_factory=list)
    expected_silhouette: str = ""
    scale_range_cm: dict[str, float] = field(default_factory=dict)
    interior_required: bool = False
    failure_conditions: list[str] = field(default_factory=list)
    style: str = ""  # modern, medieval, futuristic, rustic, etc.
    color_palette: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "asset_name": self.asset_name,
            "category": self.category,
            "purpose": self.purpose,
            "required_components": self.required_components,
            "expected_silhouette": self.expected_silhouette,
            "scale_range_cm": self.scale_range_cm,
            "interior_required": self.interior_required,
            "failure_conditions": self.failure_conditions,
            "style": self.style,
            "color_palette": self.color_palette,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetSpec":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ValidationCheck:
    """A single validation criterion result."""

    name: str
    passed: bool
    score: float  # 0.0 - 1.0
    detail: str = ""


@dataclass
class ValidationResult:
    """Result of AI visual validation."""

    passed: bool
    overall_score: float
    checks: list[ValidationCheck] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "overall_score": self.overall_score,
            "checks": [
                {"name": c.name, "passed": c.passed, "score": c.score, "detail": c.detail}
                for c in self.checks
            ],
            "issues": self.issues,
            "recommendations": self.recommendations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationResult":
        checks = [ValidationCheck(**c) for c in data.get("checks", [])]
        return cls(
            passed=data.get("passed", False),
            overall_score=data.get("overall_score", 0.0),
            checks=checks,
            issues=data.get("issues", []),
            recommendations=data.get("recommendations", []),
        )


@dataclass
class FixEntry:
    """Record of a single correction attempt."""

    attempt: int
    issues_addressed: list[str] = field(default_factory=list)
    code_changes: str = ""
    timestamp: str = field(default_factory=_now_iso)


@dataclass
class AssetRecord:
    """Complete lifecycle record for a generated asset."""

    asset_id: str = field(default_factory=_new_id)
    name: str = ""
    category: str = "prop"
    project: str = "default"
    prompt: str = ""
    spec: AssetSpec | None = None
    version: int = 1
    status: str = "pending"  # pending, generating, preview_ready, validating, approved, rejected, imported, error
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    # File paths (relative to data/ai_assets/<project>/<name>/)
    glb_path: str = ""
    preview_screenshots: list[str] = field(default_factory=list)
    generated_code: str = ""

    # Validation
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    fix_history: list[dict[str, Any]] = field(default_factory=list)
    latest_validation: dict[str, Any] = field(default_factory=dict)

    # UEFN import
    uefn_import_path: str = ""
    imported_at: str = ""

    # Generation metadata
    generation_provider: str = ""
    vertex_count: int = 0
    face_count: int = 0
    bounds_cm: dict[str, float] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        d = {
            "asset_id": self.asset_id,
            "name": self.name,
            "category": self.category,
            "project": self.project,
            "prompt": self.prompt,
            "spec": self.spec.to_dict() if self.spec else None,
            "version": self.version,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "glb_path": self.glb_path,
            "preview_screenshots": self.preview_screenshots,
            "generated_code": self.generated_code,
            "validation_results": self.validation_results,
            "fix_history": self.fix_history,
            "latest_validation": self.latest_validation,
            "uefn_import_path": self.uefn_import_path,
            "imported_at": self.imported_at,
            "generation_provider": self.generation_provider,
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "bounds_cm": self.bounds_cm,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetRecord":
        spec_data = data.pop("spec", None)
        # Filter to known fields only
        known = {k for k in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        record = cls(**filtered)
        if spec_data and isinstance(spec_data, dict):
            record.spec = AssetSpec.from_dict(spec_data)
        return record

    def to_shortlist_entry(self, base_url: str = "") -> dict[str, Any]:
        """Convert to the format used by AssetBrowser frontend."""
        glb_url = f"{base_url}/ai_assets/{self.project}/{self.name}/exports/{self.name}_v{self.version}.glb" if self.glb_path else ""
        thumbnail = ""
        if self.preview_screenshots:
            first = self.preview_screenshots[0] if self.preview_screenshots else ""
            if first:
                thumbnail = f"{base_url}/ai_assets/{self.project}/{self.name}/previews/{first}"

        return {
            "id": self.asset_id,
            "name": self.name.replace("_", " ").title(),
            "type": self.category,
            "category": self.category,
            "description": self.prompt,
            "tags": [self.category, "ai-generated", self.spec.style if self.spec else ""],
            "dimensions": self.bounds_cm,
            "trust_score": self.latest_validation.get("overall_score", 0.0),
            "composite_asset": False,
            "viewer_model_url": glb_url,
            "viewer_note": f"AI Generated v{self.version} — {self.status}",
            "pipeline_asset": True,
            "pipeline_id": self.asset_id,
            "pipeline_status": self.status,
        }
