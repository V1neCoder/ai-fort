import json
from pathlib import Path

import apps.integrations.uefn_mcp as uefn_mcp
from apps.codex_bridge.codex_session import CodexSession
from apps.integrations.uefn_backend import backend_settings
from apps.orchestrator.dirty_zone import DirtyZone
from apps.mcp_extensions.scene_tools import enrich_scene_state
from apps.mcp_extensions.uefn_tools import _stray_tool_generated_paths_for_zone
from apps.placement.assembly_builder import BoxRoomSpec, HouseSpec, StructureSpec, build_box_room_actions, build_box_room_segments
from apps.placement.assembly_builder import build_house_actions, build_house_segments, build_house_structure_plan, build_structure_actions, build_structure_plan, plan_box_room_spec, plan_house_spec, plan_structure_spec
from apps.placement.interference import detect_actor_conflicts, find_non_interfering_location
from apps.placement.managed_registry import registry_layout_snapshot, upsert_slot_record
from apps.placement.placement_solver import normalize_action_payload
from apps.placement.profile_store import load_pose_profile, save_pose_profile
from apps.placement.structure_validation import validate_structure_plan
from apps.placement.support_fit import derive_support_surface_fit
from apps.uefn.verse_export import apply_action_via_verse_export
from apps.validation.rules.registry_integrity import validate_registry_integrity
from apps.validation.rules.orientation_fit import validate_orientation_fit
from apps.validation.rules.placement_interference import validate_placement_interference
from apps.validation.rules.support_ownership import validate_support_ownership
from apps.validation.rules.support_surface_fit import validate_support_surface_fit


def write_repo_config(repo_root: Path) -> None:
    config_dir = repo_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "project.json").write_text(
        json.dumps(
            {
                "default_room_type": "living_room",
                "verse": {
                    "auto_select_after_apply": False,
                    "auto_focus_after_apply": False,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (config_dir / "room_taxonomy.json").write_text(
        json.dumps({"top_level_groups": {"living": ["living_room"]}}, indent=2),
        encoding="utf-8",
    )


def make_actor(
    *,
    label: str,
    class_name: str,
    location: list[float],
    extent: list[float],
    selected: bool = False,
    asset_path: str = "",
) -> dict:
    return {
        "label": label,
        "actor_name": label,
        "class_name": class_name,
        "actor_path": f"/Game/Test/{label}",
        "asset_path": asset_path,
        "selected": selected,
        "location": list(location),
        "rotation": [0.0, 0.0, 0.0],
        "bounds_cm": {
            "origin": list(location),
            "box_extent": list(extent),
        },
    }


def make_floor_asset_record() -> dict:
    return {
        "asset_path": "/Game/Props/Furniture/SM_Test_FloorAsset",
        "tags": {
            "mount_type": "floor",
        },
        "scale_limits": {
            "min": 0.8,
            "max": 1.2,
            "preferred": 1.0,
        },
    }


def make_enriched_floor_scene(repo_root: Path) -> dict:
    write_repo_config(repo_root)
    raw_scene = {
        "map_name": "MyProjectA",
        "room_type": "living_room",
        "actors": [
            make_actor(
                label="UpperSlab_Selected",
                class_name="GridPlane_C",
                location=[500.0, 500.0, 100.0],
                extent=[500.0, 500.0, 10.0],
                selected=True,
                asset_path="/Game/Environment/GridPlane",
            ),
            make_actor(
                label="Landscape_Main",
                class_name="LandscapeStreamingProxy",
                location=[0.0, 0.0, 0.0],
                extent=[5000.0, 5000.0, 5.0],
                selected=False,
                asset_path="/Game/Environment/Landscape",
            ),
            make_actor(
                label="OtherSlab",
                class_name="GridPlane_C",
                location=[540.0, 540.0, 80.0],
                extent=[500.0, 500.0, 10.0],
                selected=False,
                asset_path="/Game/Environment/GridPlaneOther",
            ),
        ],
    }
    return enrich_scene_state(raw_scene, repo_root)


def make_enriched_floor_scene_with_selected_wall(repo_root: Path) -> dict:
    write_repo_config(repo_root)
    raw_scene = {
        "map_name": "MyProjectA",
        "room_type": "living_room",
        "actors": [
            make_actor(
                label="SelectedWall",
                class_name="StaticMeshActor",
                location=[500.0, 500.0, 150.0],
                extent=[10.0, 200.0, 150.0],
                selected=True,
                asset_path="/Game/Environment/WallPanel",
            ),
            make_actor(
                label="GridPlane4",
                class_name="GridPlane_C",
                location=[500.0, 500.0, 100.0],
                extent=[500.0, 500.0, 10.0],
                selected=False,
                asset_path="/Game/Environment/GridPlane",
            ),
            make_actor(
                label="Landscape_Main",
                class_name="LandscapeStreamingProxy",
                location=[0.0, 0.0, 0.0],
                extent=[5000.0, 5000.0, 5.0],
                selected=False,
                asset_path="/Game/Environment/Landscape",
            ),
        ],
    }
    return enrich_scene_state(raw_scene, repo_root)


def test_selected_slab_beats_nearest_support_surface(tmp_path: Path):
    scene_state = make_enriched_floor_scene(tmp_path)

    placement_targets = dict(scene_state.get("placement_targets") or {})
    assert placement_targets["support_actor_label"] == "UpperSlab_Selected"
    assert placement_targets["support_reference_source"] == "selected_actor"
    assert placement_targets["support_surface_kind"] == "upper_slab"
    assert placement_targets["surface_anchor"] == [500.0, 500.0, 110.0]
    assert placement_targets.get("ground_anchor") is None


def test_selected_wall_does_not_override_floor_support_selection(tmp_path: Path):
    scene_state = make_enriched_floor_scene_with_selected_wall(tmp_path)

    placement_targets = dict(scene_state.get("placement_targets") or {})
    assert placement_targets["support_actor_label"] == "GridPlane4"
    assert placement_targets["support_reference_source"] == "nearest_structural_support"
    assert placement_targets["support_surface_kind"] == "support_surface"
    assert placement_targets["surface_anchor"] == [500.0, 500.0, 110.0]


def test_place_asset_on_upper_slab_uses_surface_anchor_not_ground_anchor(tmp_path: Path):
    scene_state = make_enriched_floor_scene(tmp_path)

    normalized = normalize_action_payload(
        action_payload={
            "action": "place_asset",
            "target_zone": "zone_0001",
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        },
        scene_state=scene_state,
        dirty_zone={"bounds": scene_state.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )

    hint = dict(normalized.get("placement_hint") or {})
    assert hint["placement_phase"] == "initial_place"
    assert hint["snap_policy"] == "initial_only"
    assert hint["support_reference_policy"] == "selected_first"
    assert hint["support_surface_kind"] == "upper_slab"
    assert hint["surface_anchor"] == [500.0, 500.0, 110.0]
    assert hint.get("ground_anchor") is None
    assert normalized["transform"]["location"] == [500.0, 500.0, 110.0]


def test_move_actor_preserves_requested_transform_without_resnapping(tmp_path: Path):
    scene_state = make_enriched_floor_scene(tmp_path)

    normalized = normalize_action_payload(
        action_payload={
            "action": "move_actor",
            "target_zone": "zone_0001",
            "transform": {
                "location": [900.0, 900.0, 450.0],
                "rotation": [12.0, 20.0, 30.0],
                "scale": [1.1, 0.9, 1.0],
            },
        },
        scene_state=scene_state,
        dirty_zone={"bounds": scene_state.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )

    assert normalized["placement_hint"]["placement_phase"] == "reposition"
    assert normalized["placement_hint"]["snap_policy"] == "none"
    assert normalized["transform"]["location"] == [900.0, 900.0, 450.0]
    assert normalized["transform"]["rotation"] == [12.0, 20.0, 30.0]
    assert normalized["transform"]["scale"] == [1.1, 0.9, 1.0]


def test_reanchor_snaps_back_to_selected_support_surface(tmp_path: Path):
    scene_state = make_enriched_floor_scene(tmp_path)

    normalized = normalize_action_payload(
        action_payload={
            "action": "move_actor",
            "target_zone": "zone_0001",
            "placement_hint": {
                "placement_phase": "reanchor",
            },
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        },
        scene_state=scene_state,
        dirty_zone={"bounds": scene_state.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )

    assert normalized["placement_hint"]["placement_phase"] == "reanchor"
    assert normalized["placement_hint"]["snap_policy"] == "force"
    assert normalized["transform"]["location"] == [500.0, 500.0, 110.0]


def test_pose_profile_is_cached_and_reused(tmp_path: Path):
    write_repo_config(tmp_path)
    saved = save_pose_profile(
        tmp_path,
        asset_path="/Game/Props/Furniture/SM_Test_FloorAsset",
        rest_rotation_internal=[-90.0, 0.0, 0.0],
        orientation_candidate="roll_neg_90",
        height_cm=32.0,
        support_surface_kind="support_surface",
        support_fit_state="on_surface",
    )

    loaded = load_pose_profile(tmp_path, "/Game/Props/Furniture/SM_Test_FloorAsset")
    assert loaded is not None
    assert loaded["rest_rotation_internal"] == [-90.0, 0.0, 0.0]
    assert loaded["orientation_candidate"] == "roll_neg_90"
    assert saved["asset_path"] == loaded["asset_path"]


def test_backend_defaults_leave_camera_and_selection_unchanged(tmp_path: Path):
    write_repo_config(tmp_path)
    settings = backend_settings(tmp_path)

    assert settings["auto_select_after_apply"] is False
    assert settings["auto_focus_after_apply"] is False


def test_repeated_runs_stay_deterministic_on_same_selected_support_surface(tmp_path: Path):
    scene_state_a = make_enriched_floor_scene(tmp_path)
    scene_state_b = make_enriched_floor_scene(tmp_path)
    action_payload = {
        "action": "place_asset",
        "target_zone": "zone_0001",
        "transform": {
            "location": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
    }

    normalized_a = normalize_action_payload(
        action_payload=action_payload,
        scene_state=scene_state_a,
        dirty_zone={"bounds": scene_state_a.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )
    normalized_b = normalize_action_payload(
        action_payload=action_payload,
        scene_state=scene_state_b,
        dirty_zone={"bounds": scene_state_b.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )

    assert scene_state_a["placement_targets"] == scene_state_b["placement_targets"]
    assert normalized_a["transform"] == normalized_b["transform"]


def test_support_surface_fit_only_flags_true_offsets(tmp_path: Path):
    write_repo_config(tmp_path)
    scene_state = {
        "placement_targets": {
            "surface_anchor": [0.0, 0.0, 100.0],
            "support_surface_kind": "support_surface",
        },
        "dirty_bounds": {
            "surface_anchor": [0.0, 0.0, 100.0],
            "support_surface_kind": "support_surface",
        },
        "active_actor": {
            "bounds_cm": {
                "origin": [0.0, 0.0, 110.0],
                "box_extent": [10.0, 10.0, 10.0],
            },
        },
    }
    action = {
        "placement_hint": {
            "placement_phase": "initial_place",
            "snap_policy": "initial_only",
        }
    }

    on_surface = validate_support_surface_fit(
        scene_state=scene_state,
        action=action,
        enabled=True,
        fail_hard=True,
    )
    assert on_surface["passed"] is True
    assert on_surface["details"]["support_surface_fit_state"] == "on_surface"

    scene_state["active_actor"]["bounds_cm"]["origin"] = [0.0, 0.0, 130.0]
    floating = validate_support_surface_fit(
        scene_state=scene_state,
        action=action,
        enabled=True,
        fail_hard=True,
    )
    assert floating["passed"] is False
    assert floating["details"]["support_surface_fit_state"] == "floating"


def test_support_surface_fit_skips_wall_like_structural_segments(tmp_path: Path):
    write_repo_config(tmp_path)
    scene_state = {
        "placement_targets": {
            "surface_anchor": [0.0, 0.0, 0.0],
            "support_surface_kind": "support_surface",
        },
        "active_actor": {
            "bounds_cm": {
                "origin": [0.0, 0.0, 260.0],
                "box_extent": [70.0, 10.0, 40.0],
            },
        },
    }
    action = {
        "placement_hint": {
            "placement_phase": "initial_place",
            "snap_policy": "none",
            "mount_type": "wall",
            "expected_mount_type": "wall",
        }
    }
    result = validate_support_surface_fit(
        scene_state=scene_state,
        action=action,
        enabled=True,
        fail_hard=True,
    )
    assert result["passed"] is True
    assert result["details"]["skipped"] == "mount_type_not_floor_like"


def test_live_support_fit_marks_wall_header_as_not_applicable(tmp_path: Path):
    write_repo_config(tmp_path)
    scene_state = {
        "placement_targets": {
            "surface_anchor": [0.0, 0.0, 0.0],
            "support_surface_kind": "support_surface",
        },
        "dirty_bounds": {
            "surface_anchor": [0.0, 0.0, 0.0],
            "support_surface_kind": "support_surface",
        },
    }
    active_actor = {
        "bounds_cm": {
            "origin": [0.0, 0.0, 260.0],
            "box_extent": [70.0, 10.0, 40.0],
        },
    }
    result = derive_support_surface_fit(
        scene_state=scene_state,
        active_actor=active_actor,
        mount_type="wall",
    )
    assert result["support_surface_fit_state"] == "not_applicable"
    assert result["support_fit_skipped"] == "mount_type_not_floor_like"
    assert result["support_surface_fit_ok"] is True


def test_orientation_fit_uses_cached_pose_for_floor_support_validation(tmp_path: Path):
    write_repo_config(tmp_path)
    save_pose_profile(
        tmp_path,
        asset_path="/Game/Props/Furniture/SM_Test_FloorAsset",
        rest_rotation_internal=[-90.0, 0.0, 0.0],
        orientation_candidate="roll_neg_90",
        height_cm=32.0,
        support_surface_kind="support_surface",
        support_fit_state="on_surface",
    )
    scene_state = {
        "expected_mount_type": "floor",
        "active_actor": {
            "rotation": [-90.0, 0.0, 0.0],
            "orientation_height_cm": 32.0,
        },
    }
    action = {
        "asset_path": "/Game/Props/Furniture/SM_Test_FloorAsset",
        "placement_hint": {
            "placement_phase": "initial_place",
            "snap_policy": "initial_only",
            "mount_type": "floor",
        },
    }

    result = validate_orientation_fit(
        repo_root=tmp_path,
        scene_state=scene_state,
        action=action,
        enabled=True,
        fail_hard=True,
    )
    assert result["passed"] is True
    assert result["details"]["roll_delta_deg"] == 0.0
    assert result["details"]["pitch_delta_deg"] == 0.0


def test_reuse_target_keeps_one_same_label_actor_and_cleans_duplicates(monkeypatch):
    deleted_paths: list[str] = []

    def fake_find_actors_by_label(repo_root: Path, label: str) -> list[dict]:
        return [
            {
                "label": label,
                "actor_path": "/Game/Test/ActorFar",
                "asset_path": "/Game/Props/Furniture/SM_Test_FloorAsset",
                "location": [600.0, 600.0, 100.0],
            },
            {
                "label": label,
                "actor_path": "/Game/Test/ActorNear",
                "asset_path": "/Game/Props/Furniture/SM_Test_FloorAsset",
                "location": [500.0, 500.0, 100.0],
            },
            {
                "label": label,
                "actor_path": "/Game/Test/ActorMid",
                "asset_path": "/Game/Props/Furniture/SM_Test_FloorAsset",
                "location": [520.0, 500.0, 100.0],
            },
        ]

    def fake_delete(repo_root: Path, actor_paths: list[str]) -> dict[str, object]:
        deleted_paths.extend(actor_paths)
        return {"success": True, "deleted_count": len(actor_paths), "deleted_paths": list(actor_paths)}

    monkeypatch.setattr(uefn_mcp, "find_actors_by_label", fake_find_actors_by_label)
    monkeypatch.setattr(uefn_mcp, "_delete_actors_by_paths", fake_delete)

    primary, reuse_result = uefn_mcp._find_reusable_spawn_target(
        Path("C:/AI Fort/unreal-codex-agent"),
        spawn_label="SM_Test_FloorAsset_zone_0001",
        asset_path="/Game/Props/Furniture/SM_Test_FloorAsset",
        support_anchor=[500.0, 500.0, 110.0],
        owned_actor_paths={
            "/Game/Test/ActorFar",
            "/Game/Test/ActorNear",
            "/Game/Test/ActorMid",
        },
    )

    assert primary["actor_path"] == "/Game/Test/ActorNear"
    assert reuse_result is not None
    assert reuse_result["matched_count"] == 3
    assert deleted_paths == ["/Game/Test/ActorMid", "/Game/Test/ActorFar"]


def test_reuse_target_cleans_tool_generated_duplicates_even_if_unclaimed(monkeypatch):
    deleted_paths: list[str] = []

    def fake_find_actors_by_label(repo_root: Path, label: str) -> list[dict]:
        return [
            {
                "label": "UCA_BlueWall_Back",
                "actor_path": "/Game/Test/WallKept",
                "asset_path": "/Engine/BasicShapes/Cube.Cube",
                "location": [0.0, 0.0, 0.0],
            },
            {
                "label": "UCA_BlueWall_Back",
                "actor_path": "/Game/Test/WallDuplicate",
                "asset_path": "/Engine/BasicShapes/Cube.Cube",
                "location": [50.0, 0.0, 0.0],
            },
        ]

    def fake_delete(repo_root: Path, actor_paths: list[str]) -> dict[str, object]:
        deleted_paths.extend(actor_paths)
        return {"success": True, "deleted_count": len(actor_paths), "deleted_paths": list(actor_paths)}

    monkeypatch.setattr(uefn_mcp, "find_actors_by_label", fake_find_actors_by_label)
    monkeypatch.setattr(uefn_mcp, "_delete_actors_by_paths", fake_delete)

    primary, reuse_result = uefn_mcp._find_reusable_spawn_target(
        Path("C:/AI Fort/unreal-codex-agent"),
        spawn_label="UCA_BlueWall_Back",
        asset_path="/Engine/BasicShapes/Cube.Cube",
        support_anchor=[0.0, 0.0, 0.0],
        owned_actor_paths=set(),
    )

    assert primary["actor_path"] == "/Game/Test/WallKept"
    assert reuse_result is not None
    assert deleted_paths == ["/Game/Test/WallDuplicate"]


def test_floor_spawn_label_stays_zone_stable_across_support_changes(tmp_path: Path):
    session = CodexSession(repo_root=tmp_path, mode="mock")
    dirty_zone = DirtyZone(
        zone_id="zone_0001",
        actor_ids=[],
        room_type="living_room",
        zone_type="room_local",
        shell_sensitive=False,
        capture_profile="default_room",
        bounds={},
    )
    action = session._mock_action_decision(
        dirty_zone=dirty_zone,
        shortlist=[
            {
                "asset_name": "SM_PG_Bot_Beacon",
                "asset_path": "/Game/Props/Furniture/SM_PG_Bot_Beacon",
                "tags": {"mount_type": "floor"},
                "scale_limits": {"min": 1.0, "max": 1.0, "preferred": 1.0},
            }
        ],
        scene_state={
            "placement_targets": {
                "reference_actor_label": "GridPlane4",
                "support_surface_kind": "support_surface",
            },
            "placement_context": {},
        },
    )

    assert action["spawn_label"] == "SM_PG_Bot_Beacon_zone_0001"


def test_support_fit_for_corrected_actor_uses_final_bottom_not_move_delta():
    actor_payload = {
        "bounds_cm": {
            "origin": [0.0, 0.0, 16.176],
            "box_extent": [70.8, 72.3, 16.176],
        }
    }
    fit_state = uefn_mcp._fit_state_for_actor_support(actor_payload, 0.0)
    assert fit_state["support_surface_fit_state"] == "on_surface"
    assert fit_state["support_surface_fit_ok"] is True


def test_normalize_action_defaults_managed_slot_and_identity_policy(tmp_path: Path):
    scene_state = make_enriched_floor_scene(tmp_path)

    place_asset = normalize_action_payload(
        action_payload={"action": "place_asset", "target_zone": "zone_0001"},
        scene_state=scene_state,
        dirty_zone={"bounds": scene_state.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )
    move_actor = normalize_action_payload(
        action_payload={"action": "move_actor", "target_zone": "zone_0001"},
        scene_state=scene_state,
        dirty_zone={"bounds": scene_state.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )

    assert place_asset["managed_slot"] == "primary"
    assert place_asset["identity_policy"] == "reuse_or_create"
    assert move_actor["managed_slot"] == "primary"
    assert move_actor["identity_policy"] == "reuse_only"


def test_registry_integrity_detects_duplicate_claims(tmp_path: Path):
    write_repo_config(tmp_path)
    session_path = tmp_path / "data" / "sessions" / "registry_integrity"
    session_path.mkdir(parents=True, exist_ok=True)
    upsert_slot_record(
        session_path,
        zone_id="zone_0001",
        managed_slot="primary",
        action_name="place_asset",
        identity_policy="reuse_or_create",
        actor_label="BeaconA",
        actor_path="/Game/Test/BeaconA",
        asset_path="/Game/Props/Furniture/SM_Test_FloorAsset",
        support_reference={"support_surface_kind": "support_surface"},
        placement_phase="initial_place",
        last_confirmed_transform={"location": [0.0, 0.0, 100.0]},
        fit_status={"support_surface_fit_state": "on_surface"},
        registry_status="claimed",
    )
    upsert_slot_record(
        session_path,
        zone_id="zone_0001",
        managed_slot="secondary_01",
        action_name="place_asset",
        identity_policy="reuse_or_create",
        actor_label="BeaconA",
        actor_path="/Game/Test/BeaconA",
        asset_path="/Game/Props/Furniture/SM_Test_FloorAsset",
        support_reference={"support_surface_kind": "support_surface"},
        placement_phase="initial_place",
        last_confirmed_transform={"location": [10.0, 0.0, 100.0]},
        fit_status={"support_surface_fit_state": "on_surface"},
        registry_status="claimed",
    )
    scene_state = {"managed_registry": registry_layout_snapshot(session_path)}

    result = validate_registry_integrity(
        scene_state=scene_state,
        action={"action": "place_asset", "target_zone": "zone_0001", "managed_slot": "primary"},
        enabled=True,
        fail_hard=True,
    )

    assert result["passed"] is False
    assert any("actor path" in issue for issue in result["issues"])
    assert any("actor label" in issue for issue in result["issues"])


def test_support_ownership_accepts_upper_slab_surface_family(tmp_path: Path):
    write_repo_config(tmp_path)
    scene_state = {
        "placement_targets": {
            "support_surface_kind": "upper_slab",
            "support_actor_label": "UpperSlab_Selected",
        },
        "active_actor": {
            "support_surface_kind": "support_surface",
            "support_actor_label": "UpperSlab_Selected",
        },
        "active_managed_record": {
            "support_reference": {
                "support_surface_kind": "upper_slab",
                "support_actor_label": "UpperSlab_Selected",
            }
        },
    }
    action = {
        "placement_hint": {
            "placement_phase": "initial_place",
            "snap_policy": "initial_only",
            "support_surface_kind": "upper_slab",
            "parent_support_actor": "UpperSlab_Selected",
        }
    }

    result = validate_support_ownership(
        scene_state=scene_state,
        action=action,
        enabled=True,
        fail_hard=True,
    )

    assert result["passed"] is True


def test_support_ownership_flags_real_ground_mismatch(tmp_path: Path):
    write_repo_config(tmp_path)
    scene_state = {
        "placement_targets": {
            "support_surface_kind": "landscape",
            "support_actor_label": "Landscape_Main",
        },
        "active_actor": {
            "support_surface_kind": "landscape",
            "support_actor_label": "Landscape_Main",
        },
        "active_managed_record": {
            "support_reference": {
                "support_surface_kind": "upper_slab",
                "support_actor_label": "UpperSlab_Selected",
            }
        },
    }
    action = {
        "placement_hint": {
            "placement_phase": "reanchor",
            "snap_policy": "force",
            "support_surface_kind": "upper_slab",
            "parent_support_actor": "UpperSlab_Selected",
        }
    }

    result = validate_support_ownership(
        scene_state=scene_state,
        action=action,
        enabled=True,
        fail_hard=True,
    )

    assert result["passed"] is False
    assert any("expected upper_slab" in issue for issue in result["issues"])


def test_box_room_planner_relocates_to_nearest_free_grid_slot(tmp_path: Path):
    write_repo_config(tmp_path)
    spec = BoxRoomSpec(
        zone_id="zone_box",
        center_x=0.0,
        center_y=0.0,
        support_z=0.0,
        inner_width_cm=400.0,
        inner_depth_cm=400.0,
        grid_snap_cm=100.0,
    )
    scene_actors = [
        make_actor(
            label="OccupiedPad",
            class_name="StaticMeshActor",
            location=[0.0, 0.0, 150.0],
            extent=[300.0, 300.0, 150.0],
            selected=False,
            asset_path="/Game/Environment/OccupiedPad",
        )
    ]
    plan = plan_box_room_spec(spec, scene_actors)

    assert plan["relocated"] is True
    assert plan["conflict_count"] == 0
    assert plan["spec"].center_x != 0.0 or plan["spec"].center_y != 0.0


def test_box_room_planner_ignores_existing_zone_managed_segments(tmp_path: Path):
    write_repo_config(tmp_path)
    spec = BoxRoomSpec(
        zone_id="zone_box",
        center_x=0.0,
        center_y=0.0,
        support_z=0.0,
        inner_width_cm=400.0,
        inner_depth_cm=400.0,
        grid_snap_cm=100.0,
        label_prefix="UCA_BoxRoom",
    )
    scene_actors = [
        make_actor(
            label="UCA_BoxRoom_Back",
            class_name="StaticMeshActor",
            location=[0.0, 210.0, 150.0],
            extent=[200.0, 10.0, 150.0],
            selected=False,
            asset_path="/Engine/BasicShapes/Cube.Cube",
        ),
        make_actor(
            label="OtherRoomBlocker",
            class_name="StaticMeshActor",
            location=[900.0, 0.0, 150.0],
            extent=[200.0, 200.0, 150.0],
            selected=False,
            asset_path="/Game/Environment/OtherRoomBlocker",
        ),
    ]
    plan = plan_box_room_spec(
        spec,
        scene_actors,
        ignore_actor_labels={"UCA_BoxRoom_Back", "UCA_BoxRoom_Left", "UCA_BoxRoom_Right", "UCA_BoxRoom_FrontLeft", "UCA_BoxRoom_FrontRight", "UCA_BoxRoom_DoorHeader"},
    )

    assert plan["relocated"] is False
    assert plan["conflict_count"] == 0
    assert plan["spec"].center_x == 0.0
    assert plan["spec"].center_y == 0.0


def test_cleanup_helper_detects_unclaimed_tool_generated_duplicates(monkeypatch):
    zone_records = [
        {
            "actor_label": "UCA_BoxRoom_Back",
            "actor_path": "/Game/Test/UCA_BoxRoom_Back_Primary",
        }
    ]

    def fake_find_actors_by_label(repo_root: Path, label: str) -> list[dict]:
        return [
            {"label": label, "actor_path": "/Game/Test/UCA_BoxRoom_Back_Primary"},
            {"label": label, "actor_path": "/Game/Test/UCA_BoxRoom_Back_Duplicate"},
            {"label": "NonToolThing", "actor_path": "/Game/Test/NonToolThing"},
        ]

    monkeypatch.setattr("apps.mcp_extensions.uefn_tools.find_actors_by_label", fake_find_actors_by_label)

    stray_paths = _stray_tool_generated_paths_for_zone(Path("C:/AI Fort/unreal-codex-agent"), zone_records)
    assert stray_paths == ["/Game/Test/UCA_BoxRoom_Back_Duplicate"]


def test_house_planner_relocates_when_requested_footprint_is_occupied(tmp_path: Path):
    write_repo_config(tmp_path)
    spec = HouseSpec(
        zone_id="zone_house",
        center_x=0.0,
        center_y=0.0,
        support_z=0.0,
        grid_snap_cm=100.0,
    )
    scene_actors = [
        make_actor(
            label="ExistingStructure",
            class_name="StaticMeshActor",
            location=[0.0, 0.0, 300.0],
            extent=[500.0, 450.0, 300.0],
            selected=False,
            asset_path="/Game/Environment/ExistingStructure",
        )
    ]

    plan = plan_house_spec(spec, scene_actors)
    assert plan["relocated"] is True
    assert plan["conflict_count"] == 0


def test_house_builder_creates_two_story_shell_with_roof_and_stairs():
    spec = HouseSpec(
        zone_id="zone_house",
        center_x=4200.0,
        center_y=6400.0,
        support_z=0.0,
        inner_width_cm=700.0,
        inner_depth_cm=600.0,
        story_height_cm=300.0,
        floor_thickness_cm=20.0,
        stair_step_count=10,
        stair_step_rise_cm=30.0,
        stair_step_run_cm=30.0,
        label_prefix="UCA_House",
        support_actor_label="GridPlane4",
        parent_support_actor="GridPlane4",
    )
    structure_plan = build_house_structure_plan(spec)
    segments = list(structure_plan.get("segments") or [])
    by_slot = {segment["managed_slot"]: segment for segment in segments}

    assert "floor_ground" in by_slot
    assert "floor_upper_left" in by_slot
    assert "floor_upper_right" in by_slot
    assert "floor_upper_front" in by_slot
    assert "landing_upper" in by_slot
    assert any(slot.startswith("story1_wall_back") for slot in by_slot)
    assert any(slot.startswith("story2_wall_front") for slot in by_slot)
    assert "roof_left" in by_slot
    assert "roof_right" in by_slot
    assert "roof_ridge" in by_slot
    assert "stair_guard_outer" in by_slot
    assert "stair_guard_front" in by_slot
    assert "gable_front_01" in by_slot
    assert "gable_back_01" in by_slot
    assert "stair_01" in by_slot
    assert "stair_10" in by_slot
    assert by_slot["floor_ground"]["location"][2] == 10.0
    assert by_slot["landing_upper"]["location"][2] == 310.0
    assert by_slot["roof_left"]["rotation"][2] == 30.0
    assert by_slot["roof_right"]["rotation"][2] == -30.0
    assert any(segment["structural_role"] == "window_glass" for segment in segments)
    assert any(segment["structure_piece_role"] == "canopy" for segment in segments)
    assert any(volume["name"] == "stairwell_opening" for volume in list(structure_plan.get("reserved_volumes") or []))


def test_house_builder_supports_multistory_apartment_shell():
    spec = HouseSpec(
        zone_id="zone_apartment",
        center_x=4200.0,
        center_y=5200.0,
        support_z=0.0,
        variation_seed=12,
        story_count=4,
        inner_width_cm=1040.0,
        inner_depth_cm=920.0,
        story_height_cm=290.0,
        floor_thickness_cm=20.0,
        stair_step_count=10,
        stair_step_rise_cm=31.0,
        stair_step_run_cm=30.0,
        roof_style="parapet",
        residential_profile="apartment",
        window_columns_per_wall=3,
        entry_canopy_depth_cm=110.0,
        balcony_depth_cm=100.0,
        corner_column_diameter_cm=34.0,
        label_prefix="UCA_Apartment",
        support_actor_label="GridPlane4",
        parent_support_actor="GridPlane4",
    )
    structure_plan = build_house_structure_plan(spec)
    segments = list(structure_plan.get("segments") or [])
    by_slot = {segment["managed_slot"]: segment for segment in segments}

    assert structure_plan["story_count"] == 4
    assert "floor_story2_left" in by_slot
    assert "floor_story3_left" in by_slot
    assert "floor_story4_left" in by_slot
    assert "landing_story4" in by_slot
    assert any(slot.startswith("story4_wall_back") for slot in by_slot)
    assert "stair_story3_10" in by_slot
    assert "roof_slab" in by_slot
    assert "roof_parapet_front" in by_slot
    assert "roof_parapet_right" in by_slot
    assert any(slot == "story2_balcony_slab" for slot in by_slot)
    assert any("balcony" in slot and "rail" in slot for slot in by_slot)
    assert structure_plan["circulation_plan"]["stair_run"]["flight_count"] == 3
    assert any(segment["structural_role"] == "window_glass" for segment in segments)
    assert any(segment["structural_role"] == "corner_column" for segment in segments)
    assert any(volume["name"] == "stairwell_opening" for volume in list(structure_plan.get("reserved_volumes") or []))


def test_house_builder_uses_variation_seed_for_stair_side_and_mansion_features():
    left_plan = build_house_structure_plan(
        HouseSpec(
            zone_id="zone_mansion_left",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            variation_seed=1,
            story_count=4,
            inner_width_cm=1280.0,
            inner_depth_cm=980.0,
            residential_profile="mansion",
            balcony_depth_cm=135.0,
            entry_canopy_depth_cm=150.0,
            corner_column_diameter_cm=48.0,
            roof_style="gable",
        )
    )
    right_plan = build_house_structure_plan(
        HouseSpec(
            zone_id="zone_mansion_right",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            variation_seed=2,
            story_count=4,
            inner_width_cm=1280.0,
            inner_depth_cm=980.0,
            residential_profile="mansion",
            balcony_depth_cm=135.0,
            entry_canopy_depth_cm=150.0,
            corner_column_diameter_cm=48.0,
            roof_style="gable",
        )
    )

    assert left_plan["circulation_plan"]["stair_run"]["side"] != right_plan["circulation_plan"]["stair_run"]["side"]
    left_slots = {segment["managed_slot"] for segment in list(left_plan.get("segments") or [])}
    assert "story1_portico_column_left" in left_slots
    assert "story2_balcony_slab" in left_slots


def test_house_structure_plan_reserves_upper_stair_opening_and_landing():
    spec = HouseSpec(
        zone_id="zone_house",
        center_x=0.0,
        center_y=0.0,
        support_z=0.0,
    )
    structure_plan = build_house_structure_plan(spec)

    reserved_by_name = {
        str(item.get("name")): dict(item)
        for item in list(structure_plan.get("reserved_volumes") or [])
        if isinstance(item, dict)
    }
    assert "stairwell_opening" in reserved_by_name
    assert "stair_arrival_clearance" in reserved_by_name
    assert reserved_by_name["stairwell_opening"]["kind"] == "floor_void"
    assert reserved_by_name["stair_arrival_clearance"]["kind"] == "landing_clearance"
    stairwell_opening = reserved_by_name["stairwell_opening"]
    opening_width = stairwell_opening["max"][0] - stairwell_opening["min"][0]
    assert opening_width <= spec.stair_width_cm + (spec.stair_opening_margin_cm * 2.0) + 1.0


def test_house_upper_floor_slabs_do_not_fill_stairwell_opening():
    structure_plan = build_house_structure_plan(
        HouseSpec(
            zone_id="zone_house",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
        )
    )

    report = validate_structure_plan(structure_plan)
    assert report["navigable_floor_fit"]["passed"] is True
    assert report["circulation_path"]["passed"] is True


def test_structure_validation_fails_when_upper_floor_blocks_stairwell():
    structure_plan = build_house_structure_plan(
        HouseSpec(
            zone_id="zone_house",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
        )
    )
    stairwell = next(
        item for item in list(structure_plan.get("reserved_volumes") or [])
        if isinstance(item, dict) and item.get("name") == "stairwell_opening"
    )
    blocker_center_x = (stairwell["min"][0] + stairwell["max"][0]) / 2.0
    blocker_center_y = (stairwell["min"][1] + stairwell["max"][1]) / 2.0
    blocker_center_z = (stairwell["min"][2] + stairwell["max"][2]) / 2.0
    blocker_scale_x = max(0.6, (stairwell["max"][0] - stairwell["min"][0]) / 100.0)
    blocker_scale_y = max(0.6, (stairwell["max"][1] - stairwell["min"][1]) / 100.0)
    blocker_scale_z = max(0.2, (stairwell["max"][2] - stairwell["min"][2]) / 100.0)
    segments = list(structure_plan.get("segments") or [])
    segments.append(
        {
            "managed_slot": "bad_blocker",
            "spawn_label": "BadBlocker",
            "location": [blocker_center_x, blocker_center_y, blocker_center_z],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [blocker_scale_x, blocker_scale_y, blocker_scale_z],
            "structure_piece_role": "floor_slab",
            "allowed_reserved_volume_kinds": [],
        }
    )
    blocked_plan = {**structure_plan, "segments": segments}

    report = validate_structure_plan(blocked_plan)
    assert report["passed"] is False
    assert report["circulation_path"]["passed"] is False
    assert report["assembly_interference"]["passed"] is False


def test_roof_envelope_validation_flags_drifted_roof_panel():
    structure_plan = build_house_structure_plan(
        HouseSpec(
            zone_id="zone_house",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
        )
    )
    live_actors_by_slot = {
        "roof_left": {
            "location": [200.0, 0.0, 800.0],
            "rotation": [0.0, 5.0, 0.0],
            "scale": [2.0, 2.0, 0.18],
        }
    }

    report = validate_structure_plan(structure_plan, live_actors_by_slot=live_actors_by_slot)
    assert report["roof_envelope_fit"]["passed"] is False


def test_reserved_volume_conflicts_are_reported_for_functional_openings():
    structure_plan = build_house_structure_plan(
        HouseSpec(
            zone_id="zone_house",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
        )
    )
    stairwell = next(
        item for item in list(structure_plan.get("reserved_volumes") or [])
        if isinstance(item, dict) and item.get("name") == "stairwell_opening"
    )
    active_actor = make_actor(
        label="BlockingFloor",
        class_name="StaticMeshActor",
        location=[
            (stairwell["min"][0] + stairwell["max"][0]) / 2.0,
            (stairwell["min"][1] + stairwell["max"][1]) / 2.0,
            (stairwell["min"][2] + stairwell["max"][2]) / 2.0,
        ],
        extent=[
            max(25.0, (stairwell["max"][0] - stairwell["min"][0]) / 2.0),
            max(25.0, (stairwell["max"][1] - stairwell["min"][1]) / 2.0),
            max(10.0, (stairwell["max"][2] - stairwell["min"][2]) / 2.0),
        ],
        selected=False,
        asset_path="/Engine/BasicShapes/Cube.Cube",
    )

    conflicts = detect_actor_conflicts(
        active_actor,
        [],
        mount_type="floor",
        reserved_volumes=list(structure_plan.get("reserved_volumes") or []),
    )
    assert conflicts["reserved_volume_conflict_count"] > 0


def test_house_actions_include_mount_types_for_structural_segments():
    actions = build_house_actions(
        HouseSpec(
            zone_id="zone_house",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
        )
    )
    action_by_slot = {action["managed_slot"]: action for action in actions}
    assert action_by_slot["floor_ground"]["placement_hint"]["mount_type"] == "floor"
    wall_action = next(action for action in actions if str(action["managed_slot"]).startswith("story1_wall_back"))
    glass_action = next(action for action in actions if action["placement_hint"].get("material_role") == "glass")
    assert wall_action["placement_hint"]["mount_type"] == "wall"
    assert action_by_slot["roof_left"]["placement_hint"]["mount_type"] == "roof"
    assert glass_action["asset_path"] == "/Engine/BasicShapes/Cube.Cube"


def test_structure_planner_relocates_generic_structure_when_requested_footprint_is_occupied(tmp_path: Path):
    spec = StructureSpec(
        zone_id="zone_garage",
        structure_type="garage",
        center_x=0.0,
        center_y=0.0,
        support_z=0.0,
        width_cm=800.0,
        depth_cm=720.0,
    )
    scene_actors = [
        make_actor(
            label="ExistingWorkshop",
            class_name="StaticMeshActor",
            location=[480.0, 0.0, 150.0],
            extent=[80.0, 140.0, 180.0],
            asset_path="/Game/Environment/ExistingWorkshop",
        )
    ]

    plan = plan_structure_spec(spec, scene_actors)

    assert plan["relocated"] is True
    assert plan["conflict_count"] == 0
    assert plan["spec"].center_x != 0.0 or plan["spec"].center_y != 0.0


def test_garage_structure_plan_builds_enclosed_shell_with_opening_and_roof():
    structure_plan = build_structure_plan(
        StructureSpec(
            zone_id="zone_garage",
            structure_type="garage",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            width_cm=820.0,
            depth_cm=760.0,
            label_prefix="UCA_Garage",
        )
    )

    segments = list(structure_plan.get("segments") or [])
    by_slot = {segment["managed_slot"]: segment for segment in segments}

    assert structure_plan["structure_type"] == "garage"
    assert "floor_base" in by_slot
    assert "wall_front_left" in by_slot
    assert "wall_front_right" in by_slot
    assert "front_header" in by_slot
    assert "roof_left" in by_slot
    assert "roof_right" in by_slot
    assert "roof_ridge" in by_slot
    assert any(volume["name"] == "front_entry_opening" for volume in list(structure_plan.get("reserved_volumes") or []))


def test_warehouse_structure_plan_builds_large_enclosed_shell_with_wide_opening():
    structure_plan = build_structure_plan(
        StructureSpec(
            zone_id="zone_warehouse",
            structure_type="warehouse",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            width_cm=1320.0,
            depth_cm=980.0,
            opening_width_cm=420.0,
            opening_height_cm=300.0,
            label_prefix="UCA_Warehouse",
        )
    )

    segments = list(structure_plan.get("segments") or [])
    by_slot = {segment["managed_slot"]: segment for segment in segments}

    assert structure_plan["structure_type"] == "warehouse"
    assert "wall_front_left" in by_slot
    assert "wall_front_right" in by_slot
    assert "front_header" in by_slot
    assert "roof_left" in by_slot
    assert "roof_right" in by_slot
    assert by_slot["wall_front_left"]["scale"][0] < 4.7
    assert by_slot["wall_front_right"]["scale"][0] < 4.7
    assert any(volume["name"] == "front_entry_opening" for volume in list(structure_plan.get("reserved_volumes") or []))


def test_pavilion_structure_plan_builds_open_post_and_roof_layout():
    structure_plan = build_structure_plan(
        StructureSpec(
            zone_id="zone_pavilion",
            structure_type="pavilion",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            width_cm=900.0,
            depth_cm=720.0,
            label_prefix="UCA_Pavilion",
        )
    )

    segments = list(structure_plan.get("segments") or [])
    by_slot = {segment["managed_slot"]: segment for segment in segments}

    assert structure_plan["structure_type"] == "pavilion"
    assert structure_plan["reserved_volumes"] == []
    assert "post_front_left" in by_slot
    assert "post_front_right" in by_slot
    assert "post_back_left" in by_slot
    assert "post_back_right" in by_slot
    assert "beam_front" in by_slot
    assert "beam_back" in by_slot
    assert "roof_left" in by_slot
    assert "roof_right" in by_slot
    assert "roof_ridge" in by_slot


def test_canopy_structure_plan_builds_open_support_layout_with_posts_and_roof():
    structure_plan = build_structure_plan(
        StructureSpec(
            zone_id="zone_canopy",
            structure_type="canopy",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            width_cm=860.0,
            depth_cm=620.0,
            label_prefix="UCA_Canopy",
        )
    )

    segments = list(structure_plan.get("segments") or [])
    by_slot = {segment["managed_slot"]: segment for segment in segments}

    assert structure_plan["structure_type"] == "canopy"
    assert structure_plan["reserved_volumes"] == []
    assert "post_front_left" in by_slot
    assert "post_front_right" in by_slot
    assert "beam_front" in by_slot
    assert "beam_back" in by_slot
    assert "roof_left" in by_slot
    assert "roof_right" in by_slot
    assert "roof_ridge" in by_slot


def test_structure_actions_share_managed_contract():
    actions = build_structure_actions(
        StructureSpec(
            zone_id="zone_workshop",
            structure_type="workshop",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            label_prefix="UCA_Workshop",
        )
    )
    action_by_slot = {action["managed_slot"]: action for action in actions}

    assert action_by_slot["floor_base"]["identity_policy"] == "reuse_or_create"
    assert action_by_slot["floor_base"]["placement_hint"]["structure_type"] == "workshop"
    assert action_by_slot["roof_left"]["placement_hint"]["mount_type"] == "roof"
    assert action_by_slot["wall_front_left"]["placement_hint"]["mount_type"] == "wall"


def test_publish_safe_export_keeps_managed_action_contract(tmp_path: Path):
    write_repo_config(tmp_path)
    session_path = tmp_path / "data" / "sessions" / "publish_safe"
    session_path.mkdir(parents=True, exist_ok=True)
    scene_state = make_enriched_floor_scene(tmp_path)
    action_payload = normalize_action_payload(
        action_payload={
            "action": "place_asset",
            "target_zone": "zone_0001",
            "managed_slot": "primary",
            "identity_policy": "reuse_or_create",
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        },
        scene_state=scene_state,
        dirty_zone={"bounds": scene_state.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )
    dirty_zone = DirtyZone(
        zone_id="zone_0001",
        actor_ids=[],
        room_type="living_room",
        zone_type="room_local",
        shell_sensitive=False,
        capture_profile="default_room",
        bounds=scene_state.get("dirty_bounds", {}),
    ).to_dict()

    result = apply_action_via_verse_export(
        repo_root=tmp_path,
        session_path=session_path,
        cycle_number=1,
        scene_state=scene_state,
        dirty_zone=dirty_zone,
        action_payload=action_payload,
    )
    apply_queue = json.loads((session_path / "uefn_bridge" / "apply_queue" / "current.json").read_text(encoding="utf-8"))

    assert result["backend"] == "uefn_verse_apply"
    assert result["managed_slot"] == action_payload["managed_slot"]
    assert result["identity_policy"] == action_payload["identity_policy"]
    assert result["placement_phase"] == action_payload["placement_hint"]["placement_phase"]
    assert result["snap_policy"] == action_payload["placement_hint"]["snap_policy"]
    assert apply_queue["managed_slot"] == action_payload["managed_slot"]
    assert apply_queue["identity_policy"] == action_payload["identity_policy"]
    assert apply_queue["placement_phase"] == action_payload["placement_hint"]["placement_phase"]
    assert apply_queue["snap_policy"] == action_payload["placement_hint"]["snap_policy"]


def test_box_room_builder_creates_connected_walls_and_door_header():
    spec = BoxRoomSpec(
        zone_id="zone_box_room",
        center_x=7600.0,
        center_y=6400.0,
        support_z=0.0,
        inner_width_cm=400.0,
        inner_depth_cm=400.0,
        wall_height_cm=300.0,
        wall_thickness_cm=20.0,
        door_width_cm=140.0,
        door_height_cm=220.0,
        grid_snap_cm=10.0,
        label_prefix="UCA_BoxRoom",
        support_actor_label="GridPlane4",
        parent_support_actor="GridPlane4",
    )
    segments = build_box_room_segments(spec)
    by_slot = {segment["managed_slot"]: segment for segment in segments}

    assert set(by_slot) == {
        "wall_back",
        "wall_left",
        "wall_right",
        "wall_front_left",
        "wall_front_right",
        "door_header",
    }
    assert by_slot["wall_back"]["location"] == [7600.0, 6610.0, 150.0]
    assert by_slot["wall_left"]["location"] == [7390.0, 6400.0, 150.0]
    assert by_slot["wall_right"]["location"] == [7810.0, 6400.0, 150.0]
    assert by_slot["wall_front_left"]["location"] == [7460.0, 6190.0, 150.0]
    assert by_slot["wall_front_right"]["location"] == [7740.0, 6190.0, 150.0]
    assert by_slot["door_header"]["location"] == [7600.0, 6190.0, 260.0]
    assert by_slot["wall_back"]["scale"] == [4.0, 0.2, 3.0]
    assert by_slot["wall_front_left"]["scale"] == [1.2, 0.2, 3.0]
    assert by_slot["wall_front_right"]["scale"] == [1.2, 0.2, 3.0]
    assert by_slot["door_header"]["scale"] == [1.6, 0.2, 0.8]


def test_box_room_builder_butt_join_prevents_corner_overlap():
    segments = build_box_room_segments(
        BoxRoomSpec(
            zone_id="zone_box_room",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            inner_width_cm=400.0,
            inner_depth_cm=400.0,
            wall_height_cm=300.0,
            wall_thickness_cm=20.0,
            door_width_cm=140.0,
            door_height_cm=220.0,
            grid_snap_cm=10.0,
            corner_join_style="butt_join",
        )
    )
    by_slot = {segment["managed_slot"]: segment for segment in segments}

    def x_span(slot: str) -> tuple[float, float]:
        segment = by_slot[slot]
        width = segment["scale"][0] * 100.0
        center_x = segment["location"][0]
        return (center_x - (width / 2.0), center_x + (width / 2.0))

    left_wall_x = by_slot["wall_left"]["location"][0] + (by_slot["wall_left"]["scale"][0] * 100.0 / 2.0)
    right_wall_x = by_slot["wall_right"]["location"][0] - (by_slot["wall_right"]["scale"][0] * 100.0 / 2.0)

    back_min_x, back_max_x = x_span("wall_back")
    front_left_min_x, front_left_max_x = x_span("wall_front_left")
    front_right_min_x, front_right_max_x = x_span("wall_front_right")
    header_min_x, header_max_x = x_span("door_header")

    assert back_min_x == left_wall_x
    assert back_max_x == right_wall_x
    assert front_left_min_x >= left_wall_x
    assert front_right_max_x <= right_wall_x
    assert front_left_max_x <= header_min_x
    assert front_right_min_x >= header_max_x
    assert front_left_min_x == left_wall_x
    assert front_right_max_x == right_wall_x
    assert front_left_max_x == header_min_x
    assert front_right_min_x == header_max_x


def test_box_room_actions_share_managed_contract():
    actions = build_box_room_actions(
        BoxRoomSpec(
            zone_id="zone_box_room",
            center_x=0.0,
            center_y=0.0,
            support_z=0.0,
            support_actor_label="GridPlane4",
            parent_support_actor="GridPlane4",
        )
    )

    assert len(actions) == 6
    assert all(action["action"] == "place_asset" for action in actions)
    assert all(action["identity_policy"] == "reuse_or_create" for action in actions)
    assert all(action["placement_hint"]["support_actor_label"] == "GridPlane4" for action in actions)
    assert all(action["placement_hint"]["support_reference_policy"] == "explicit_only" for action in actions)


def test_place_asset_defaults_to_interference_avoidance(tmp_path: Path):
    scene_state = make_enriched_floor_scene(tmp_path)

    normalized = normalize_action_payload(
        action_payload={
            "action": "place_asset",
            "target_zone": "zone_0001",
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        },
        scene_state=scene_state,
        dirty_zone={"bounds": scene_state.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )

    hint = dict(normalized.get("placement_hint") or {})
    assert hint["interference_policy"] == "avoid"
    assert hint["duplicate_policy"] == "cleanup_managed"


def test_reposition_defaults_to_allowing_manual_overlap_preservation(tmp_path: Path):
    scene_state = make_enriched_floor_scene(tmp_path)

    normalized = normalize_action_payload(
        action_payload={
            "action": "move_actor",
            "target_zone": "zone_0001",
            "transform": {
                "location": [900.0, 900.0, 450.0],
                "rotation": [12.0, 20.0, 30.0],
                "scale": [1.1, 0.9, 1.0],
            },
        },
        scene_state=scene_state,
        dirty_zone={"bounds": scene_state.get("dirty_bounds", {})},
        asset_record=make_floor_asset_record(),
    )

    hint = dict(normalized.get("placement_hint") or {})
    assert hint["placement_phase"] == "reposition"
    assert hint["interference_policy"] == "allow"
    assert hint["duplicate_policy"] == "reuse"


def test_detect_actor_conflicts_ignores_support_actor_but_finds_duplicates_and_overlap():
    support_reference = {
        "support_surface_kind": "upper_slab",
        "support_actor_label": "GridPlane4",
    }
    active_actor = make_actor(
        label="ManagedBox",
        class_name="StaticMeshActor",
        location=[0.0, 0.0, 100.0],
        extent=[50.0, 50.0, 50.0],
        asset_path="/Game/Props/SM_Box",
    )
    support_actor = make_actor(
        label="GridPlane4",
        class_name="GridPlane_C",
        location=[0.0, 0.0, 0.0],
        extent=[500.0, 500.0, 10.0],
        asset_path="/Game/Environment/GridPlane",
    )
    duplicate_actor = make_actor(
        label="ManagedBox",
        class_name="StaticMeshActor",
        location=[0.0, 0.0, 100.0],
        extent=[50.0, 50.0, 50.0],
        asset_path="/Game/Props/SM_Box",
    )
    duplicate_actor["actor_path"] = "/Game/Test/ManagedBoxDuplicate"
    blocking_actor = make_actor(
        label="BlockingCrate",
        class_name="StaticMeshActor",
        location=[30.0, 0.0, 100.0],
        extent=[50.0, 50.0, 50.0],
        asset_path="/Game/Props/SM_Crate",
    )

    conflicts = detect_actor_conflicts(
        active_actor,
        [support_actor, duplicate_actor, blocking_actor],
        ignore_actor_paths={str(active_actor.get("actor_path"))},
        support_reference=support_reference,
    )

    assert conflicts["blocking_interference_count"] == 1
    assert conflicts["duplicate_count"] == 1
    assert conflicts["blocking_overlaps"][0]["actor_label"] == "BlockingCrate"
    assert conflicts["duplicates"][0]["actor_label"] == "ManagedBox"


def test_detect_actor_conflicts_flags_incompatible_wall_support_for_floor_asset():
    active_actor = make_actor(
        label="ManagedBeacon",
        class_name="StaticMeshActor",
        location=[0.0, 0.0, 210.0],
        extent=[25.0, 25.0, 10.0],
        asset_path="/Game/Props/SM_Beacon",
    )
    wall_actor = make_actor(
        label="SelectedWall",
        class_name="StaticMeshActor",
        location=[0.0, 0.0, 100.0],
        extent=[10.0, 150.0, 100.0],
        asset_path="/Game/Environment/WallPanel",
    )

    conflicts = detect_actor_conflicts(
        active_actor,
        [wall_actor],
        ignore_actor_paths={str(active_actor.get("actor_path"))},
        support_reference={},
        mount_type="floor",
    )

    assert conflicts["support_mismatch"] is True
    assert conflicts["support_contact"]["support_surface_kind"] == "wall_surface"
    assert conflicts["support_compatibility"] == "incompatible"


def test_find_non_interfering_location_finds_nearby_free_spot():
    active_actor = make_actor(
        label="ManagedBox",
        class_name="StaticMeshActor",
        location=[0.0, 0.0, 100.0],
        extent=[50.0, 50.0, 50.0],
        asset_path="/Game/Props/SM_Box",
    )
    blocking_actor = make_actor(
        label="BlockingCrate",
        class_name="StaticMeshActor",
        location=[0.0, 0.0, 100.0],
        extent=[50.0, 50.0, 50.0],
        asset_path="/Game/Props/SM_Crate",
    )

    candidate = find_non_interfering_location(
        active_actor,
        [blocking_actor],
        requested_location=[0.0, 0.0, 100.0],
        support_z=100.0,
        grid_cm=100.0,
        ignore_actor_paths={str(active_actor.get("actor_path"))},
        support_reference={},
    )

    assert candidate is not None
    assert candidate["location"] != [0.0, 0.0, 100.0]
    assert candidate["conflicts"]["blocking_interference_count"] == 0


def test_validate_placement_interference_reports_real_overlap():
    result = validate_placement_interference(
        scene_state={
            "active_actor": {
                "interference_report": {
                    "interference_policy": "avoid",
                    "blocking_interference_count": 2,
                    "duplicate_count": 0,
                    "blocking_overlaps": [{"actor_label": "WallA"}, {"actor_label": "WallB"}],
                    "duplicates": [],
                    "interference_status": "blocked",
                }
            }
        },
        action={
            "placement_hint": {
                "placement_phase": "initial_place",
                "interference_policy": "avoid",
            }
        },
        enabled=True,
        fail_hard=True,
    )

    assert result["passed"] is False
    assert "blocking overlap" in result["issues"][0]


def test_validate_placement_interference_reports_incompatible_support():
    result = validate_placement_interference(
        scene_state={
            "active_actor": {
                "interference_report": {
                    "interference_policy": "avoid",
                    "blocking_interference_count": 0,
                    "duplicate_count": 0,
                    "support_occupancy_count": 0,
                    "support_mismatch": True,
                    "expected_mount_type": "floor",
                    "support_contact": {"support_surface_kind": "wall_surface"},
                    "interference_status": "support_mismatch",
                }
            }
        },
        action={
            "placement_hint": {
                "placement_phase": "initial_place",
                "interference_policy": "avoid",
            }
        },
        enabled=True,
        fail_hard=True,
    )

    assert result["passed"] is False
    assert any("incompatible support" in issue for issue in result["issues"])
