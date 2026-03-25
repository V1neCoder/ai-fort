from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


DEFAULT_DEVELOPER_TOOLS = {
    "enabled": True,
    "experimental": True,
    "scene_xray": {
        "enabled": True,
        "auto_generate_per_cycle": True,
        "default_xray_on": True,
        "default_show_identified": True,
        "default_show_undefined": True,
        "default_show_labels": True,
        "default_show_tool_list": True,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def merge_developer_tools_config(project_config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_DEVELOPER_TOOLS, dict(project_config.get("developer_tools") or {}))


def scene_xray_settings(project_config: dict[str, Any]) -> dict[str, Any]:
    developer_tools = merge_developer_tools_config(project_config)
    return dict(developer_tools.get("scene_xray") or {})


def developer_tools_enabled(project_config: dict[str, Any]) -> bool:
    settings = merge_developer_tools_config(project_config)
    return bool(settings.get("enabled", True))


def scene_xray_enabled(project_config: dict[str, Any]) -> bool:
    if not developer_tools_enabled(project_config):
        return False
    return bool(scene_xray_settings(project_config).get("enabled", True))


def scene_xray_auto_generate(project_config: dict[str, Any]) -> bool:
    if not scene_xray_enabled(project_config):
        return False
    return bool(scene_xray_settings(project_config).get("auto_generate_per_cycle", True))


def load_project_config(repo_root: Path) -> dict[str, Any]:
    project_path = repo_root / "config" / "project.json"
    if not project_path.exists():
        return {}
    try:
        payload = json.loads(project_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_project_config(repo_root: Path, project_config: dict[str, Any]) -> None:
    project_path = repo_root / "config" / "project.json"
    project_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=project_path.parent, suffix=".tmp") as handle:
            handle.write(json.dumps(project_config, indent=2))
            temp_path = Path(handle.name)
        temp_path.replace(project_path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
