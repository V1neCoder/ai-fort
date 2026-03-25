# Required Project Settings

## Purpose

These are the UEFN project and editor settings the scaffold expects before the local agent loop can work reliably.

This file is for setup, not for scene logic.

## Required UEFN features

### 1. Verse
This must be enabled and used as the scripting path.

Why:
- the repo is now built around Verse-authored devices
- generated cycle artifacts are exported for Verse/device handoff
- island-side logic should live in supported UEFN scripting workflows

### 2. Fortnite devices
These should be part of the authored island workflow.

Why:
- devices are part of the supported UEFN authoring model
- they are the safest way to wire gameplay-side reactions to exported placement intent

### 3. Scene Graph
Enable and use Scene Graph if your island will rely on entity/component placement workflows.

Why:
- Scene Graph is the official entity/component path in UEFN
- the local planner now carries Scene Graph assumptions through placement context and Verse scaffolds

## Recommended setup steps

### Enable Verse in the project
In UEFN:

- create at least one Verse device
- verify Verse scripts build successfully
- keep generated Verse files in a predictable folder

### Use Fortnite devices for authored control points
In UEFN:

- keep named devices for triggers, validation indicators, and placement gates
- use consistent device naming so the local planner can describe them clearly

### Enable Scene Graph when needed
In UEFN:

- keep Scene Graph enabled for entity/component placement flows
- treat it as a project choice, especially while it remains Beta

## Strongly recommended editor setup

### Keep your content organized
The asset indexer will work better if content is not dumped into random folders.

Recommended:
- group by category or space
- keep naming somewhat readable
- avoid giant mixed folders when possible

## Recommended project plugins and systems

### Verse Explorer and generated Verse folder discipline
Keep a clear generated Verse location that mirrors the repo scaffold:

- `uefn/verse/`
- `uefn/verse/generated/`

### Scene Graph
Use Scene Graph for structural and entity/component placement flows when your project needs them.

### Optional free-first references
These remain useful references around UEFN-adjacent workflows:
- PCG Framework
- Prefabricator as a reference for prefab thinking outside UEFN

These are part of the camera/capture side of the scaffold.

## Recommended content conventions

### Metadata
The asset pipeline works better if assets carry clean metadata tags in the local catalog.

The scaffold is designed to reason over tags like:
- category
- function
- room types
- mount type
- scale policy
- trust level
- trust score

### Trust and quarantine workflow
Do not assume every imported asset is safe for autonomous use.

The intended workflow is:
- index
- measure
- tag
- score
- quarantine weak assets
- only shortlist trusted assets at runtime

## Recommended save and safety workflow

Because the external control layer can make real editor changes:

- use version control
- save often
- keep review checkpoints
- do not trust fully autonomous edits without rollback support
- prefer grouped undo behavior for agent edits

## Minimum required setup checklist

Before trying the full scaffold, confirm:

- UEFN project opens correctly
- Verse scripts build successfully
- Fortnite devices are available in the island workflow
- Scene Graph is enabled if your project depends on entity/component placement
- the repo `uefn/verse/` folder exists
- the local export folder exists for scene-state and placement intent handoff

## Important practical note

The repo scaffold can run in placeholder mode even before every Unreal-side feature is fully wired.
But the real UEFN-backed workflow now depends on Verse/device wiring and consistent export/import contracts, not Unreal Python remote execution.
