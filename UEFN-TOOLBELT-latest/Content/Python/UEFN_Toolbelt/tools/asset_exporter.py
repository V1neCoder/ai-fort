"""
UEFN TOOLBELT — Asset Exporter v5.3 Integration
================================================
Wrapper registering the standalone asset exporter/importer as Toolbelt tools.

Four registered tools:
  1. asset_exporter_open       — Launch full tkinter GUI
  2. asset_exporter_scan       — Headless project scan → asset catalog dict
  3. asset_exporter_export     — Headless export: assets + dependencies to disk
  4. asset_exporter_import     — Headless import: bundle → target project Content/
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

from ..registry import register_tool


# ─────────────────────────────────────────────────────────────────────
# TOOL 1: Open the Full GUI
# ─────────────────────────────────────────────────────────────────────

@register_tool(
    name="asset_exporter_open",
    category="Assets",
    description="Open the UEFN Asset Exporter/Importer v5.3 — interactive GUI with 5 tabs: Export, Paste Export, Import, Organize, Log. Scan projects, filter assets by category/folder/search, resolve dependency chains, and export/import asset bundles.",
    tags=["asset", "export", "import", "dependency", "migrate", "bundle"],
    version="5.3.0",
    author="Community (integrated with Toolbelt)",
    shortcut="",
)
def asset_exporter_open(**kwargs) -> dict:
    """Launch the tkinter Asset Exporter application."""
    try:
        from .asset_exporter_ui import App
        App().run()
        return {"status": "ok", "message": "Asset Exporter v5.3 launched"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────
# TOOL 2: Headless Scan
# ─────────────────────────────────────────────────────────────────────

@register_tool(
    name="asset_exporter_scan",
    category="Assets",
    description="Scan a UEFN project folder without opening the UI. Returns categorized asset catalog: project name, asset counts by category, full asset list with metadata.",
    tags=["asset", "scan", "catalog"],
    version="5.3.0",
)
def asset_exporter_scan(source_path: str = "", **kwargs) -> dict:
    """
    Scan a UEFN project folder and return a categorized asset catalog.

    Args:
        source_path (str): Path to the UEFN project folder (e.g. "C:/MyProject").
                          Auto-detected if empty.

    Returns:
        dict with keys:
          - status: "ok" or "error"
          - project: detected project name
          - total: total asset count
          - by_category: dict of {category: count}
          - assets: list of asset dicts with stem, full_path, category, ext, rel_path, size_mb
    """
    try:
        from .asset_exporter_ui import ProjectScanner

        path = Path(source_path) if source_path else Path.cwd()
        scanner = ProjectScanner(path)
        scanner.scan()

        return {
            "status": "ok",
            "project": scanner.project_name,
            "total": len(scanner.all_entries),
            "by_category": dict(scanner.category_counts),
            "assets": scanner.all_entries,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────
# TOOL 3: Headless Export
# ─────────────────────────────────────────────────────────────────────

@register_tool(
    name="asset_exporter_export",
    category="Assets",
    description="Headless export of selected assets from a project to a timestamped export folder on disk. Optionally resolves and includes all dependencies (meshes, materials, textures). Generates export_manifest.json.",
    tags=["asset", "export", "dependency"],
    version="5.3.0",
)
def asset_exporter_export(
    source_path: str = "",
    asset_stems: List[str] = None,
    export_dir: str = "",
    resolve_deps: bool = True,
    **kwargs,
) -> dict:
    """
    Export selected assets to a folder with optional dependency resolution.

    Args:
        source_path (str): Path to UEFN project to scan.
        asset_stems (list): List of asset stem names to export (e.g. ["SM_Door", "MI_Metal"]).
                           If empty, exports all assets in the project.
        export_dir (str): Base export folder. Default: Saved/UEFN_Toolbelt/
        resolve_deps (bool): If True, includes all mesh/material/texture dependencies.

    Returns:
        dict with keys:
          - status: "ok" or "error"
          - exported_count: number of assets exported
          - export_folder: path to the created export folder
          - category_breakdown: dict of {category: count}
          - manifest: export_manifest.json content
    """
    try:
        from .asset_exporter_ui import ProjectScanner, AssetExporter, DependencyResolver

        source = Path(source_path) if source_path else Path.cwd()
        dest = Path(export_dir) if export_dir else Path("Saved/UEFN_Toolbelt")

        # Scan
        scanner = ProjectScanner(source)
        scanner.scan()

        # Filter
        stems = asset_stems or []
        if stems:
            selected = [e for e in scanner.all_entries if e.get("stem") in stems]
        else:
            selected = scanner.all_entries

        # Export
        resolver = DependencyResolver(scanner) if resolve_deps else None
        exporter = AssetExporter(dest, resolver)
        result = exporter.export(selected, resolve=resolve_deps)

        return {
            "status": "ok",
            "exported_count": len(selected),
            "export_folder": str(result.get("export_folder", dest)),
            "category_breakdown": result.get("category_counts", {}),
            "manifest": result.get("manifest", {}),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────
# TOOL 4: Headless Import
# ─────────────────────────────────────────────────────────────────────

@register_tool(
    name="asset_exporter_import",
    category="Assets",
    description="Import an asset export bundle into a target UEFN project. Reads the bundle's export_manifest.json and copies all assets into Content/ImportedAssets/<Category>/ of the target project.",
    tags=["asset", "import", "bundle"],
    version="5.3.0",
)
def asset_exporter_import(
    bundle_path: str = "",
    target_path: str = "",
    **kwargs,
) -> dict:
    """
    Import an export bundle into a target UEFN project.

    Args:
        bundle_path (str): Path to the export bundle folder (containing export_manifest.json).
        target_path (str): Path to the target UEFN project.

    Returns:
        dict with keys:
          - status: "ok" or "error"
          - imported_count: number of files copied
          - target_folder: where assets were copied to
    """
    try:
        from .asset_exporter_ui import AssetImporter

        bundle = Path(bundle_path) if bundle_path else Path.cwd()
        target = Path(target_path) if target_path else Path.cwd()

        importer = AssetImporter(bundle, target)
        result = importer.run()

        return {
            "status": "ok",
            "imported_count": result.get("imported_count", 0),
            "target_folder": str(target / "Content" / "ImportedAssets"),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
