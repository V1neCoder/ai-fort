"""Multi-angle screenshot renderer for 3D asset validation."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

CAMERA_ANGLES = [
    {"name": "front",         "azimuth": 0,   "elevation": 30},
    {"name": "back",          "azimuth": 180, "elevation": 30},
    {"name": "left",          "azimuth": 270, "elevation": 30},
    {"name": "right",         "azimuth": 90,  "elevation": 30},
    {"name": "top",           "azimuth": 0,   "elevation": 80},
    {"name": "perspective",   "azimuth": 45,  "elevation": 45},
    {"name": "three_quarter", "azimuth": 135, "elevation": 35},
    {"name": "detail",        "azimuth": 20,  "elevation": 15},
]


def render_screenshots(
    glb_path: Path | str,
    output_dir: Path | str,
    version: int = 1,
    resolution: tuple[int, int] = (800, 600),
    angles: list[dict] | None = None,
) -> list[str]:
    """Render multi-angle screenshots of a GLB file.

    Tries pyrender first (best quality), falls back to trimesh's built-in
    scene rendering if pyrender/OpenGL is unavailable.

    Args:
        glb_path: Path to the GLB file.
        output_dir: Directory to save PNG screenshots.
        version: Version number for filename prefix.
        resolution: (width, height) in pixels.
        angles: Camera angle definitions. Defaults to CAMERA_ANGLES.

    Returns:
        List of screenshot filenames (relative to output_dir).
    """
    glb_path = Path(glb_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    angles = angles or CAMERA_ANGLES

    # Try pyrender first
    try:
        return _render_pyrender(glb_path, output_dir, version, resolution, angles)
    except Exception:
        pass

    # Fallback to trimesh's built-in rendering
    try:
        return _render_trimesh(glb_path, output_dir, version, resolution, angles)
    except Exception:
        pass

    # Last resort: generate a single placeholder
    return _render_placeholder(glb_path, output_dir, version)


def _render_pyrender(
    glb_path: Path, output_dir: Path, version: int,
    resolution: tuple[int, int], angles: list[dict],
) -> list[str]:
    """Render using pyrender offscreen renderer."""
    import numpy as np
    import trimesh
    import pyrender
    from PIL import Image

    # Load the scene
    tm_scene = trimesh.load(str(glb_path))
    if isinstance(tm_scene, trimesh.Trimesh):
        s = trimesh.Scene()
        s.add_geometry(tm_scene, node_name="main")
        tm_scene = s

    pr_scene = pyrender.Scene.from_trimesh_scene(tm_scene)

    # Add ambient light
    pr_scene.ambient_light = np.array([0.3, 0.3, 0.3, 1.0])

    # Add directional light
    light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
    light_pose = np.eye(4)
    light_pose[:3, 3] = [0, 0, 500]
    pr_scene.add(light, pose=light_pose)

    # Calculate scene bounds for camera placement
    bounds = tm_scene.bounds
    center = (bounds[0] + bounds[1]) / 2
    size = np.linalg.norm(bounds[1] - bounds[0])
    distance = size * 1.8

    # Create camera
    camera = pyrender.PerspectiveCamera(yfov=math.radians(45))

    renderer = pyrender.OffscreenRenderer(*resolution)
    filenames = []

    try:
        for angle in angles:
            # Compute camera position
            az = math.radians(angle["azimuth"])
            el = math.radians(angle["elevation"])

            cam_x = center[0] + distance * math.cos(el) * math.sin(az)
            cam_y = center[1] + distance * math.cos(el) * math.cos(az)
            cam_z = center[2] + distance * math.sin(el)

            cam_pos = np.array([cam_x, cam_y, cam_z])

            # Look-at matrix
            pose = _look_at(cam_pos, center, np.array([0, 0, 1]))

            cam_node = pr_scene.add(camera, pose=pose)
            color, _ = renderer.render(pr_scene)
            pr_scene.remove_node(cam_node)

            fname = f"v{version}_{angle['name']}.png"
            Image.fromarray(color).save(str(output_dir / fname))
            filenames.append(fname)
    finally:
        renderer.delete()

    return filenames


def _render_trimesh(
    glb_path: Path, output_dir: Path, version: int,
    resolution: tuple[int, int], angles: list[dict],
) -> list[str]:
    """Fallback: render using trimesh's scene.save_image (requires pyglet)."""
    import trimesh
    import numpy as np
    from PIL import Image

    scene = trimesh.load(str(glb_path))
    if isinstance(scene, trimesh.Trimesh):
        s = trimesh.Scene()
        s.add_geometry(scene, node_name="main")
        scene = s

    bounds = scene.bounds
    center = (bounds[0] + bounds[1]) / 2
    size = np.linalg.norm(bounds[1] - bounds[0])
    distance = size * 1.8

    filenames = []
    for angle in angles:
        az = math.radians(angle["azimuth"])
        el = math.radians(angle["elevation"])

        cam_x = center[0] + distance * math.cos(el) * math.sin(az)
        cam_y = center[1] + distance * math.cos(el) * math.cos(az)
        cam_z = center[2] + distance * math.sin(el)

        cam_pos = np.array([cam_x, cam_y, cam_z])
        pose = _look_at(cam_pos, center, np.array([0, 0, 1]))

        scene.camera_transform = pose

        try:
            png_data = scene.save_image(resolution=resolution, visible=False)
            fname = f"v{version}_{angle['name']}.png"
            with open(output_dir / fname, "wb") as f:
                f.write(png_data)
            filenames.append(fname)
        except Exception:
            continue

    return filenames if filenames else _render_placeholder(glb_path, output_dir, version)


def _render_placeholder(glb_path: Path, output_dir: Path, version: int) -> list[str]:
    """Generate a simple placeholder image when rendering is unavailable."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return []

    img = Image.new("RGB", (800, 600), (40, 40, 45))
    draw = ImageDraw.Draw(img)

    # Draw info text
    text_lines = [
        f"3D Preview Unavailable",
        f"Asset: {glb_path.stem}",
        f"Install pyrender for 3D screenshots",
        f"GLB file available for model-viewer",
    ]
    y = 200
    for line in text_lines:
        try:
            draw.text((200, y), line, fill=(200, 200, 200))
        except Exception:
            pass
        y += 40

    fname = f"v{version}_placeholder.png"
    img.save(str(output_dir / fname))
    return [fname]


def _look_at(eye: Any, target: Any, up: Any) -> Any:
    """Compute a 4x4 camera look-at matrix."""
    import numpy as np

    forward = target - eye
    forward = forward / np.linalg.norm(forward)

    right = np.cross(forward, up)
    norm = np.linalg.norm(right)
    if norm < 1e-6:
        right = np.array([1.0, 0.0, 0.0])
    else:
        right = right / norm

    true_up = np.cross(right, forward)
    true_up = true_up / np.linalg.norm(true_up)

    mat = np.eye(4)
    mat[:3, 0] = right
    mat[:3, 1] = true_up
    mat[:3, 2] = -forward
    mat[:3, 3] = eye

    return mat
