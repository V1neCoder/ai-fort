"""UEFN import via MCP bridge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# UEFN Content Browser category paths
CATEGORY_PATHS = {
    "furniture": "/Game/Generated/Props/Furniture/",
    "architecture": "/Game/Generated/Buildings/",
    "terrain": "/Game/Generated/Terrain/",
    "prop": "/Game/Generated/Props/",
    "vegetation": "/Game/Generated/Foliage/",
    "vehicle": "/Game/Generated/Vehicles/",
}


def import_to_uefn(
    record: Any,
    mcp_url: str = "http://127.0.0.1:8765",
) -> dict[str, Any]:
    """Import an approved asset to UEFN via the MCP bridge.

    Args:
        record: AssetRecord with glb_path, name, category.
        mcp_url: URL of the MCP bridge HTTP listener.

    Returns:
        Dict with keys: success, uefn_path, error.
    """
    if not record.glb_path or not Path(record.glb_path).exists():
        return {"success": False, "error": f"GLB file not found: {record.glb_path}"}

    target_path = CATEGORY_PATHS.get(record.category, "/Game/Generated/Props/")
    uefn_path = f"{target_path}{record.name}"

    # Build MCP command matching UEFN Toolbelt bridge protocol
    command = {
        "command": "import_asset",
        "params": {
            "source_file": str(Path(record.glb_path).resolve()),
            "destination_path": uefn_path,
            "replace_existing": True,
            "save": True,
        },
    }

    try:
        import urllib.request

        body = json.dumps(command).encode()
        req = urllib.request.Request(
            mcp_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())

        if result.get("success") or result.get("status") == "ok":
            return {"success": True, "uefn_path": uefn_path}
        else:
            return {
                "success": False,
                "uefn_path": uefn_path,
                "error": result.get("error", "Unknown MCP error"),
            }

    except Exception as e:
        return {
            "success": False,
            "uefn_path": uefn_path,
            "error": f"MCP bridge unavailable: {e}. "
                     f"Ensure UEFN editor is running with MCP bridge active at {mcp_url}",
        }
