"""AI-powered trimesh code generation for 3D assets."""

from __future__ import annotations

import re
from typing import Any

from .models import AssetSpec
from .ai_client import chat
from .trimesh_reference import TRIMESH_API_REFERENCE, CATEGORY_EXAMPLES


SYSTEM_PROMPT = f"""You are a 3D mesh construction expert. Given an asset specification,
write Python code using the trimesh library to build the 3D model.

{TRIMESH_API_REFERENCE}

IMPORTANT RULES:
- Output ONLY valid Python code. No markdown, no explanation, no comments outside code.
- Your code MUST define a variable called `scene` (trimesh.Scene).
- Only import: trimesh, numpy (as np), math — nothing else.
- All dimensions in CENTIMETERS.
- Color every mesh — no default gray.
- Keep total vertex count under 50,000.
- Center the asset at origin, sitting on the XY plane (Z up).
- Use scene.add_geometry() to add named parts.
- Wrap boolean operations in try/except with a fallback.
- Call mesh.fix_normals() on custom vertex/face meshes.
"""


def generate_code(spec: AssetSpec, attempt: int = 1,
                  previous_code: str = "", error_context: str = "",
                  placement_context: str = "", reference_context: str = "") -> str:
    """Generate trimesh Python code for the given asset spec.

    Args:
        spec: The parsed asset specification.
        attempt: Current attempt number (1-based).
        previous_code: Code from previous attempt (for corrections).
        error_context: Error or validation feedback from previous attempt.
        placement_context: Scene context from MCP (where the model will be placed).
        reference_context: Analysis of reference images.

    Returns:
        Python source code string that builds a trimesh.Scene.
    """
    # Build the user prompt
    parts = [f"Create a 3D model of: {spec.prompt}"]
    parts.append(f"\nCategory: {spec.category}")

    if spec.required_components:
        parts.append(f"Required components: {', '.join(spec.required_components)}")

    if spec.scale_range_cm:
        sr = spec.scale_range_cm
        parts.append(
            f"Target dimensions (cm): "
            f"width {sr.get('min_width', 0)}-{sr.get('max_width', 0)}, "
            f"height {sr.get('min_height', 0)}-{sr.get('max_height', 0)}, "
            f"depth {sr.get('min_depth', 0)}-{sr.get('max_depth', 0)}"
        )

    if spec.interior_required:
        parts.append("IMPORTANT: This asset requires a hollow interior (use boolean difference).")

    if spec.style:
        parts.append(f"Visual style: {spec.style}")

    if spec.color_palette:
        parts.append(f"Color palette: {', '.join(spec.color_palette)}")

    if spec.expected_silhouette:
        parts.append(f"Expected silhouette: {spec.expected_silhouette}")

    if spec.failure_conditions:
        parts.append(f"Avoid these issues: {'; '.join(spec.failure_conditions)}")

    # Add category example if available
    example = CATEGORY_EXAMPLES.get(spec.category)
    if example:
        parts.append(f"\nHere is an example of good {spec.category} code for reference:\n```python{example}```")

    # Correction context for retry attempts
    if attempt > 1 and previous_code:
        parts.append("\n--- CORRECTION ATTEMPT ---")
        parts.append(f"Attempt #{attempt}. The previous code had problems.")
        if error_context:
            parts.append(f"Issues found:\n{error_context}")
        parts.append(f"\nPrevious code:\n```python\n{previous_code}\n```")
        parts.append("\nFix the issues above and generate improved code. "
                      "Make sure the asset is more detailed and correct.")

    # Add placement context (scene awareness)
    if placement_context:
        parts.append(f"\n{placement_context}")

    # Add reference image analysis
    if reference_context:
        parts.append(f"\n{reference_context}")

    user_msg = "\n".join(parts)

    # Call the free AI
    raw = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.4 if attempt == 1 else 0.6,
        max_tokens=4096,
    )

    return _extract_code(raw)


def _extract_code(response: str) -> str:
    """Extract Python code from AI response, stripping markdown fences."""
    # Try to find code in markdown blocks
    match = re.search(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
    if match:
        code = match.group(1).strip()
    else:
        # Assume entire response is code
        code = response.strip()

    # Remove any leading markdown or explanation lines before imports
    lines = code.split("\n")
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ", "#")):
            start = i
            break
    code = "\n".join(lines[start:])

    # Validate it has required elements
    if "scene" not in code:
        # Wrap in a minimal scene if the AI forgot
        code += "\n\n# Ensure scene exists\nif 'scene' not in dir():\n    scene = trimesh.Scene()\n"

    return code
