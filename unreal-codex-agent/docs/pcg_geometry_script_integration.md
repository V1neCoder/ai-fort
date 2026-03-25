# PCG and Geometry Script Integration

## Purpose

This document maps the built-in Unreal PCG and Geometry Script toolsets to concrete seams in this repo's UEFN-first architecture.

These are preferred because they are free or built into Unreal.

## PCG fits these repo areas

### Asset placement augmentation

Most direct future targets:

- [shortlist.py](/C:/AI%20Fort/unreal-codex-agent/apps/asset_ai/shortlist.py)
- [capture_manager.py](/C:/AI%20Fort/unreal-codex-agent/apps/capture_service/capture_manager.py)
- [main.py](/C:/AI%20Fort/unreal-codex-agent/apps/orchestrator/main.py)

What PCG should help with:

- clustering related assets
- scattering support props around chosen focal assets
- room-fill and coverage assists
- layout-aware variation after shortlist selection

### Dirty-zone-aware refinement

Future idea:

- Codex chooses the main asset or prefab
- PCG graph handles support prop distribution in the same room zone
- validators check the result

## Geometry Script fits these repo areas

### Better geometric reasoning

Most direct future targets:

- [scene_tools.py](/C:/AI%20Fort/unreal-codex-agent/apps/mcp_extensions/scene_tools.py)
- [validator_scale.py](/C:/AI%20Fort/unreal-codex-agent/unreal/validators/validator_scale.py)
- [validator_clearance.py](/C:/AI%20Fort/unreal-codex-agent/unreal/validators/validator_clearance.py)
- [ue_measure_asset.py](/C:/AI%20Fort/unreal-codex-agent/unreal/python/ue_measure_asset.py)

What Geometry Script should help with:

- footprint extraction
- more accurate bounds and surface reasoning
- support-surface analysis
- smarter clearance estimation
- wall/opening alignment helpers

## Recommended staged rollout

### Phase 1

- keep current shortlist-driven placement
- keep current validator loop
- add docs and backend preference

### Phase 2

- add UEFN-authored notes and device conventions for PCG-assisted placement
- add Geometry Script-based measurement helpers where the desktop Unreal side is still used as an offline reference pipeline

### Phase 3

- expose placement assist outputs through local export contracts the UEFN project can consume
- let orchestrator request structured placement assists instead of only single-asset decisions

## Practical code seams to extend

### New offline reference helpers to add later

- `unreal/python/ue_run_pcg_graph.py`
- `unreal/python/ue_extract_footprint.py`
- `unreal/python/ue_find_support_surfaces.py`
- `unreal/python/ue_estimate_clearance.py`

### New repo-side adapters to add later

- `apps/integrations/pcg_adapter.py`
- `apps/integrations/geometry_script_adapter.py`

## Rule of thumb

Use:

- Asset AI for candidate choice
- PCG for structured secondary placement
- Geometry Script for geometry-aware truth
- validators for acceptance

That keeps responsibilities clean.
