# UEFN Quality Grounding (Terrain, Materials, Scale)

Use this as execution grounding, not as a tutorial.

## Terrain shaping baseline

- Work in phases: `manage -> sculpt -> paint`.
- Keep broad forms first (major height and flow), then medium forms, then micro detail.
- Prefer smooth transitions for playable paths; avoid random spikes and abrupt slope shifts.
- Use ramp and spline-friendly transitions where traversal or roads are expected.
- Prefer layer-safe edits so large forms and fine detail can be adjusted independently.

## Landscape paint and layer quality

- Treat paint layers as weightmaps: blend intentionally, avoid muddy overmixing.
- Keep a clear dominant layer per region with secondary breakup layers.
- Use noise and smoothing to break tiling patterns while preserving readability.
- Avoid hard paint boundaries unless the art style explicitly calls for them.

## Material quality and performance

- Use physically plausible material values (base color, roughness, metallic behavior).
- Prefer parameterized materials/instances for controlled variation over copy-paste variants.
- Keep material graphs practical; avoid unnecessarily heavy instruction counts.
- Use detail normals/noise subtly; avoid over-crisp or noisy surfaces at gameplay distance.

## Scale and fit sanity

- Real-world scale consistency is mandatory across neighboring assets and terrain features.
- Respect trusted dimensions and safe scale ranges; avoid dramatic non-uniform scaling.
- Preserve circulation and interaction clearance around placed gameplay spaces.
- Prefer asset replacement over extreme scaling when fit is poor.

## Evidence and confidence policy

- Favor decisions backed by scene state, validators, capture packet views, and tool inventory.
- If evidence is insufficient, request `request_more_views` or `request_state_refresh`.
- Do not claim certainty when cross-angle evidence is missing.

## Anti-generic rule

- Do not output generic advice when an executable action is possible.
- Return a concrete action/review/completion decision that the orchestrator can apply now.
