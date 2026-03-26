"""Sandboxed execution of AI-generated trimesh code to produce GLB files."""

from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path
from typing import Any


def build_mesh(code: str, asset_name: str, export_dir: Path, version: int = 1) -> dict[str, Any]:
    """Execute trimesh code in a restricted namespace and export GLB.

    Args:
        code: Python source code that builds a trimesh.Scene.
        asset_name: Name for the exported file.
        export_dir: Directory to write the GLB file.
        version: Asset version number.

    Returns:
        Dict with keys: glb_path, vertex_count, face_count, bounds, success, error.
    """
    try:
        import trimesh
        import trimesh.transformations
        import trimesh.boolean
        import trimesh.creation
        import trimesh.util
        import numpy as np
        import math
    except ImportError as e:
        return {"success": False, "error": f"Missing dependency: {e}"}

    # Optional: shapely for extrusions
    try:
        import shapely
        import shapely.geometry
    except ImportError:
        shapely = None

    export_dir.mkdir(parents=True, exist_ok=True)

    # Allowed modules for the restricted __import__
    _allowed_modules = {
        "trimesh": trimesh,
        "trimesh.transformations": trimesh.transformations,
        "trimesh.boolean": trimesh.boolean,
        "trimesh.creation": trimesh.creation,
        "trimesh.util": trimesh.util,
        "numpy": np,
        "np": np,
        "math": math,
    }
    if shapely:
        _allowed_modules["shapely"] = shapely
        _allowed_modules["shapely.geometry"] = shapely.geometry

    def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        """Only allow importing pre-approved modules."""
        if name in _allowed_modules:
            mod = _allowed_modules[name]
            return mod
        # Check if it's a submodule of an allowed top-level
        top = name.split(".")[0]
        if top in ("trimesh", "numpy", "math") or (shapely and top == "shapely"):
            import importlib
            try:
                mod = importlib.import_module(name)
                _allowed_modules[name] = mod
                return mod
            except ImportError:
                pass
        raise ImportError(f"Import not allowed: {name}")

    # Build restricted namespace
    builtins = _safe_builtins()
    builtins["__import__"] = _restricted_import

    namespace: dict[str, Any] = {
        "trimesh": trimesh,
        "np": np,
        "numpy": np,
        "math": math,
        "__builtins__": builtins,
    }
    if shapely:
        namespace["shapely"] = shapely

    # Capture stdout/stderr from exec
    old_stdout, old_stderr = sys.stdout, sys.stderr
    captured_out = io.StringIO()
    sys.stdout = captured_out
    sys.stderr = captured_out

    try:
        exec(code, namespace)
    except Exception as e:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        tb = traceback.format_exc()
        return {
            "success": False,
            "error": f"Code execution failed: {e}",
            "traceback": tb,
            "output": captured_out.getvalue(),
        }
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    # Extract scene
    scene = namespace.get("scene")
    if scene is None:
        return {"success": False, "error": "Code did not define a 'scene' variable."}

    if not isinstance(scene, trimesh.Scene):
        # Maybe they returned a single mesh
        if isinstance(scene, trimesh.Trimesh):
            mesh = scene
            scene = trimesh.Scene()
            scene.add_geometry(mesh, node_name="main")
        else:
            return {"success": False, "error": f"'scene' is {type(scene).__name__}, expected trimesh.Scene."}

    # Validate scene has geometry
    if len(scene.geometry) == 0:
        return {"success": False, "error": "Scene has no geometry."}

    # Calculate stats
    total_vertices = 0
    total_faces = 0
    for geom in scene.geometry.values():
        if hasattr(geom, "vertices"):
            total_vertices += len(geom.vertices)
        if hasattr(geom, "faces"):
            total_faces += len(geom.faces)

    # Check vertex limit
    if total_vertices > 100_000:
        return {
            "success": False,
            "error": f"Too many vertices: {total_vertices} (limit 100,000).",
            "vertex_count": total_vertices,
        }

    # Calculate bounds
    try:
        bounds = scene.bounds
        bounds_dict = {
            "min": bounds[0].tolist(),
            "max": bounds[1].tolist(),
            "size": (bounds[1] - bounds[0]).tolist(),
        }
    except Exception:
        bounds_dict = {}

    # Export GLB
    glb_name = f"{asset_name}_v{version}.glb"
    glb_path = export_dir / glb_name

    try:
        scene.export(str(glb_path), file_type="glb")
    except Exception as e:
        # Fallback: try exporting as concatenated mesh
        try:
            combined = trimesh.util.concatenate(list(scene.geometry.values()))
            combined.export(str(glb_path), file_type="glb")
        except Exception as e2:
            return {
                "success": False,
                "error": f"GLB export failed: {e}. Fallback also failed: {e2}",
            }

    return {
        "success": True,
        "glb_path": str(glb_path),
        "glb_name": glb_name,
        "vertex_count": total_vertices,
        "face_count": total_faces,
        "bounds": bounds_dict,
        "geometry_count": len(scene.geometry),
        "output": captured_out.getvalue(),
    }


def _safe_builtins() -> dict[str, Any]:
    """Return a restricted set of builtins safe for mesh generation code."""
    import builtins

    allowed = [
        "abs", "all", "any", "bool", "bytes", "bytearray", "callable",
        "chr", "complex", "dict", "dir", "divmod", "enumerate",
        "filter", "float", "format", "frozenset", "getattr", "hasattr",
        "hash", "hex", "id", "int", "isinstance", "issubclass", "iter",
        "len", "list", "map", "max", "min", "next", "object", "oct",
        "ord", "pow", "print", "property", "range", "repr", "reversed",
        "round", "set", "slice", "sorted", "str", "sum", "super",
        "tuple", "type", "vars", "zip",
        "True", "False", "None",
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "RuntimeError", "StopIteration", "AttributeError", "ZeroDivisionError",
        "NotImplementedError", "OverflowError", "ArithmeticError",
        "__build_class__", "__name__",
    ]

    safe = {}
    for name in allowed:
        val = getattr(builtins, name, None)
        if val is not None:
            safe[name] = val

    return safe


def validate_code_safety(code: str) -> tuple[bool, str]:
    """Basic static check that code doesn't do anything dangerous.

    Returns (is_safe, reason).
    """
    # Allowed import targets — these are fine
    safe_imports = {"trimesh", "numpy", "np", "math", "shapely"}

    for line in code.split("\n"):
        stripped = line.strip()
        # Check import statements
        if stripped.startswith("import ") or stripped.startswith("from "):
            # Extract the top-level module name
            parts = stripped.replace("from ", "").replace("import ", "").split(".")
            top_module = parts[0].split()[0].strip(",")
            if top_module not in safe_imports:
                return False, f"Import not allowed: {top_module}"

    dangerous_patterns = [
        ("eval(", "eval not allowed"),
        ("exec(", "nested exec not allowed"),
        ("open(", "file I/O not allowed"),
        ("socket.", "network access not allowed"),
        ("subprocess", "subprocess not allowed"),
    ]

    for pattern, reason in dangerous_patterns:
        if pattern in code:
            return False, reason

    return True, "OK"
