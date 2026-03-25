from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def backend_settings(repo_root: Path) -> dict[str, Any]:
    project = _load_json(repo_root / "config" / "project.json")
    env_values = _load_env_file(repo_root / ".env")
    example_values = _load_env_file(repo_root / ".env.example")

    def get_env(key: str, default: str = "") -> str:
        return env_values.get(key) or example_values.get(key) or default

    integrations = project.get("integrations", {})
    capture = project.get("capture", {})
    scene_state = project.get("scene_state", {})
    verse = project.get("verse", {})
    uefn = project.get("uefn", {})
    uefn_mcp = integrations.get("uefn_mcp", {})
    uefn_toolbelt = integrations.get("uefn_toolbelt", {})

    uefn_project_path = get_env("UEFN_PROJECT_PATH", get_env("UNREAL_PROJECT_PATH", ""))
    verse_root = get_env("UEFN_VERSE_PATH", str(repo_root / uefn.get("verse_root", "uefn/verse")))
    generated_root = get_env("UEFN_VERSE_GENERATED_PATH", str(repo_root / uefn.get("generated_root", "uefn/verse/generated")))
    export_root = get_env("UEFN_EXPORT_ROOT", str(repo_root / uefn.get("export_root", "data/uefn_bridge")))
    latest_scene_state_path = get_env(
        "UEFN_SCENE_STATE_EXPORT",
        str(Path(export_root) / "latest_scene_state.json"),
    )
    capture_import_dir = get_env(
        "UEFN_CAPTURE_IMPORT_DIR",
        str(Path(export_root) / "captures"),
    )

    return {
        "preferred_runtime": get_env("PREFERRED_RUNTIME", integrations.get("preferred_runtime", "uefn_verse")),
        "preferred_bridge": get_env("PREFERRED_BRIDGE", integrations.get("preferred_bridge", "uefn_verse")),
        "scene_backend": scene_state.get("backend", get_env("SCENE_STATE_BACKEND", "uefn_session_export")),
        "capture_backend": capture.get("backend", get_env("CAPTURE_BACKEND", "auto")),
        "action_backend": verse.get("action_backend", get_env("UEFN_ACTION_BACKEND", "uefn_verse_apply")),
        "auto_select_after_apply": _parse_bool(get_env("UEFN_AUTO_SELECT_AFTER_APPLY", verse.get("auto_select_after_apply", False)), False),
        "auto_focus_after_apply": _parse_bool(get_env("UEFN_AUTO_FOCUS_AFTER_APPLY", verse.get("auto_focus_after_apply", False)), False),
        "auto_optimize_floor_orientation": _parse_bool(get_env("UEFN_AUTO_OPTIMIZE_FLOOR_ORIENTATION", verse.get("auto_optimize_floor_orientation", True)), True),
        "uefn_project_path": uefn_project_path,
        "uefn_editor_path": get_env("UEFN_EDITOR_PATH", ""),
        "verse_root": verse_root,
        "generated_root": generated_root,
        "export_root": export_root,
        "latest_scene_state_path": latest_scene_state_path,
        "capture_import_dir": capture_import_dir,
        "scene_graph_enabled": bool(uefn.get("scene_graph_enabled", True)),
        "fortnite_devices_enabled": bool(uefn.get("fortnite_devices_enabled", True)),
        "creative_devices_enabled": bool(uefn.get("creative_devices_enabled", True)),
        "scene_graph_beta": bool(uefn.get("scene_graph_beta", True)),
        "uefn_mcp_enabled": _parse_bool(get_env("UEFN_MCP_ENABLED", uefn_mcp.get("enabled", False)), False),
        "uefn_mcp_port": _parse_int(get_env("UEFN_MCP_PORT", uefn_mcp.get("default_port", 8765)), 8765),
        "uefn_mcp_max_port": _parse_int(get_env("UEFN_MCP_MAX_PORT", uefn_mcp.get("max_port", 8770)), 8770),
        "uefn_mcp_repo_path": get_env("UEFN_MCP_REPO_PATH", str(repo_root / uefn_mcp.get("vendor_root", "vendor/uefn-mcp-server"))),
        "uefn_mcp_server_path": get_env("UEFN_MCP_SERVER_PATH", str(repo_root / uefn_mcp.get("server_script", "vendor/uefn-mcp-server/mcp_server.py"))),
        "uefn_mcp_listener_path": get_env("UEFN_MCP_LISTENER_PATH", str(repo_root / uefn_mcp.get("listener_script", "vendor/uefn-mcp-server/uefn_listener.py"))),
        "uefn_mcp_init_path": get_env("UEFN_MCP_INIT_PATH", str(repo_root / uefn_mcp.get("init_script", "vendor/uefn-mcp-server/init_unreal.py"))),
        "uefn_mcp_client_config_path": get_env("UEFN_MCP_CLIENT_CONFIG_PATH", str(repo_root / uefn_mcp.get("client_config_path", ".mcp.json"))),
        "uefn_toolbelt_enabled": _parse_bool(get_env("UEFN_TOOLBELT_ENABLED", uefn_toolbelt.get("enabled", True)), True),
        "uefn_toolbelt_repo_path": get_env("UEFN_TOOLBELT_REPO_PATH", str(repo_root / uefn_toolbelt.get("vendor_root", "vendor/uefn-toolbelt"))),
        "uefn_toolbelt_python_root": get_env(
            "UEFN_TOOLBELT_PYTHON_ROOT",
            str(repo_root / uefn_toolbelt.get("python_root", "vendor/uefn-toolbelt/Content/Python")),
        ),
        "uefn_toolbelt_package_path": get_env(
            "UEFN_TOOLBELT_PACKAGE_PATH",
            str(repo_root / uefn_toolbelt.get("package_root", "vendor/uefn-toolbelt/Content/Python/UEFN_Toolbelt")),
        ),
        "uefn_toolbelt_init_path": get_env(
            "UEFN_TOOLBELT_INIT_PATH",
            str(repo_root / uefn_toolbelt.get("init_script", "vendor/uefn-toolbelt/init_unreal.py")),
        ),
        "uefn_toolbelt_mcp_server_path": get_env(
            "UEFN_TOOLBELT_MCP_SERVER_PATH",
            str(repo_root / uefn_toolbelt.get("mcp_server_script", "vendor/uefn-toolbelt/mcp_server.py")),
        ),
        "uefn_toolbelt_client_path": get_env(
            "UEFN_TOOLBELT_CLIENT_PATH",
            str(repo_root / uefn_toolbelt.get("client_script", "vendor/uefn-toolbelt/client.py")),
        ),
        "uefn_toolbelt_launcher_path": get_env(
            "UEFN_TOOLBELT_LAUNCHER_PATH",
            str(repo_root / uefn_toolbelt.get("launcher_script", "vendor/uefn-toolbelt/launcher.py")),
        ),
        "uefn_toolbelt_docs_root": get_env(
            "UEFN_TOOLBELT_DOCS_ROOT",
            str(repo_root / uefn_toolbelt.get("docs_root", "vendor/uefn-toolbelt/docs")),
        ),
    }


def uefn_project_available(repo_root: Path) -> bool:
    project_path = str(backend_settings(repo_root).get("uefn_project_path", "")).strip()
    if not project_path:
        return False
    path = Path(project_path)
    if not path.exists():
        return False
    return path.suffix.lower() == ".uefnproject"


def uefn_project_root(repo_root: Path) -> Path | None:
    project_path = str(backend_settings(repo_root).get("uefn_project_path", "")).strip()
    if not project_path:
        return None
    path = Path(project_path)
    if not path.exists():
        return None
    return path.parent


def uefn_content_root(repo_root: Path) -> Path | None:
    project_root = uefn_project_root(repo_root)
    if project_root is None:
        return None
    content_root = project_root / "Content"
    if content_root.exists():
        return content_root
    return None


def verse_workspace_available(repo_root: Path) -> bool:
    settings = backend_settings(repo_root)
    verse_root = Path(str(settings.get("verse_root", "")).strip() or (repo_root / "uefn" / "verse"))
    generated_root = Path(str(settings.get("generated_root", "")).strip() or (repo_root / "uefn" / "verse" / "generated"))
    return verse_root.exists() or generated_root.exists()


def latest_scene_state_export_path(repo_root: Path) -> Path:
    settings = backend_settings(repo_root)
    return Path(str(settings.get("latest_scene_state_path", repo_root / "data" / "uefn_bridge" / "latest_scene_state.json")))


def capture_import_root(repo_root: Path) -> Path:
    settings = backend_settings(repo_root)
    return Path(str(settings.get("capture_import_dir", repo_root / "data" / "uefn_bridge" / "captures")))


def verse_generated_root(repo_root: Path) -> Path:
    settings = backend_settings(repo_root)
    return Path(str(settings.get("generated_root", repo_root / "uefn" / "verse" / "generated")))


def choose_scene_backend(repo_root: Path) -> str:
    settings = backend_settings(repo_root)
    preferred = str(settings.get("scene_backend", "uefn_session_export")).lower()
    if preferred == "fallback":
        return "fallback"
    if preferred in {"uefn_mcp", "auto"} and bool(settings.get("uefn_mcp_enabled", False)):
        try:
            from apps.integrations.uefn_mcp import mcp_listener_running

            if mcp_listener_running(repo_root):
                return "uefn_mcp"
        except Exception:
            pass
    if preferred in {"uefn_session_export", "auto", "uefn_mcp"}:
        if latest_scene_state_export_path(repo_root).exists():
            return "uefn_session_export"
        return "fallback"
    return "fallback"


def choose_capture_backend(repo_root: Path) -> str:
    settings = backend_settings(repo_root)
    preferred = str(settings.get("capture_backend", "auto")).lower()
    if preferred == "placeholder":
        return "placeholder"
    if preferred in {"uefn_viewport_reference", "uefn_capture_import"}:
        return preferred if capture_import_root(repo_root).exists() else "placeholder"
    if preferred == "auto":
        if capture_import_root(repo_root).exists():
            return "uefn_capture_import"
        return "placeholder"
    return preferred or "placeholder"


def choose_action_backend(repo_root: Path) -> str:
    settings = backend_settings(repo_root)
    preferred = str(settings.get("action_backend", "auto")).lower()
    if preferred == "plan_only":
        return "plan_only"
    if preferred in {"auto", "uefn_mcp_apply"} and bool(settings.get("uefn_mcp_enabled", False)):
        try:
            from apps.integrations.uefn_mcp import mcp_listener_running

            if mcp_listener_running(repo_root):
                return "uefn_mcp_apply"
        except Exception:
            pass
    if preferred in {"auto", "uefn_verse_apply", "verse_device_export", "uefn_mcp_apply"}:
        return "uefn_verse_apply" if verse_workspace_available(repo_root) else "plan_only"
    return preferred or "plan_only"


def backend_summary(repo_root: Path) -> dict[str, Any]:
    settings = backend_settings(repo_root)
    content_root = uefn_content_root(repo_root)
    try:
        from apps.integrations.uefn_mcp import mcp_status_summary

        mcp_status = mcp_status_summary(repo_root)
    except Exception as exc:  # noqa: BLE001
        mcp_status = {"enabled": bool(settings.get("uefn_mcp_enabled", False)), "error": str(exc)}
    try:
        from apps.integrations.uefn_toolbelt import toolbelt_status_summary

        toolbelt_status = toolbelt_status_summary(repo_root)
    except Exception as exc:  # noqa: BLE001
        toolbelt_status = {"enabled": bool(settings.get("uefn_toolbelt_enabled", False)), "error": str(exc)}
    return {
        "platform": "uefn",
        "preferred_runtime": settings.get("preferred_runtime", "uefn_verse"),
        "preferred_bridge": settings.get("preferred_bridge", "uefn_verse"),
        "scene_backend": choose_scene_backend(repo_root),
        "capture_backend": choose_capture_backend(repo_root),
        "action_backend": choose_action_backend(repo_root),
        "uefn_project_available": uefn_project_available(repo_root),
        "verse_workspace_available": verse_workspace_available(repo_root),
        "uefn_content_root_available": content_root is not None,
        "scene_graph_enabled": bool(settings.get("scene_graph_enabled", True)),
        "fortnite_devices_enabled": bool(settings.get("fortnite_devices_enabled", True)),
        "creative_devices_enabled": bool(settings.get("creative_devices_enabled", True)),
        "scene_graph_beta": bool(settings.get("scene_graph_beta", True)),
        "uefn_mcp": mcp_status,
        "uefn_toolbelt": toolbelt_status,
        "paths": {
            "uefn_project_path": settings.get("uefn_project_path", ""),
            "uefn_project_root": str(uefn_project_root(repo_root) or ""),
            "uefn_content_root": str(content_root or ""),
            "uefn_editor_path": settings.get("uefn_editor_path", ""),
            "verse_root": settings.get("verse_root", ""),
            "generated_root": settings.get("generated_root", ""),
            "export_root": settings.get("export_root", ""),
            "latest_scene_state_path": settings.get("latest_scene_state_path", ""),
            "capture_import_dir": settings.get("capture_import_dir", ""),
            "uefn_mcp_repo_path": settings.get("uefn_mcp_repo_path", ""),
            "uefn_mcp_server_path": settings.get("uefn_mcp_server_path", ""),
            "uefn_mcp_listener_path": settings.get("uefn_mcp_listener_path", ""),
            "uefn_mcp_init_path": settings.get("uefn_mcp_init_path", ""),
            "uefn_mcp_client_config_path": settings.get("uefn_mcp_client_config_path", ""),
            "uefn_toolbelt_repo_path": settings.get("uefn_toolbelt_repo_path", ""),
            "uefn_toolbelt_python_root": settings.get("uefn_toolbelt_python_root", ""),
            "uefn_toolbelt_package_path": settings.get("uefn_toolbelt_package_path", ""),
            "uefn_toolbelt_init_path": settings.get("uefn_toolbelt_init_path", ""),
            "uefn_toolbelt_mcp_server_path": settings.get("uefn_toolbelt_mcp_server_path", ""),
            "uefn_toolbelt_client_path": settings.get("uefn_toolbelt_client_path", ""),
            "uefn_toolbelt_launcher_path": settings.get("uefn_toolbelt_launcher_path", ""),
            "uefn_toolbelt_docs_root": settings.get("uefn_toolbelt_docs_root", ""),
        },
    }
