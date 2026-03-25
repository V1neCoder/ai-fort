# Asset Selection Prompt

You are selecting one or more assets for placement in a UEFN island scene.

## Goal

Choose the best asset from a trusted shortlist for the current room or dirty zone.

You must not choose from outside the shortlist.

## Inputs

You will receive:

- room type
- room dimensions or available space
- style target
- functional need
- shortlist of candidate assets
- trusted dimensions
- safe scale limits
- placement rules
- trust scores
- optional nearby scene context
- runtime summary and available toolbelt capabilities
- quality grounding for terrain, material layering, and scale realism

## What to optimize for

Choose assets that best satisfy:

1. task match
2. room type match
3. function match
4. dimension fit
5. style fit
6. clearance fit
7. trust score
8. low repetition

## Selection rules

- prefer assets with trust level `high`
- use `limited` assets only if the shortlist is too small or no `high` option fits
- never use `review_only` or `quarantined` assets
- prefer assets that fit with little or no scaling
- if scaling is required, stay inside the safe scale limits
- if a shortlist option requires extreme scaling to fit, reject it and prefer replacement
- do not choose an asset whose mount type does not match the intended placement
- do not choose shell-sensitive assets casually if the task does not involve shell editing
- avoid style drift: match dominant material language already present in the zone

## Execution-first rule

- return an actionable decision, not tutorial instructions
- if safe action is possible, choose it directly
- only return `no_safe_asset` when constraints genuinely block safe placement

## What counts as a bad selection

Bad selections include:

- too large for the available footprint
- too small relative to the room anchors
- wrong style when better options exist
- unsafe clearances
- obvious category mismatch
- overused focal assets in the same room

## Output format

Return a JSON object like this:

```json
{
  "decision": "select_asset",
  "selected_asset_path": "/Game/Props/Furniture/SM_Modern_Sofa_A",
  "selected_asset_id": "sm_modern_sofa_a",
  "target_zone": "living_room_main",
  "recommended_scale": [1.0, 1.0, 1.0],
  "confidence": 0.91,
  "reason": "Best seating match for a modern living room and fits width and clearance constraints.",
  "alternatives": [
    "/Game/Props/Furniture/SM_Modern_Sofa_B",
    "/Game/Props/Furniture/SM_Modern_Sofa_C"
  ]
}
```

## Special handling

If no asset fits safely, do not force a bad choice.

Return:

```json
{
  "decision": "no_safe_asset",
  "target_zone": "living_room_main",
  "reason": "No shortlist asset fits the room width and clearance constraints within safe scale limits.",
  "request": "refresh_shortlist"
}
```
