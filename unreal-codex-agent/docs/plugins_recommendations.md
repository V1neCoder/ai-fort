# Plugin Recommendations

## Priority rule

This repo should prioritize free or built-in Unreal options first.

Recommended order:

1. built-in Unreal plugins and systems
2. free open-source plugins
3. paid marketplace tools only when they solve a real missing capability

## Best free priorities for this repo

### 1. UEFN + Verse + Fortnite devices + Scene Graph

Primary fit for:

- supported scripting workflows
- authored island behaviors
- Scene Graph entity/component structure
- exported placement-intent handoff

Why it is prioritized:

- free
- officially supported by UEFN
- now matches the architecture in this repo

### 2. Unreal PCG Framework

Primary fit for:

- procedural placement
- asset distribution
- graph-driven layout helpers
- room dressing assists

Why it is prioritized:

- built into Unreal
- no extra paid dependency
- useful for future room layout and asset clustering workflows

### 3. Geometry Script

Primary fit for:

- geometry-aware editor tooling
- footprint extraction
- dimension and surface analysis
- custom building and placement utilities

Why it is prioritized:

- built into Unreal as a plugin
- strong fit for placement reasoning and structural helpers

### 4. UnrealValidationFramework

Primary fit for:

- Unreal-native validation reporting
- project-side validation extension
- editor-driven report export

Why it is prioritized:

- free
- aligns with the validation-heavy architecture in this repo

Reference:

- [Netflix-Skunkworks/UnrealValidationFramework](https://github.com/Netflix-Skunkworks/UnrealValidationFramework)

### 5. Prefabricator UE5

Primary fit for:

- prefab-driven structural placement
- doorway kits
- roof chunks
- corner assemblies

Why it is useful:

- free
- directly reduces transform drift by letting you place one authored assembly at a known pivot
- strong match for the corner and roof problems in this repo

Reference:

- [unknownworlds/prefabricator-ue5](https://github.com/unknownworlds/prefabricator-ue5)

### 6. PCG Extended Toolkit

Primary fit for:

- richer PCG graph operations
- more advanced placement relationships
- procedural layout logic beyond the stock PCG set

Why it is useful:

- free
- extends the built-in PCG path instead of replacing it

Reference:

- [PCG Extended Toolkit](https://github.com/Nebukam/PCGExtendedToolkit)

## Useful but lower priority

### UnrealImageCapture

Primary fit:

- real image generation backend

Why it is not first:

- stronger Unreal/C++ integration cost
- better treated as an implementation reference than a drop-in

Reference:

- [TimmHess/UnrealImageCapture](https://github.com/TimmHess/UnrealImageCapture)

### Dungeon Architect

Primary fit:

- layout generation
- room graph assembly

Why it is secondary:

- stronger generator-level system, not a first integration for this repo

## What this repo should implement first

### For building and placement

- use trusted asset shortlists
- add PCG and Geometry Script guidance into Unreal-side planning
- keep capture and validation as the safety loop

### For placement quality

- use room-aware shortlists
- use scale and clearance validation
- use capture packets with multi-angle review

### For procedural building

- treat PCG and Geometry Script as the first free upgrade path
- only move to heavier external systems when the built-in stack is insufficient

## Practical recommendation

If you want the strongest free stack for this repo, use:

- UEFN + Verse
- Fortnite devices
- Scene Graph
- Unreal PCG Framework
- Geometry Script
- optional PCG Extended Toolkit

That gives you supported UEFN runtime workflows, procedural placement help, and geometry-aware tooling without forcing paid tools into the core path.
