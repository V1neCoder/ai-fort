# UEFN Structure Generation Grounding

Use this as execution grounding for non-house structures and mixed build requests.

## Core rule

- Use shared geometry planners and managed actions for structures whenever possible.
- Do not fall back to ad-hoc cube spam when a planned structure family fits the request.

## Generative rule

- Structure generation must feel varied and intentional, not cloned.
- Vary footprint, roof pitch, overhang, opening width, post thickness, and proportions within believable ranges.
- Keep variation stable per request/chat so reruns update the same idea instead of drifting randomly.
- Prefer code-driven structure plans over text-only prompting. The model should trigger the shared builders so geometry, circulation, openings, and managed reuse come from the planner, not from prose.

## Supported structure families

- Enclosed utility structures: garage, shed, workshop, barn, warehouse, greenhouse, studio, hangar, kiosk
- Open roofed structures: pavilion, gazebo, pergola, canopy, carport, market stall
- Scenic or special structures may still use dedicated procedural code when no shared planner exists yet.

## Structural quality rules

- Use managed slots so rebuilds update existing pieces instead of stacking duplicates.
- Respect support surfaces first; do not place buildings on random nearby actors.
- Keep openings clear and proportions human-scaled.
- Roof pieces must align to one solved envelope when a roof is present.
- Open-air structures should use posts, beams, and coherent roof logic instead of fake walls.
- When importable model attachments are provided, preserve and place those assets with the import tools instead of replacing them with placeholder cubes.
- If the request is broad, use the shared structure action first and only use lower-level tools for targeted follow-up adjustments or material passes.

## Tooling rule

- For houses, use `build_house_action`.
- For garages, sheds, workshops, barns, warehouses, greenhouses, studios, hangars, kiosks, pavilions, gazebos, pergolas, canopies, carports, and market stalls, use `build_structure_action`.
- Only use raw Python placement when neither shared structure action nor a registered tool can satisfy the request.
