# Architecture

## Overview

`unreal-codex-agent` is now a local-first UEFN co-editor scaffold.

The system is built around six connected layers:

1. **Codex / agent layer**
2. **UEFN + Verse runtime bridge**
3. **Asset AI layer**
4. **Capture service**
5. **Validation layer**
6. **Orchestrator**

The goal is to let an AI-assisted workflow plan, review, and export island edits safely for UEFN projects without relying on unsupported Unreal Python remote-execution assumptions.

## Core principle

UEFN is always the source of truth.

The agent should never rely only on memory.
Every cycle should re-check current scene state, current asset options, and current visual evidence before deciding what to do next.

## Layer breakdown

### 1. Codex / agent layer

This is the planning and review brain.

Responsibilities:
- interpret the user's build goal
- choose assets from trusted shortlists
- decide what action to take next
- review the result of each edit
- decide whether to keep, revise, replace, undo, or continue

### 2. UEFN + Verse runtime bridge

This is the supported handoff layer.

Responsibilities:
- read exported scene state from the UEFN project workflow
- export placement intents for Verse devices
- expose Fortnite-device and Scene Graph constraints to the planner
- keep the runtime contract tied to supported UEFN workflows

This layer is intentionally different from a desktop Unreal Python bridge.
The local scaffold plans and exports; island behavior is authored through Verse devices, Fortnite devices, and Scene Graph.

### 3. Asset AI layer

This is the asset memory and trust system.

Responsibilities:
- scan the asset library
- build a clean catalog
- infer tags for messy or weakly named assets
- measure trusted dimensions
- assign safe scale limits
- compute trust scores
- quarantine bad assets
- return shortlists for runtime placement

### 4. Capture service

This is the visual inspection layer.

Responsibilities:
- detect dirty zones after edits
- decide which views are needed
- generate multi-angle image packets
- handle shell-sensitive inside/outside review
- save packets for debugging and history

### 5. Validation layer

This is the rule-checking layer.

Responsibilities:
- enforce scale sanity
- enforce clearance rules
- enforce shell alignment when relevant
- enforce room-fit rules
- enforce asset-trust rules
- block false completion

### 6. Orchestrator

This is the control loop.

Responsibilities:
- start and manage sessions
- run the asset index when needed
- read scene state
- request capture packets
- ask Codex for decisions
- export Verse/device intents
- run validation
- score outcomes
- decide whether to keep iterating

## High-level runtime cycle

The normal runtime loop is:

1. read current scene state
2. identify the dirty zone
3. request an asset shortlist if needed
4. request a capture packet
5. send scene packet + images + context to Codex
6. receive a structured decision
7. export a UEFN placement/device intent
8. recapture or re-import the dirty zone evidence
9. run validators
10. score the result
11. keep, revise, replace, undo, or continue

## Dirty zone concept

A dirty zone is the area that must be re-reviewed after an edit.

A dirty zone usually includes:
- the edited entity or device-driven set piece
- nearby affected actors or props
- the containing room or sub-zone
- inside/outside views if the edit touches the shell

## Runtime handoff concept

The local scaffold exports:
- structured JSON placement intents
- cycle manifests
- generated Verse starter files

The UEFN project owns:
- Verse logic
- Fortnite device bindings
- Scene Graph entities and components
- project-specific placement and gameplay outcomes

## Design constraints

This system is designed to avoid:

- Unreal Python remote execution as the main control path
- one-angle scene review
- unrestricted asset placement
- unrestricted scaling
- blind asset selection from raw folder names
- false completion based on a single screenshot

## v1 boundaries

The first UEFN-first version focuses on:

- local orchestrator
- trusted asset indexing
- structured shortlists
- dirty-zone capture packets
- basic validator rules
- Verse/device export scaffolding
- simple keep / revise / undo loop
