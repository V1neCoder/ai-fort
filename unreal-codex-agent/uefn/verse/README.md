# UEFN Verse Scaffold

This folder is the repo-side handoff point for UEFN-first workflows.

Generated files under `generated/` are rewritten by the local orchestrator.
Review them in UEFN, wire them to Fortnite devices or Scene Graph entities,
and replace placeholder logic with project-specific Verse behavior.

Expected flow:

1. Run the local orchestrator.
2. Inspect `data/sessions/<session_id>/uefn_bridge/` for cycle manifests and intents.
3. Run `python -m apps.mcp_extensions.uefn_tools sync-verse --repo-root .` to copy generated Verse into the island Content folder.
4. Compile Verse in UEFN and bind the devices to your island setup.
5. Enable Verse Debug Draw during playtest if you want to see live placement markers.
