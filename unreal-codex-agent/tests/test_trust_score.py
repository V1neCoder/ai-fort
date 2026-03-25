from apps.asset_ai.quarantine import evaluate_quarantine
from apps.asset_ai.trust_score import enrich_record


ROOM_TAXONOMY = {
    "aliases": {
        "living": "living_room",
        "bath": "bathroom",
    }
}

PLACEMENT_PROFILES = {
    "profiles": {
        "sofa_standard": {
            "allowed_surfaces": ["floor"],
            "min_front_clearance_cm": 60,
            "min_side_clearance_cm": 10,
            "min_back_clearance_cm": 3,
            "against_wall_ok": True,
            "corner_ok": True,
            "default_scale_policy": "tight",
        },
        "door_standard": {
            "allowed_surfaces": ["opening"],
            "shell_sensitive": True,
            "default_scale_policy": "locked",
        },
    }
}

CATEGORY_BASELINES = {
    "baselines": {
        "sofa_standard": {
            "category": "furniture",
            "function": "seating",
            "expected_dimensions_cm": {
                "width_min": 140,
                "width_max": 280,
                "depth_min": 70,
                "depth_max": 120,
                "height_min": 65,
                "height_max": 110,
            },
            "default_scale_limits": {
                "min": 0.92,
                "max": 1.08,
                "preferred": 1.0,
            },
        },
        "door_standard": {
            "category": "opening",
            "function": "access",
            "expected_dimensions_cm": {
                "width_min": 70,
                "width_max": 120,
                "depth_min": 3,
                "depth_max": 20,
                "height_min": 190,
                "height_max": 240,
            },
            "default_scale_limits": {
                "min": 1.0,
                "max": 1.0,
                "preferred": 1.0,
            },
        },
    }
}


def test_enrich_record_builds_high_trust_sofa_record():
    raw = {
        "asset_path": "/Game/Props/Furniture/SM_Modern_Sofa_A",
        "asset_name": "SM_Modern_Sofa_A",
        "asset_class": "StaticMesh",
        "dimensions_cm": {
            "width": 210.0,
            "depth": 90.0,
            "height": 82.0,
        },
        "collision_verified": True,
        "validator_passed": True,
    }

    record = enrich_record(
        raw=raw,
        room_taxonomy=ROOM_TAXONOMY,
        placement_profiles=PLACEMENT_PROFILES,
        category_baselines=CATEGORY_BASELINES,
    )

    assert record["tags"]["category"] == "furniture"
    assert "seating" in record["tags"]["function"]
    assert record["tags"]["mount_type"] == "floor"
    assert record["trust_score"] >= 85
    assert record["status"] == "approved"
    assert record["scale_limits"]["min"] == 0.92
    assert record["scale_limits"]["max"] == 1.08


def test_quarantine_marks_bad_door_record_as_quarantined():
    raw = {
        "asset_path": "/Game/Props/Doors/SM_Bad_Door_WrongScale",
        "asset_name": "SM_Bad_Door_WrongScale",
        "asset_class": "StaticMesh",
        "dimensions_cm": {
            "width": 18.0,
            "depth": 4.0,
            "height": 410.0,
        },
        "collision_verified": False,
        "validator_passed": False,
        "pivot_suspect": True,
    }

    record = enrich_record(
        raw=raw,
        room_taxonomy=ROOM_TAXONOMY,
        placement_profiles=PLACEMENT_PROFILES,
        category_baselines=CATEGORY_BASELINES,
    )
    assert record["status"] == "limited"
    assert record["trust_score"] < 75

    quarantined = evaluate_quarantine(record, min_trust=75)

    assert quarantined["tags"]["category"] == "opening"
    assert quarantined["tags"]["scale_policy"] == "locked"
    assert quarantined["status"] == "quarantined"
    assert quarantined["quarantine"]["is_quarantined"] is True
    assert quarantined["trust_score"] < 75
    assert len(quarantined["quarantine"]["reasons"]) > 0
