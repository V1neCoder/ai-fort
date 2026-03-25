# Prefabricator UE5 Integration

This is reference-only for the repo's UEFN-first architecture.
Use it only as a desktop Unreal structural-placement reference workflow, not as a required UEFN runtime dependency.

## Why this plugin

For the specific failure mode in this repo, Prefabricator UE5 is one of the strongest free adds because it lets you place a stable modular assembly instead of many fragile single actors.

That matters most for:

- roof kits
- corner assemblies
- doorway or opening frames
- facade chunks
- repeated trim groups

The UE5 fork to use is:

- [unknownworlds/prefabricator-ue5](https://github.com/unknownworlds/prefabricator-ue5)

## Why it fits this repo

This repo already has:

- mount-type inference
- structural placement snapping
- shell-aware validation
- shortlist ranking

Prefabricator complements that by reducing the number of per-actor transforms that have to be perfect.

Instead of:

- place wall piece
- place trim piece
- place corner piece
- place roof edge piece

you can often:

- place one prefab assembly at the correct anchor

## Best use in this repo

Use Prefabricator first for:

- `opening`
- `corner`
- `roof`

Those are also the mount families the repo now prefers for prefab ranking.

## Repo-side support already added

The repo now recognizes prefab-oriented assets through:

- `tags.is_prefab`
- `tags.prefab_family`
- `placement_behavior` including `prefab_anchor_driven`

Relevant files:

- `apps/integrations/prefabricator.py`
- `apps/asset_ai/trust_score.py`
- `apps/asset_ai/shortlist.py`
- `apps/codex_bridge/prompt_builder.py`
- `config/project.json`

## Installation

Only use this for a desktop Unreal reference project, not for the primary UEFN island workflow.

Windows PowerShell:

```powershell
.\scripts\install_prefabricator_ue5.ps1 -UnrealProjectPath "C:\Path\To\Project\MyProject.uproject"
```

macOS / Linux:

```bash
./scripts/install_prefabricator_ue5.sh "/path/to/MyProject.uproject"
```

These scripts clone the plugin into:

- `YourProject/Plugins/Prefabricator`

## Recommended workflow

1. Install the plugin into the Unreal project.
2. Open the project and enable Prefabricator if Unreal asks.
3. Create prefab assets for the structural problem cases:
   - roof corners
   - roof edge runs
   - doorway kits
   - facade corner modules
4. Tag those assets so the catalog can prefer them for structural mount types.
5. Let the solver anchor the prefab as a single placement instead of trying to solve every child actor separately.

## Catalog guidance

If you add prefab assets to the catalog, prefer tags like:

- `is_prefab: true`
- `prefab_family: roof`
- `mount_type: roof`

or:

- `is_prefab: true`
- `prefab_family: corner`
- `mount_type: corner`

## Honest limitation

This repo can prepare for Prefabricator and prefer prefab assets, but it does not compile or ship the Unreal plugin by itself from here.

The real Unreal project still needs to:

- install the plugin
- enable it
- create the prefab assets you want to place
