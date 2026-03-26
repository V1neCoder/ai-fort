"""AI-powered model editing — targeted modifications to existing assets."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from .models import AssetRecord
from .registry import AssetRegistry
from .ai_client import chat, vision_analyze, detect_vision_provider
from .code_generator import generate_code, _extract_code
from .mesh_builder import build_mesh, validate_code_safety
from .preview import render_screenshots
from .validator import validate_asset
from .trimesh_reference import TRIMESH_API_REFERENCE


def edit_asset(
    asset_id: str,
    edit_prompt: str,
    registry: AssetRegistry,
) -> dict[str, Any]:
    """Apply an AI-directed edit to an existing asset.

    Args:
        asset_id: The asset to edit.
        edit_prompt: Natural language edit instruction.
        registry: The asset registry.

    Returns:
        Dict with success status, updated asset info.
    """
    record = registry.get(asset_id)
    if not record:
        return {"success": False, "error": f"Asset not found: {asset_id}"}

    # Get the existing code
    previous_code = record.generated_code or ""
    if not previous_code:
        return {"success": False, "error": "No generated code found for this asset — cannot edit."}

    # Build edit prompt for AI
    system_msg = f"""You are a 3D mesh editing expert. Given existing trimesh Python code and an edit instruction,
modify the code to apply the requested change.

{TRIMESH_API_REFERENCE}

IMPORTANT:
- Keep all existing geometry that isn't being changed.
- Only modify what the user asked to change.
- The code MUST define a variable called `scene` (trimesh.Scene).
- Only import: trimesh, numpy (as np), math.
- Color every mesh — no default gray.
- Output ONLY valid Python code. No markdown, no explanation."""

    user_msg = f"""Here is the current code for asset "{record.name}" ({record.category}):

```python
{previous_code}
```

Edit instruction: {edit_prompt}

Apply this edit and output the complete updated code."""

    try:
        raw = chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.4,
            max_tokens=4096,
        )
        new_code = _extract_code(raw)
    except Exception as e:
        return {"success": False, "error": f"AI edit failed: {e}"}

    # Safety check
    is_safe, reason = validate_code_safety(new_code)
    if not is_safe:
        return {"success": False, "error": f"Unsafe code: {reason}"}

    # Build new mesh
    record.version += 1
    export_dir = registry.storage.exports_dir(record.project, record.name)
    build_result = build_mesh(new_code, record.name, export_dir, record.version)

    if not build_result.get("success"):
        return {"success": False, "error": f"Build failed: {build_result.get('error')}"}

    # Update record
    record = registry.update_generation(
        record,
        glb_path=build_result["glb_path"],
        code=new_code,
        provider="free_ai_edit",
        vertex_count=build_result.get("vertex_count", 0),
        face_count=build_result.get("face_count", 0),
        bounds=build_result.get("bounds"),
    )

    # Render previews
    preview_dir = registry.storage.previews_dir(record.project, record.name)
    try:
        screenshots = render_screenshots(build_result["glb_path"], preview_dir, record.version)
        record = registry.update_previews(record, screenshots)
    except Exception:
        screenshots = []

    # Add to fix history
    registry.add_fix(record, {
        "action": "edit",
        "edit_prompt": edit_prompt,
        "version": record.version,
    })

    return {
        "success": True,
        "asset_id": asset_id,
        "version": record.version,
        "glb_path": build_result["glb_path"],
        "vertex_count": build_result.get("vertex_count", 0),
        "face_count": build_result.get("face_count", 0),
    }


def detect_problems(
    asset_id: str,
    registry: AssetRegistry,
) -> dict[str, Any]:
    """Use vision AI to detect structural problems in a model."""
    record = registry.get(asset_id)
    if not record:
        return {"error": f"Asset not found: {asset_id}"}

    provider, _ = detect_vision_provider()
    if not provider:
        return {"error": "No vision provider available. Set GEMINI_API_KEY."}

    # Collect preview screenshots
    preview_dir = registry.storage.previews_dir(record.project, record.name)
    image_paths = []
    for name in (record.preview_screenshots or []):
        p = preview_dir / name
        if p.exists():
            image_paths.append(str(p))

    if not image_paths:
        return {"error": "No preview screenshots available for analysis."}

    prompt = f"""Analyze these screenshots of a 3D model that should be: "{record.prompt}"
Category: {record.category}

List ALL structural problems you can see:
- Floating or disconnected parts
- Missing components
- Wrong proportions or scale
- Bad geometry (clipping, overlapping)
- Shape doesn't match the description
- Missing colors or textures
- Unrealistic features

Respond as JSON:
{{"problems": ["problem 1", "problem 2", ...], "severity": "low|medium|high", "fixable": true|false}}"""

    try:
        response = vision_analyze(prompt, image_paths[:4])
    except Exception as e:
        return {"error": f"Vision analysis failed: {e}"}

    import json, re
    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {"problems": data.get("problems", []), "severity": data.get("severity", "unknown"), "fixable": data.get("fixable", True)}
        except json.JSONDecodeError:
            pass

    return {"problems": [response.strip()], "severity": "unknown", "fixable": True}


def suggest_fixes(
    asset_id: str,
    problems: list[str],
    registry: AssetRegistry,
) -> dict[str, Any]:
    """Generate actionable fix suggestions for detected problems."""
    record = registry.get(asset_id)
    if not record:
        return {"error": f"Asset not found: {asset_id}"}

    problem_text = "\n".join(f"- {p}" for p in problems)

    prompt = f"""Given a 3D model of "{record.prompt}" ({record.category}) with these problems:
{problem_text}

Suggest specific, actionable edit commands that could fix each problem.
Each suggestion should be a short instruction I can give to an AI editor.

Respond as JSON:
{{"fixes": [{{"problem": "...", "fix_command": "..."}}]}}"""

    try:
        raw = chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )
    except Exception as e:
        return {"error": f"AI suggestion failed: {e}"}

    import json, re
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {"fixes": data.get("fixes", [])}
        except json.JSONDecodeError:
            pass

    return {"fixes": [{"problem": "general", "fix_command": raw.strip()}]}
