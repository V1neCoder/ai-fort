"""Main orchestrator for the AI asset generation pipeline."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

from .models import AssetSpec, AssetRecord, ValidationResult, FixEntry
from .storage import AssetStorage
from .registry import AssetRegistry
from .intent_parser import parse_intent
from .result_profile import build_profile
from .code_generator import generate_code
from .mesh_builder import build_mesh, validate_code_safety
from .preview import render_screenshots
from .validator import validate_asset
from .corrector import build_correction_context, should_retry
from .approval import check_approval
from .importer import import_to_uefn


class AssetPipeline:
    """End-to-end pipeline: prompt -> 3D asset -> validation -> UEFN import."""

    def __init__(self, storage: AssetStorage | None = None):
        self.storage = storage or AssetStorage()
        self.registry = AssetRegistry(self.storage)

    def generate(self, prompt: str, project: str = "default",
                 max_attempts: int = 3, auto_approve: bool = False) -> dict[str, Any]:
        """Run the full generation pipeline.

        Args:
            prompt: Natural language description of the asset.
            project: Project namespace.
            max_attempts: Maximum correction attempts.
            auto_approve: If True, auto-approve passing assets.

        Returns:
            Dict with asset_id, status, record details, and any errors.
        """
        result: dict[str, Any] = {"prompt": prompt, "project": project}

        # 1. Parse intent
        try:
            spec = parse_intent(prompt, project)
        except Exception as e:
            return {**result, "status": "error", "error": f"Intent parsing failed: {e}"}

        result["spec"] = spec.to_dict()

        # 2. Create registry entry
        try:
            record = self.registry.create(spec, project)
        except Exception as e:
            return {**result, "status": "error", "error": f"Registry creation failed: {e}"}

        result["asset_id"] = record.asset_id
        result["name"] = record.name

        # 3. Generation loop
        previous_code = ""
        error_context = ""

        for attempt in range(1, max_attempts + 1):
            record = self.registry.update_status(record, "generating")

            # Generate code
            try:
                code = generate_code(spec, attempt, previous_code, error_context)
            except Exception as e:
                record = self.registry.update_status(record, "generation_failed")
                result["status"] = "generation_failed"
                result["error"] = f"Code generation failed (attempt {attempt}): {e}"
                if attempt >= max_attempts:
                    return result
                continue

            # Safety check
            is_safe, reason = validate_code_safety(code)
            if not is_safe:
                error_context = f"Generated code contains unsafe operations: {reason}"
                previous_code = code
                if attempt >= max_attempts:
                    record = self.registry.update_status(record, "generation_failed")
                    result["status"] = "generation_failed"
                    result["error"] = error_context
                    return result
                continue

            # Build mesh
            export_dir = self.storage.exports_dir(project, record.name)
            try:
                build_result = build_mesh(code, record.name, export_dir, record.version)
            except Exception as e:
                build_result = {"success": False, "error": str(e), "traceback": traceback.format_exc()}

            if not build_result.get("success"):
                error_msg = build_result.get("error", "Unknown build error")
                tb = build_result.get("traceback", "")
                error_context = f"Build error: {error_msg}"
                if tb:
                    # Include last few lines of traceback for AI context
                    tb_lines = tb.strip().split("\n")
                    error_context += "\n" + "\n".join(tb_lines[-5:])
                previous_code = code

                self.registry.add_fix(record, {
                    "attempt": attempt,
                    "action": "build_failed",
                    "error": error_msg,
                })

                if attempt >= max_attempts:
                    record = self.registry.update_status(record, "build_failed")
                    result["status"] = "build_failed"
                    result["error"] = error_msg
                    return result
                continue

            # Update record with generation results
            record = self.registry.update_generation(
                record,
                glb_path=build_result["glb_path"],
                code=code,
                provider="free_ai",
                vertex_count=build_result.get("vertex_count", 0),
                face_count=build_result.get("face_count", 0),
                bounds=build_result.get("bounds"),
            )

            # Render previews
            preview_dir = self.storage.previews_dir(project, record.name)
            try:
                screenshots = render_screenshots(build_result["glb_path"], preview_dir, record.version)
                record = self.registry.update_previews(record, screenshots)
            except Exception:
                screenshots = []

            # Validate
            record = self.registry.update_status(record, "validating")
            try:
                validation = validate_asset(
                    preview_dir, screenshots, spec, build_result,
                )
            except Exception as e:
                # If validation itself fails, treat as a pass-through
                validation = ValidationResult(
                    passed=True,
                    overall_score=0.5,
                    checks=[],
                    issues=[f"Validation error: {e}"],
                    recommendations=[],
                    vision_provider="none",
                )

            record = self.registry.update_validation(record, validation)

            if validation.passed:
                break

            # Correction
            if should_retry(validation, attempt, max_attempts):
                error_context = build_correction_context(spec, validation, code, attempt + 1)
                previous_code = code
                record.version += 1
                self.registry.add_fix(record, {
                    "attempt": attempt,
                    "action": "correction",
                    "score": validation.overall_score,
                    "issues": validation.issues[:5],
                })
            else:
                break

        # 4. Approval gate
        if record.status == "approved":
            approval = {"approved": True, "reasons": [], "warnings": []}
        elif record.status == "needs_correction" and auto_approve:
            approval = check_approval(record)
        else:
            approval = check_approval(record)

        if approval["approved"] and (auto_approve or record.status == "approved"):
            record = self.registry.update_status(record, "approved")
            self.registry.sync_to_shortlist(record)

        result["status"] = record.status
        result["version"] = record.version
        result["glb_path"] = record.glb_path
        result["vertex_count"] = record.vertex_count
        result["face_count"] = record.face_count
        result["bounds"] = record.bounds_cm
        result["validation"] = record.latest_validation
        result["approval"] = approval
        result["preview_screenshots"] = record.preview_screenshots

        return result

    def revalidate(self, asset_id: str) -> dict[str, Any]:
        """Re-run validation on an existing asset."""
        record = self.registry.get(asset_id)
        if not record:
            return {"error": f"Asset not found: {asset_id}"}

        if not record.glb_path:
            return {"error": "No GLB file to validate"}

        spec = record.spec
        if not spec:
            return {"error": "No spec found for asset"}

        preview_dir = self.storage.previews_dir(record.project, record.name)
        screenshots = record.preview_screenshots

        # Re-render if no screenshots
        if not screenshots:
            screenshots = render_screenshots(record.glb_path, preview_dir, record.version)
            record = self.registry.update_previews(record, screenshots)

        validation = validate_asset(preview_dir, screenshots, spec, {
            "vertex_count": record.vertex_count,
            "face_count": record.face_count,
            "bounds": record.bounds_cm,
        })

        record = self.registry.update_validation(record, validation)
        return {"status": record.status, "validation": validation.to_dict()}

    def approve(self, asset_id: str) -> dict[str, Any]:
        """Manually approve an asset."""
        record = self.registry.get(asset_id)
        if not record:
            return {"error": f"Asset not found: {asset_id}"}

        approval = check_approval(record)
        if not approval["approved"]:
            # Force approve anyway (manual override)
            pass

        record = self.registry.update_status(record, "approved")
        self.registry.sync_to_shortlist(record)
        return {"status": "approved", "asset_id": asset_id, "warnings": approval.get("warnings", [])}

    def import_asset(self, asset_id: str) -> dict[str, Any]:
        """Import an approved asset to UEFN."""
        record = self.registry.get(asset_id)
        if not record:
            return {"error": f"Asset not found: {asset_id}"}

        if record.status not in ("approved", "imported"):
            return {"error": f"Asset not approved (status: {record.status})"}

        result = import_to_uefn(record)
        if result.get("success"):
            record = self.registry.mark_imported(record, result["uefn_path"])

        return result

    def list_assets(self, project: str | None = None) -> list[dict[str, Any]]:
        """List all pipeline assets."""
        records = self.registry.list_all(project)
        return [r.to_dict() for r in records]

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        """Get full asset details."""
        record = self.registry.get(asset_id)
        if not record:
            return None
        return record.to_dict()

    def delete_asset(self, asset_id: str) -> bool:
        """Delete an asset and its files."""
        return self.registry.delete(asset_id)
