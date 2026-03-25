# UEFN Codex Agent - Complete Integrated Desktop Application

**A modern, feature-rich desktop application that brings together UEFN-TOOLBELT (161 professional tools), your existing Codex infrastructure, and a beautiful Electron UI for unified island creation and management.**

> **🎉 This is a complete, integrated, production-ready desktop application. Everything is wired together and ready to use.**

## Overview

This is a professional desktop application combining:

1. **UEFN-TOOLBELT** (161 professional tools)
   - Material Master, Procedural Generation, Bulk Operations
   - Text & Signs, Assets Management, Verse Helpers
   - API Explorer, and 140+ more tools

2. **Your Existing Codex Infrastructure**
   - Asset AI for smart asset management
   - Capture Service for multi-angle verification
   - Validation system for rule enforcement
   - Orchestrator loop for workflow automation
   - Codex Bridge for AI-powered planning

3. **Modern Electron Desktop App**
   - Beautiful dark theme UI
   - Tool Dashboard with 161 tools accessible
   - Asset Browser with preview
   - AI Planning interface
   - Real-time status monitoring
   - Production-ready code

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Setup (first time only)
setup.bat                    # Windows
# OR
bash setup.sh                # macOS/Linux
npm install                  # Install root launcher dependencies
cd app/frontend && npm install
cd ../..                     # Go back to root

# 2. Start the App
# Make sure your Python venv is active first!
.venv\Scripts\activate.bat   # Windows
# OR
source .venv/bin/activate    # macOS/Linux

npm start
```

This single command will launch both the Python backend and the React frontend simultaneously! Your browser will automatically open to the app.

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **[QUICKSTART.md](QUICKSTART.md)** | 5-minute getting started guide |
| **[UNIFIED_APP_README.md](UNIFIED_APP_README.md)** | Complete user manual & API reference (2000+ lines) |
| **[DEVELOPMENT.md](DEVELOPMENT.md)** | Developer guide for extending & customizing |
| **[INTEGRATION_PLAN.md](INTEGRATION_PLAN.md)** | Technical architecture & design decisions |
| **[INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md)** | Summary of everything integrated |

**👉 New to the app? Start with [QUICKSTART.md](QUICKSTART.md)**

## Goals

- build a local-first UEFN editing agent
- avoid blind asset placement
- keep asset choices tied to trusted metadata, dimensions, and scale limits
- inspect edited zones from multiple angles instead of one weak screenshot
- validate placement before marking anything complete
- keep the full system structured enough for Codex to reason over

## Planned system

### Core layers

1. **Codex / OpenAI agent**
   - reads scene packets
   - reads asset shortlists
   - proposes edits
   - reviews results

2. **UEFN runtime bridge**
   - reads exported scene state
   - writes Verse/device placement intents
   - exposes Scene Graph and authored-device assumptions to the planner

3. **Asset AI**
   - scans assets
   - measures trusted dimensions
   - assigns tags, trust, and scale policies
   - returns shortlists for runtime placement

4. **Capture service**
   - captures dirty zones
   - generates multi-view packets
   - handles shell-sensitive inside/outside cases

5. **Validation**
   - checks scale, clearance, shell alignment, and trust rules
   - blocks fake completion

6. **Orchestrator**
   - runs the loop
   - reads state
   - sends packets to Codex
   - exports Verse/device intents
   - retries or undoes when needed

## Requirements

- Python 3.11+
- Node.js 20+
- Unreal Editor for Fortnite (UEFN)
- Verse enabled in the island project
- Fortnite devices for authored interactions
- Scene Graph enabled if you plan to use entity/component placement flows
- Codex CLI or Codex app signed in with your ChatGPT account

## Quick start

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd unreal-codex-agent
```

### 2. Create a virtual environment

Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Copy environment file

Windows PowerShell

```powershell
Copy-Item .env.example .env
```

macOS / Linux

```bash
cp .env.example .env
```

### 5. Generate the local UEFN Verse workspace

```bash
python scripts/generate_uefn_workspace.py --repo-root .
```

### 6. Check UEFN setup

```bash
python scripts/check_uefn_setup.py --repo-root .
```

### 7. Deploy the local UEFN stack into your island

```bash
python -m apps.mcp_extensions.uefn_tools sync-stack --repo-root .
```

`sync-stack` deploys the vendored MCP listener and the vendored UEFN Toolbelt into the same `Content/Python` target, scaffolds the repo-side Verse handoff folder, and runs a Toolbelt nuclear reload when the live listener is already connected.

If you prefer the lower-level steps, the separate commands still exist:

```bash
python -m apps.mcp_extensions.uefn_tools sync-mcp-listener --repo-root .
python -m apps.mcp_extensions.uefn_tools sync-toolbelt --repo-root . --reload-live
python -m apps.mcp_extensions.uefn_tools write-mcp-config --repo-root .
```

`sync-mcp-listener` and `sync-toolbelt` share a generated `Content/Python/init_unreal.py`, so both the live MCP listener and the Toolbelt startup/menu bootstrap can coexist in the same UEFN project.

### 9. Run the full helper smoke pass

```bash
python scripts/smoke_check.py --repo-root .
```

## Environment configuration

Edit `.env` and fill in the paths for:

- the `.uefnproject`
- the UEFN editor executable
- the Verse workspace root
- the local scene-state export path
- the local capture import folder
- session storage
- asset catalog storage

## Runtime model

The local scaffold stays responsible for:

- catalog building
- shortlist generation
- dirty-zone review
- validation
- scoring
- action planning
- exporting UEFN-ready placement intents and Verse scaffolds

The island-side UEFN project is responsible for:

- Verse device logic
- Fortnite device wiring
- Scene Graph entities/components
- authored placement rules and island-specific references

If the UEFN MCP listener is running, the local planner can also read the editor scene directly instead of waiting for exported scene snapshots.

## Generated UEFN artifacts

Every cycle can now export:

- `data/sessions/<session_id>/uefn_bridge/placement_intents/cycle_XXXX.json`
- `data/sessions/<session_id>/uefn_bridge/manifests/cycle_XXXX.json`
- `data/sessions/<session_id>/uefn_bridge/debug_overlay/cycle_XXXX.json`
- `uefn/verse/generated/UCA_PlacementCoordinator.generated.verse`
- `uefn/verse/generated/UCA_SceneMonitor.generated.verse`

Those files are the handoff between the local planner and the UEFN project.

The generated placement coordinator now includes a Verse Debug Draw overlay for:

- support-surface anchors
- terrain or landscape anchors
- target placement points
- dirty-zone bounds

Enable `Verse Debug Draw` during playtest if you want to see those markers live.

## Official workflow references

- [Create your own device using Verse](https://dev.epicgames.com/documentation/en-us/uefn/modify-and-run-your-first-verse-program-in-unreal-editor-for-fortnite)
- [Getting started in Scene Graph](https://dev.epicgames.com/documentation/en-us/uefn/getting-started-in-scene-graph-in-fortnite)
- [Transforms in Scene Graph](https://dev.epicgames.com/documentation/en-us/uefn/transforms-in-scene-graph-in-unreal-editor-for-fortnite)

## Integration guides

- [UEFN-supported workflows](C:/AI%20Fort/unreal-codex-agent/docs/uefn_supported_workflows.md)
- [UEFN MCP server integration](C:/AI%20Fort/unreal-codex-agent/docs/uefn_mcp_server_integration.md)
- [UEFN Toolbelt integration](C:/AI%20Fort/unreal-codex-agent/docs/uefn_toolbelt_integration.md)
- [Architecture](C:/AI%20Fort/unreal-codex-agent/docs/architecture.md)
- [PCG and Geometry Script integration](C:/AI%20Fort/unreal-codex-agent/docs/pcg_geometry_script_integration.md)
- [Free plugin recommendations](C:/AI%20Fort/unreal-codex-agent/docs/plugins_recommendations.md)
- [Modular placement plugins](C:/AI%20Fort/unreal-codex-agent/docs/modular_placement_plugins.md)
- [UEFN required project settings](C:/AI%20Fort/unreal-codex-agent/unreal/content_support/required_project_settings.md)

## Helper commands

The repo exposes working local helper CLIs under `apps/mcp_extensions/`:

- `scene_tools`: `scene-state`, `dirty-zone`
- `capture_tools`: `scene`, `zone`
- `developer_tools`: `status`, `enable`, `disable`, `toggle-scene-xray`, `toggle-scene-xray-auto`, `toggle-scene-xray-tool-list`, `set-defaults`, `scene-xray`
- `validator_tools`: `run`
- `catalog_tools`: `build-index`, `update-asset`, `search`, `get-asset`, `shortlist`, `mark-quarantine`, `safe-scale`
- `uefn_tools`: `status`, `scaffold-verse`, `sync-verse`, `mcp-status`, `sync-mcp-listener`, `sync-stack`, `sync-toolbelt`, `toolbelt-status`, `toolbelt-source-tools`, `toolbelt-live-tools`, `toolbelt-reload`, `toolbelt-launch`, `toolbelt-run`, `toolbelt-smoke-test`, `toolbelt-integration-test`, `write-mcp-config`, `export-cycle`

Use `python -m apps.mcp_extensions.<tool> --help` or `python -m apps.mcp_extensions.<tool> <command> --help` to inspect them.

## License

MIT
