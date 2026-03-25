# Modular Placement Plugins

## Priority Order

These are the highest-value free or built-in Unreal tools for fixing the kinds of placement failures that usually hit:

- corners
- roof modules
- shell openings
- snapped structural pieces
- modular facade sections

## 1. Built-in Transform and Snap Systems

Use these first.

- `STransformViewportToolBar`
- `UEditorInteractiveToolsContext::SetAbsoluteWorldSnappingEnabled`
- `UEditorEngine::SnapElementTo`
- `UModelingSceneSnappingManager`
- `FRaySpatialSnapSolver`
- `FPointPlanarSnapSolver`

Why this matters:

- these handle grid, axis, planar, vertex, and edge snapping
- they map directly to the failure modes for corners, walls, and roofs
- they are already part of Unreal, so they fit a free-first workflow

Best repo seam:

- `unreal/python/ue_apply_edit.py`
- future Unreal plugin work under `unreal/plugin/UCADeveloperTools`

## 2. Geometry Script

Official direction:

- use it for mesh analysis and editor tooling
- use it to inspect pivots, bounds, planar alignment, and modular edge conditions
- docs: [Geometry Scripting User Guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/geometry-scripting-users-guide-in-unreal-engine)
- docs: [Geometry Scripting Reference](https://dev.epicgames.com/documentation/en-us/unreal-engine/geometry-scripting-reference-in-unreal-engine)

Why it matters:

- good for building custom “is this really a corner piece / roof piece / opening piece” checks
- good for authoring custom mesh preprocessing tools

Best repo seam:

- `unreal/python/`
- `unreal/validators/`
- future mesh analysis utilities that support `apps/placement/placement_solver.py`

## 3. Procedural Content Generation Framework

Built-in Unreal plugin.

- docs: [Procedural Content Generation Framework](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-framework-in-unreal-engine)
- docs: [PCG Node Reference](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-framework-node-reference-in-unreal-engine)
- docs: [PCG Geometry Script Interop API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/PCGGeometryScriptInterop)

Why it matters:

- strong fit for repeated modular placement patterns
- especially useful for roofs, facade strips, repeated supports, and guided structural scatter

Best repo seam:

- `apps/capture_service/`
- `apps/orchestrator/main.py`
- future procedural building helpers that choose a modular family first and then a final asset

## 4. PCG Extended Toolkit

Free plugin:

- [PCG Extended Toolkit](https://nebukam.github.io/PCGExtendedToolkit/)

Why it matters:

- stronger spatial relationships than stock PCG alone
- useful for corners, intersections, path-aware layouts, graph-driven adjacency, and structural linking

Best repo seam:

- future PCG-heavy building workflows
- room shell graph generation
- structural edge and corner placement tools

## 5. Prefabricator

Free/open-source:

- [Prefabricator GitHub](https://github.com/coderespawn/prefabricator-ue4)
- [Prefabricator site](https://prefabricator.dev/)

Why it matters:

- helps treat modular assemblies as one reusable authored unit instead of many fragile single placements
- useful for corners, roof kits, trim assemblies, and repeated facade chunks

Best repo seam:

- asset catalog tagging
- shortlist selection
- Codex action selection when a prefab is safer than a single mesh

## Repo-side improvements already added

The local code now includes placement heuristics for:

- expected mount inference for floor, wall, opening, corner, ceiling, and roof
- yaw snapping for wall/opening/corner pieces
- pitch snapping for roof pieces
- grid snapping for shell and modular pieces
- uniform-scale enforcement for opening, corner, and roof modules
- roof and corner zone recognition in the dirty-zone detector

Main files:

- `apps/placement/placement_solver.py`
- `apps/orchestrator/main.py`
- `apps/mcp_extensions/scene_tools.py`
- `apps/validation/rules/room_fit.py`
- `unreal/python/ue_apply_edit.py`

## Best next Unreal-side step

If you want the next strongest real improvement inside Unreal itself:

1. use the built-in snapping APIs first
2. enable Geometry Script
3. enable PCG
4. add Prefabricator only when repeated assemblies are safer than per-asset placement
