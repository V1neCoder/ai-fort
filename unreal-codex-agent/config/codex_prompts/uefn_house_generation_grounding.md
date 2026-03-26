# UEFN House Generation Grounding

Use this as execution grounding for house and home requests.

## Core rule

- Plan the structure first, then place pieces that satisfy the plan.
- Do not improvise a house as unrelated cubes.

## Functional house baseline

- A house should feel complete by default: floor, walls, roof, door, circulation, and believable proportions.
- A multi-story house must include stairs, a stairwell opening, and a reachable landing.
- The upper floor must not block the stair arrival.
- Roofs must be solved from the wall envelope so they cover the structure cleanly.

## Structural correctness rules

- Connect wall corners cleanly without overlap or visible gaps.
- Preserve door and stair openings as protected functional space.
- Avoid blocking circulation paths with walls, slabs, or decorative pieces.
- Keep roof panels, ridge, and gable closure pieces aligned to one solved roof envelope.
- Prefer deterministic support surfaces such as selected slabs, platforms, or terrain instead of random nearby actors.

## Generative variation rules

- Do not generate the exact same house every time.
- Vary width, depth, roof pitch, overhang, stair-side placement, balcony presence, entry treatment, window rhythm, and overall character within sane residential ranges.
- Keep variation believable and structurally valid.
- When the request is general, choose a coherent house style rather than a generic cube shell.
- Treat mansion, villa, townhouse, apartment, cottage, cabin, and suburban house as different residential families with different proportions and facade language.
- A mansion or villa should feel larger and more articulated than a starter house by default, with stronger entry composition, wider footprint, and richer frontage.

## Placement behavior

- New structure placement should avoid interfering with existing managed builds when possible.
- Respect selected support surfaces first.
- Reuse managed actors for the same structure zone instead of stacking duplicates.

## Material and realism expectations

- Default houses should feel intentional, not placeholder-only.
- Use coherent body and roof materials when material choices are available.
- Keep house proportions human-scaled and traversal-friendly.
- Avoid stacking new houses onto other existing builds. Prefer planner-backed relocation when the requested footprint would interfere with nearby structures.

## Tooling rule

- For house requests, use the dedicated shared house generation action instead of generic `build_structure` or ad-hoc Python unless the user explicitly asks for a custom low-level build.
