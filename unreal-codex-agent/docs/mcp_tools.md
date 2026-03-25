# MCP Tools

## Purpose

This document explains the tool categories the system expects from the UEFN runtime bridge and from local extensions.

The bridge layer is the state and handoff bridge between Codex and the UEFN project workflow.

## Tool groups

The system is easiest to reason about when tools are grouped by purpose.

### 1. Scene-state tools
These read the current state of the island or exported scene snapshot.

Examples:
- get current island or map info
- get exported entity state
- get actor or prop transforms
- get authored device state
- get current validation state

### 2. Asset tools
These read project asset information.

Examples:
- list assets
- search assets
- get asset info
- get asset references
- get asset metadata

### 3. Intent/export tools
These prepare changes for the UEFN project.

Examples:
- export placement intent
- export Verse/device scaffold
- export cycle manifest
- refresh generated Verse files

### 4. Capture tools
These create image evidence for review.

Examples:
- capture dirty zone
- capture shell cross-check views
- capture close-up packet
- capture room packet
- capture cube-style surround packet

### 5. Validation tools
These run or return validator information.

Examples:
- run zone validators
- get last validation report
- check trust gate
- check scale sanity
- check shell alignment

### 6. Catalog tools
These are local extensions that sit on top of the Asset AI catalog.

Examples:
- build full catalog index
- update one asset
- query catalog
- get catalog record
- get shortlist
- mark asset quarantined
- get safe scale limits

## Minimum useful tool set

A v1 setup should have at least:

### Scene/state
- `scene_state_export_get_latest`
- `scene_graph_get_entities`

### Assets
- `editor_list_assets`
- `editor_search_assets`
- `editor_get_asset_info`

### Intents
- `export_placement_intent`
- `export_verse_scaffold`
- `export_cycle_manifest`

### Review support
- `capture_dirty_zone_packet`
- `capture_shell_crosscheck_packet`
- validator execution via local rules or exported reports

## Expected local extension tools

The repo also expects custom MCP-side helper tools such as:

- `catalog_build_full_index`
- `catalog_update_asset`
- `catalog_query`
- `catalog_get_record`
- `catalog_get_shortlist`
- `catalog_mark_quarantine`
- `catalog_get_safe_scale`

These are repo-specific extensions or helper wrappers.

## Current helper command map

The local helper CLIs currently wired into this repo are:

### `apps.mcp_extensions.scene_tools`
- `scene-state`
- `dirty-zone`

### `apps.mcp_extensions.capture_tools`
- `scene`
- `zone`

### `apps.mcp_extensions.developer_tools`
- `status`
- `enable`
- `disable`
- `toggle-scene-xray`
- `toggle-scene-xray-auto`
- `toggle-scene-xray-tool-list`
- `set-defaults`
- `scene-xray`

### `apps.mcp_extensions.validator_tools`
- `run`

### `apps.mcp_extensions.catalog_tools`
- `build-index`
- `update-asset`
- `search`
- `get-asset`
- `shortlist`
- `mark-quarantine`
- `safe-scale`

### `apps.mcp_extensions.uefn_tools`
- `status`
- `scaffold-verse`
- `export-cycle`

### Repeatable verification

Run:

`python scripts/smoke_check.py --repo-root .`

This exercises the helper CLIs, orchestrator lifecycle, UEFN scaffold exports, and launcher scripts in one pass.

## Recommended tool behavior

### Read tools
Should be:
- safe
- deterministic
- structured
- fast enough for repeated calls

### Write tools
Should be:
- explicit
- scoped
- undo-friendly
- logged

### Capture tools
Should be:
- tied to a zone
- consistent in naming
- reusable across review passes

### Validation tools
Should return:
- pass/fail state
- blocking issues
- warnings
- next-action hints when possible

## Tool design rule

The AI should use high-level safe tools when possible.

Prefer:
- `catalog_get_shortlist`
- `capture_dirty_zone_packet`
- `run_zone_validators`

over:
- raw broad scans
- raw ad hoc screenshot spam
- unrestricted unsafe actor editing

## Logging

Every write action should be logged into session history.

Useful fields:
- action type
- target actor or zone
- parameters
- timestamp
- result
- related score or validator report if available

## Tool failure behavior

If a tool fails:
- do not continue as if it succeeded
- refresh state if needed
- retry only when the failure is likely transient
- prefer no-op over unsafe assumptions

## Tool philosophy

MCP tools are how the system stays real.

Codex thinks.
Bridge tools export.
Validators verify.
The orchestrator connects the loop.
