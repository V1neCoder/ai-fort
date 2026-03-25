# UEFN TOOLBELT — Project Setup Demo
# ====================================
# Run this in the UEFN Python REPL (Output Log > Python (REPL) tab)
# to see the full AI project setup workflow live.
#
# Prerequisites:
#   1. UEFN is open with any level loaded
#   2. UEFN Toolbelt is installed (Content/Python/ contains UEFN_Toolbelt/)
#   3. Run the nuclear reload if you just installed:
#      import sys; [sys.modules.pop(k) for k in list(sys.modules) if "UEFN_Toolbelt" in k]; import UEFN_Toolbelt as tb; tb.register_all_tools(); tb.launch_qt()
#
# Then paste each block below into the REPL one at a time.
# Each block must complete before running the next (Quirk #22).

import UEFN_Toolbelt as tb

# ------------------------------------------------------------------
# STEP 1 — Scaffold the project + deploy Verse game manager
#
# What happens:
#   - Creates 56 professional folders in Content Browser
#     (/Game/MyGame/Maps, /Meshes, /Materials, /Verse, etc.)
#   - Generates a wired MyGameManager Verse device skeleton
#   - Deploys it directly to your project's Verse directory
#
# Run this first. Wait for it to return before step 2.
# ------------------------------------------------------------------
result = tb.run("project_setup", project_name="MyGame")
print("Verse file:", result.get("verse_path"))
print("Next steps:", result.get("next_steps"))


# ------------------------------------------------------------------
# STEP 2 — Spawn a symmetrical Red vs Blue arena
#
# What happens:
#   - Places 493 actors in the viewport (floor tiles, walls, platform)
#   - Red spawn cluster at X+ / Blue spawn cluster at X-
#   - Fully undoable with Ctrl+Z
#
# Run AFTER step 1 returns. Separate call required (Quirk #22).
# ------------------------------------------------------------------
result = tb.run("arena_generate", size="medium")
print(f"Arena: {result.get('placed')} actors placed")
print(f"  Red spawns: {result.get('red_spawns')}")
print(f"  Blue spawns: {result.get('blue_spawns')}")


# ------------------------------------------------------------------
# STEP 3 — Build Verse (one manual click)
#
# In UEFN: Verse menu -> Build Verse Code
# Wait for the build to complete, then run step 4.
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# STEP 4 — Close the error loop
#
# Reads the build log, extracts any errors, returns file content
# so Claude (or you) can fix and redeploy in one shot.
# If the build succeeded, returns build_status: SUCCESS.
# ------------------------------------------------------------------
result = tb.run("verse_patch_errors")
print("Build status:", result.get("build_status"))
print("Errors:", result.get("error_count"))
if result.get("errors"):
    for e in result["errors"]:
        print(f"  Line {e['line']}: {e['message']}")
