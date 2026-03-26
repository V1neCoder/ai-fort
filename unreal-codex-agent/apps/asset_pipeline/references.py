"""Reference image management — upload, store, analyze, and use as generation context."""

from __future__ import annotations

import base64
import shutil
from pathlib import Path
from typing import Any

from .models import AssetRecord
from .registry import AssetRegistry
from .ai_client import vision_analyze, detect_vision_provider


def save_reference(
    asset_id: str,
    image_data: bytes,
    filename: str,
    registry: AssetRegistry,
) -> dict[str, Any]:
    """Save a reference image for an asset.

    Args:
        asset_id: The asset to attach reference to.
        image_data: Raw image bytes.
        filename: Original filename.
        registry: The asset registry.

    Returns:
        Dict with success status and saved path.
    """
    record = registry.get(asset_id)
    if not record:
        return {"success": False, "error": f"Asset not found: {asset_id}"}

    # Create references directory
    ref_dir = registry.storage.base_dir / record.project / record.name / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")
    if not safe_name:
        safe_name = "reference.png"

    # Avoid overwriting
    dest = ref_dir / safe_name
    counter = 1
    while dest.exists():
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix or ".png"
        dest = ref_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    dest.write_bytes(image_data)

    # Update record
    if not hasattr(record, "reference_images") or record.reference_images is None:
        record.reference_images = []
    record.reference_images.append(str(dest.name))
    registry.update(record)

    return {
        "success": True,
        "filename": dest.name,
        "path": str(dest),
        "total_references": len(record.reference_images),
    }


def list_references(
    asset_id: str,
    registry: AssetRegistry,
) -> dict[str, Any]:
    """List all reference images for an asset."""
    record = registry.get(asset_id)
    if not record:
        return {"error": f"Asset not found: {asset_id}"}

    ref_dir = registry.storage.base_dir / record.project / record.name / "references"
    if not ref_dir.exists():
        return {"references": []}

    refs = []
    for f in sorted(ref_dir.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            refs.append({
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
            })

    return {"references": refs}


def delete_reference(
    asset_id: str,
    filename: str,
    registry: AssetRegistry,
) -> dict[str, Any]:
    """Delete a reference image."""
    record = registry.get(asset_id)
    if not record:
        return {"success": False, "error": f"Asset not found: {asset_id}"}

    ref_dir = registry.storage.base_dir / record.project / record.name / "references"
    target = ref_dir / filename
    if not target.exists():
        return {"success": False, "error": f"Reference not found: {filename}"}

    target.unlink()

    # Update record
    if record.reference_images and filename in record.reference_images:
        record.reference_images.remove(filename)
        registry.update(record)

    return {"success": True, "filename": filename}


def analyze_references(
    asset_id: str,
    registry: AssetRegistry,
) -> dict[str, Any]:
    """Use vision AI to analyze reference images and extract style/structure notes.

    Returns descriptions that can be fed into the code generator as context.
    """
    record = registry.get(asset_id)
    if not record:
        return {"error": f"Asset not found: {asset_id}"}

    provider, _ = detect_vision_provider()
    if not provider:
        return {"error": "No vision provider available. Set GEMINI_API_KEY."}

    ref_dir = registry.storage.base_dir / record.project / record.name / "references"
    if not ref_dir.exists():
        return {"error": "No references directory found."}

    image_paths = []
    for f in sorted(ref_dir.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            image_paths.append(str(f))

    if not image_paths:
        return {"error": "No reference images found."}

    prompt = f"""Analyze these reference images for a 3D model generation task.
The target asset is: "{record.prompt}" (category: {record.category})

For each image, describe:
1. Key shapes and geometry (what primitives would build this?)
2. Color palette (list specific colors)
3. Proportions and relative scale of parts
4. Important structural details
5. Style (realistic, stylized, low-poly, etc.)

Then provide a combined summary that a 3D code generator should use.

Respond as JSON:
{{"per_image": [{{"description": "...", "colors": ["#hex", ...], "shapes": ["..."]}}], "combined_guidance": "..."}}"""

    try:
        response = vision_analyze(prompt, image_paths[:4])
    except Exception as e:
        return {"error": f"Vision analysis failed: {e}"}

    import json
    import re

    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {
                "analysis": data,
                "image_count": len(image_paths[:4]),
            }
        except json.JSONDecodeError:
            pass

    return {
        "analysis": {"combined_guidance": response.strip()},
        "image_count": len(image_paths[:4]),
    }


def build_reference_context(
    asset_id: str,
    registry: AssetRegistry,
) -> str:
    """Build a text context string from reference analysis for the code generator.

    Returns empty string if no references or analysis fails.
    """
    result = analyze_references(asset_id, registry)
    if "error" in result:
        return ""

    analysis = result.get("analysis", {})
    guidance = analysis.get("combined_guidance", "")
    if not guidance:
        return ""

    return f"\n\nREFERENCE IMAGE GUIDANCE:\n{guidance}\nUse these visual cues to match the style, colors, and proportions described above."
