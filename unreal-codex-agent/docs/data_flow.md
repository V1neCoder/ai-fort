# Data Flow

## Purpose

This document explains how data moves through the system from startup to repeated scene-editing cycles in the UEFN-first architecture.

The goal is to make every stage of the repo easy to reason about and debug.

## Main data objects

The system passes around a few important data objects:

- **asset record**
- **asset shortlist**
- **scene state**
- **dirty zone**
- **capture packet**
- **validation report**
- **decision payload**
- **score record**
- **completion state**

## Startup flow

### 1. Config load

The orchestrator loads:

- `config/project.json`
- `config/room_taxonomy.json`
- `config/tag_dictionary.json`
- `config/placement_profiles.json`
- `config/category_baselines.json`
- `config/capture_profiles.json`
- `config/validator_rules.json`
- `config/codex_prompts/*.md`

These become the working rules for the session.

### 2. Asset catalog check

The orchestrator checks whether the catalog exists and whether a rebuild is required.

Possible outcomes:
- use existing catalog
- run full index
- run incremental update

### 3. Session creation

A session folder is created under `data/sessions/<session_id>/`.

This folder should hold:
- scene state snapshots
- image packets
- action history
- score history
- completion state

## Asset indexing flow

### 1. Registry scan

Input:
- raw asset inventory exports
- config filters

Output:
- raw asset records

Each raw asset record should include:
- asset path
- package path
- asset name
- asset class
- raw tags if available

### 2. Metadata enrichment

Input:
- raw asset records
- tag dictionary
- room taxonomy
- category baselines

Output:
- enriched asset records

The indexer should assign:
- category
- function
- room types
- styles
- mount type
- scale policy
- clearance profile
- shell-sensitive flag

### 3. Dimension measurement

Input:
- enriched asset records
- validation map tools

Output:
- asset records with trusted dimensions and scale limits

This stage should:
- load or spawn the asset when needed
- measure bounds
- compare to baseline ranges
- assign scale limits

### 4. Preview generation

Input:
- measured asset records

Output:
- preview images and preview paths

### 5. Trust scoring

Input:
- asset records with tags, dimensions, previews, and quality flags

Output:
- trust score
- trust level
- status

### 6. Metadata write-back or catalog-side persistence

Input:
- final asset record

Output:
- local metadata contract written back where supported

### 7. Catalog store

Output:
- SQLite catalog
- JSONL export
- quarantine JSONL

## Runtime scene-editing flow

### 1. Build goal intake

Input:
- user build goal

Output:
- session goal state

The orchestrator stores:
- goal text
- target room or zone if known
- style intent if known
- function targets if known

### 2. Scene-state read

Input:
- UEFN scene-state export contract

Output:
- `scene_state.json`

Typical scene-state data should include:
- current map
- exported entity or prop state
- transforms
- tags
- touched actor IDs
- room or zone mapping if available
- validation warnings if available

### 3. Dirty zone generation

Input:
- latest edit or touched actors
- scene state
- room mapping
- shell-sensitive hints

Output:
- dirty zone object

A dirty zone should include:
- zone ID
- actor IDs
- zone type
- room type
- shell-sensitive flag
- bounding box or approximate bounds

### 4. Shortlist generation

Input:
- dirty zone
- scene goal
- room type
- asset catalog

Output:
- shortlist of approved or limited candidate assets

The shortlist should already respect:
- trust threshold
- room type
- function
- mount type
- size fit
- style fit if available

### 5. Capture packet generation

Input:
- dirty zone
- scene state
- capture profile

Output:
- `capture_packet.json`
- image files

A capture packet should include:
- zone ID
- image paths
- image labels
- capture profile used
- shell cross-check flag
- timestamp

### 6. Prompt packet build

Input:
- build goal
- scene state
- dirty zone
- shortlist if needed
- validation report if present
- score history
- capture packet

Output:
- Codex request payload

### 7. Codex decision

Input:
- prompt packet

Output:
- structured decision payload

Examples:
- select asset
- place asset
- move actor
- rotate actor
- revise placement
- request more views
- undo
- mark incomplete

### 8. UEFN intent export

Input:
- decision payload

Output:
- placement intent JSON
- generated Verse/device scaffold updates

### 9. Post-edit state refresh

Input:
- latest scene state
- latest capture packet
- latest validator results

Output:
- post-edit evaluation packet

### 10. Validation run

Input:
- dirty zone
- scene state
- validator rules

Output:
- `validation_report.json`

### 11. Score update

Input:
- Codex review
- validator report
- scene-state fit
- completion signals

Output:
- `score_record.json`

### 12. Completion gate

Input:
- current zone packet
- score record
- validator report
- unresolved issues

Output:
- zone completion decision

## Storage flow

### Asset catalog storage

Persistent:
- `data/catalog/asset_catalog.sqlite`
- `data/catalog/asset_catalog.jsonl`
- `data/catalog/quarantine.jsonl`

### Session storage

Per-session:
- image packets
- scene state snapshots
- action history
- score history
- completion state

## Failure handling flow

If a step fails:

### Asset indexing failure
- mark asset as limited or quarantined
- continue indexing others

### Capture packet failure
- request recapture
- do not guess from missing evidence

### Codex parse failure
- retry with stricter schema prompt
- if repeated, fall back to no-op

### Validator failure
- mark zone blocked or incomplete
- prefer revise or undo

### Scene-state mismatch
- refresh scene state before continuing

## Data flow rule

The system should always prefer:

1. fresh scene state
2. trusted catalog data
3. multi-view evidence
4. validator results

over:
- raw memory
- raw names
- one-angle guesses
- stale packets
