# 🗺️ UEFN Schema Explorer: The High-Fidelity API Guide

This document "dissects" the **1.6MB Reference Schema** (`uefn_reference_schema.json`) for engineers and creators. It translates the raw JSON data into actionable knowledge for building smarter UEFN automation.

---

## 📊 The "Big Picture" Stats

- **Total Discoverable Classes**: 14 (Unique classes found in the level context)
- **Total UPROPERTIES**: 1,031 (Boolean switches, Floats, Vectors, etc.)
- **Total Discoverable Methods**: 3,485 (Functions accessible via Python/Verse)

### Top 5 Property-Heavy Classes
| Class | Properties | Why it matters |
| :--- | :--- | :--- |
| `BuildingProp` | 149 | The base of all placement logic. |
| `FortCreativeDeviceProp` | 149 | The gatekeeper to Verse logic. |
| `BuildingFloor` | 144 | Critical for grid-snapping and voxelization. |
| `FortMinigameSettingsBuilding` | 72 | Controls Game Settings in-session. |
| `FortPlayerStartCreative` | 59 | Essential for spawn-point automation. |

---

## 🧠 For Engineers: How to use the Schema

### 1. Zero-Friction Property Access
The Toolbelt uses `schema_utils.py` to validate your scripts at runtime.
```python
from UEFN_Toolbelt import schema_utils

# Check if a property exists and is readable
res = schema_utils.validate_property("Actor", "actor_guid")
if res["exists"] and res["meta"]["readable"]:
    # Safe to use!
```

### 2. Multi-Component Discovery
The schema reveals that an "Actor" is more than just its label. You can now target:
- **`BillboardComponent`**: For icon scaling/visibility.
- **`DecalComponent`**: For universal material painting.
- **`SkeletalMeshComponent`**: For 1.6MB accurate character rigging.

### 3. Read-Only Guards
Stop hunting for silent failures. The schema marks properties like `_wrapper_meta_data` as `readable: false`, so our tools can warn you *before* the crash.

---

## 🎨 For Non-Technical Creators

**"How does this make my AI smarter?"**
By "feeding" this schema into an AI (like Claude or Antigravity), the AI stops guessing. It knows the **exact** name of the setting you want to change (e.g., `bIsEnabled` instead of `IsActive`).

**One-Click Brain Sync**:
Every time you add a new Verse device, use the **"Sync Level Schema to AI"** button in the Dashboard. It updates your local documentation instantly.

---

---
 
 ## 🛤️ Simulation & Sequences (Phase 19 COMPLETE)
 
 Phase 19 has successfully operationalized the schema with:
 - **Simulation Proxies**: Python handlers generated directly from schema method discovery.
 - **Named Auto-Link**: Robust fuzzy resolution that maps viewport actors to Verse classes when the formal API is invisible.
 - **Sequencer Automation**: One-click level sequence generation for any schema-validated actor.
 
 > [!IMPORTANT]
 > For a deep dive into the technical hurdles overcome in this phase, see **[docs/UEFN_QUIRKS.md](docs/UEFN_QUIRKS.md)**.
