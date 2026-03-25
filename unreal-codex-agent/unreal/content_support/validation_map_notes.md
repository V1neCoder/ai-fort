# Validation Map Notes

## Purpose

The validation map is a controlled Unreal level used for safe asset measurement, preview generation, and basic placement checks before an asset is trusted for autonomous use.

This map should stay simple and stable.
It is not meant to look good.
It is meant to make measurement and testing predictable.

## Why this map exists

The asset catalog should not trust raw import size or weak asset names.

Before an asset is approved for autonomous placement, the system may need to:

- load or spawn it in isolation
- measure bounds at scale 1,1,1
- inspect pivot behavior
- generate preview images
- test very basic placement assumptions

Doing that in a normal production level is noisy and harder to reason about.

## Recommended map setup

Create one dedicated map, for example:

`/Game/UCA/Validation/UCA_ValidationMap`

Keep the map light and clean.

### Include:

- a flat floor at world origin
- enough empty space around origin for large assets
- neutral lighting
- a simple sky or neutral background
- optional wall planes for wall-mounted asset tests
- optional ceiling plane for ceiling-mounted asset tests

### Avoid:

- clutter
- gameplay logic
- streaming dependencies
- complicated materials
- moving actors
- extra cameras that are not part of validation

## Suggested zones inside the validation map

You can divide the map into simple test regions.

### 1. Floor asset zone
Use for:
- chairs
- sofas
- tables
- rugs
- cabinets
- beds
- clutter that sits on the ground

### 2. Wall asset zone
Use for:
- wall lights
- wall shelves
- wall cabinets
- frames
- mirrors

### 3. Ceiling asset zone
Use for:
- pendant lights
- chandeliers
- ceiling fixtures

### 4. Opening or shell zone
Use for:
- doors
- windows
- facade pieces
- shell-sensitive elements

## Spawn behavior

Validation actors should be spawned with:

- a known label prefix like `UCA_ValidationActor`
- scale reset to 1,1,1
- predictable location
- predictable rotation

This makes cleanup easy and keeps measurements consistent.

## Cleanup behavior

Always destroy validation actors after a pass unless you are debugging.

The repo already has a cleanup script path planned for this, so the validation map should stay clean between runs.

## Measurement expectations

The validation map should be treated as a place to answer questions like:

- what are the asset dimensions at default scale
- does the pivot feel suspicious
- does the asset look centered or offset
- does it appear floor-mounted, wall-mounted, or ceiling-mounted
- does it need quarantine because the dimensions look wrong

## Preview generation use

The validation map is also a good place to generate preview renders for:

- front view
- angle view
- top view

These previews do not need to be artistic.
They just need to be consistent enough for catalog comparison.

## Good practices

- keep origin and axes predictable
- keep test lighting stable
- do not mix validation work with production work
- log which asset was measured and when
- save validation outputs into the repo data folders, not random temp locations

## Minimum practical version

If you want the smallest working version:

- one flat floor
- one neutral wall
- one overhead light
- enough empty space around origin
- one fixed preview camera setup

That is already enough to make the validation map useful.
