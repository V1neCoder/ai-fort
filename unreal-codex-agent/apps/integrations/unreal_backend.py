from __future__ import annotations

"""Compatibility shim.

The repo is now UEFN-first, but several local modules still import
``apps.integrations.unreal_backend``. Re-export the UEFN runtime helpers so
the older import path keeps working while the architecture migrates.
"""

from apps.integrations.uefn_backend import (  # noqa: F401
    backend_settings,
    backend_summary,
    capture_import_root,
    choose_action_backend,
    choose_capture_backend,
    choose_scene_backend,
    latest_scene_state_export_path,
    uefn_project_available,
    verse_generated_root,
    verse_workspace_available,
)
