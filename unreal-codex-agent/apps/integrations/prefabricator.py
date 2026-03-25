from __future__ import annotations

from typing import Any


STRUCTURAL_PREFAB_MOUNT_TYPES = {"opening", "corner", "roof"}
PREFAB_PREFIXES = ("PA_", "PAC_")


def prefabricator_settings(project_config: dict[str, Any] | None) -> dict[str, Any]:
    integrations = (project_config or {}).get("integrations", {}) or {}
    engine = (project_config or {}).get("engine", {}) or {}
    settings = dict(integrations.get("prefabricator", {}) or {})
    mount_types = settings.get("prefer_prefabs_for_mount_types", list(STRUCTURAL_PREFAB_MOUNT_TYPES))
    if not isinstance(mount_types, list):
        mount_types = list(STRUCTURAL_PREFAB_MOUNT_TYPES)
    settings["prefer_prefabs_for_mount_types"] = [str(value) for value in mount_types if value]
    settings.setdefault("enabled", False)
    settings.setdefault("plugin_folder_name", "Prefabricator")
    settings.setdefault("reference_only", str(engine.get("platform", "")).lower() == "uefn")
    return settings


def should_prefer_prefabs(project_config: dict[str, Any] | None, requested_mount_type: str | None) -> bool:
    if not requested_mount_type:
        return False
    settings = prefabricator_settings(project_config)
    if not bool(settings.get("enabled", False)):
        return False
    if bool(settings.get("reference_only", False)):
        return False
    return requested_mount_type in set(settings.get("prefer_prefabs_for_mount_types", []))


def is_prefab_asset(record: dict[str, Any] | None) -> bool:
    if not isinstance(record, dict):
        return False
    tags = record.get("tags", {}) or {}
    if bool(tags.get("is_prefab", False)):
        return True
    asset_name = str(record.get("asset_name") or "").upper()
    asset_class = str(record.get("asset_class") or "")
    return asset_name.startswith(PREFAB_PREFIXES) or "Prefab" in asset_class


def prefab_family(record: dict[str, Any] | None) -> str | None:
    if not isinstance(record, dict):
        return None
    tags = record.get("tags", {}) or {}
    family = tags.get("prefab_family")
    if family:
        return str(family)
    if is_prefab_asset(record):
        return str(tags.get("mount_type") or tags.get("category") or "prefab")
    return None


def structural_prefab_bonus(record: dict[str, Any], requested_mount_type: str | None) -> float:
    if not requested_mount_type or requested_mount_type not in STRUCTURAL_PREFAB_MOUNT_TYPES:
        return 0.0
    if not is_prefab_asset(record):
        return 0.0
    tags = record.get("tags", {}) or {}
    mount_type = str(tags.get("mount_type") or "")
    bonus = 0.08
    if mount_type == requested_mount_type:
        bonus += 0.07
    if requested_mount_type == "corner" and "snap_to_corner" in (tags.get("placement_behavior") or []):
        bonus += 0.03
    if requested_mount_type == "roof" and "roof_aligned" in (tags.get("placement_behavior") or []):
        bonus += 0.03
    if requested_mount_type == "opening" and "shell_boundary" in (tags.get("placement_behavior") or []):
        bonus += 0.03
    return bonus
