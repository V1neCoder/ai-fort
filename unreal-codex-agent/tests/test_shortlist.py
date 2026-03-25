from apps.asset_ai.shortlist import shortlist_assets


def make_record(
    *,
    asset_id: str,
    asset_path: str,
    trust_score: int,
    trust_level: str,
    status: str,
    room_types: list[str],
    function_names: list[str],
    styles: list[str],
    mount_type: str,
    width: float,
    depth: float,
) -> dict:
    return {
        "asset_id": asset_id,
        "asset_path": asset_path,
        "status": status,
        "trust_score": trust_score,
        "trust_level": trust_level,
        "tags": {
            "category": "furniture",
            "function": function_names,
            "room_types": room_types,
            "styles": styles,
            "mount_type": mount_type,
            "scale_policy": "tight",
        },
        "dimensions_cm": {
            "width": width,
            "depth": depth,
            "height": 80.0,
        },
        "scale_limits": {
            "min": 0.95,
            "max": 1.05,
            "preferred": 1.0,
        },
    }


def test_shortlist_filters_wrong_room_and_low_trust_assets():
    catalog = [
        make_record(
            asset_id="sofa_a",
            asset_path="/Game/Props/Furniture/SM_Sofa_A",
            trust_score=91,
            trust_level="high",
            status="approved",
            room_types=["living_room"],
            function_names=["seating"],
            styles=["modern"],
            mount_type="floor",
            width=210.0,
            depth=90.0,
        ),
        make_record(
            asset_id="sofa_b",
            asset_path="/Game/Props/Furniture/SM_Sofa_B",
            trust_score=88,
            trust_level="medium",
            status="limited",
            room_types=["living_room"],
            function_names=["seating"],
            styles=["modern"],
            mount_type="floor",
            width=205.0,
            depth=92.0,
        ),
        make_record(
            asset_id="chair_office",
            asset_path="/Game/Props/Furniture/SM_Chair_Office",
            trust_score=95,
            trust_level="high",
            status="approved",
            room_types=["office"],
            function_names=["seating"],
            styles=["modern"],
            mount_type="floor",
            width=55.0,
            depth=55.0,
        ),
        make_record(
            asset_id="sofa_quarantine",
            asset_path="/Game/Props/Furniture/SM_Sofa_Quarantine",
            trust_score=20,
            trust_level="low",
            status="quarantined",
            room_types=["living_room"],
            function_names=["seating"],
            styles=["modern"],
            mount_type="floor",
            width=210.0,
            depth=90.0,
        ),
    ]

    results = shortlist_assets(
        catalog=catalog,
        room_type="living_room",
        function_name="seating",
        mount_type="floor",
        style="modern",
        min_trust="high",
        room_dimensions={"width": 500.0, "depth": 400.0},
        limit=10,
    )

    assert len(results) == 1
    assert results[0]["asset_id"] == "sofa_a"


def test_shortlist_ranks_better_fitting_asset_higher():
    catalog = [
        make_record(
            asset_id="sofa_good_fit",
            asset_path="/Game/Props/Furniture/SM_Sofa_Good",
            trust_score=90,
            trust_level="high",
            status="approved",
            room_types=["living_room"],
            function_names=["seating"],
            styles=["modern"],
            mount_type="floor",
            width=220.0,
            depth=95.0,
        ),
        make_record(
            asset_id="sofa_too_large",
            asset_path="/Game/Props/Furniture/SM_Sofa_Large",
            trust_score=95,
            trust_level="high",
            status="approved",
            room_types=["living_room"],
            function_names=["seating"],
            styles=["modern"],
            mount_type="floor",
            width=470.0,
            depth=390.0,
        ),
    ]

    results = shortlist_assets(
        catalog=catalog,
        room_type="living_room",
        function_name="seating",
        mount_type="floor",
        style="modern",
        min_trust="high",
        room_dimensions={"width": 500.0, "depth": 400.0},
        limit=10,
    )

    assert len(results) == 2
    assert results[0]["asset_id"] == "sofa_good_fit"
    assert results[0]["placement_rank"] > results[1]["placement_rank"]
