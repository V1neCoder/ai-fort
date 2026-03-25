# Asset AI

## Purpose

Asset AI is the system that turns a messy Unreal asset library into a trusted runtime catalog.

Without this layer, the scene-editing agent would have to guess:
- what assets exist
- what the assets are for
- what room types they fit
- whether their dimensions are safe
- how much they can be scaled
- whether they are safe for autonomous placement

Asset AI solves that.

## Core responsibilities

Asset AI should:

- scan project assets
- infer or normalize metadata
- measure trusted dimensions
- assign safe scale limits
- assign placement rules
- generate preview images
- compute trust scores
- quarantine bad assets
- build runtime shortlists

## Why Asset AI exists

Raw project assets are often messy.

Problems include:
- weak names
- missing tags
- bad import scale
- mixed styles
- unknown room fit
- unknown mount type
- unsafe scaling
- inconsistent collision or pivots

Asset AI is the filter between those messy assets and runtime autonomous placement.

## Asset record concept

Every usable asset should have one catalog record.

A record should contain:
- identity
- tags
- measured dimensions
- bounds
- scale limits
- placement rules
- trust score
- status
- preview set
- notes or quarantine reasons

## Catalog statuses

Use these status bands:

- `approved`
- `limited`
- `review_only`
- `quarantined`

### Meaning

**approved**
Safe for autonomous placement.

**limited**
Allowed when the shortlist is small or no stronger candidate fits.

**review_only**
Not eligible for default autonomous placement.

**quarantined**
Blocked from placement unless explicitly overridden.

## Trust score concept

Trust score is the gate that decides whether an asset can enter a runtime shortlist.

Trust should be based on:
- metadata completeness
- dimension sanity
- classification confidence
- naming quality
- collision sanity
- placement fit
- validator results

### Recommended trust behavior

- 85 to 100 = approved
- 70 to 84 = limited
- 50 to 69 = review_only
- below 50 = quarantined

## Asset AI pipeline

### 1. Registry scan

Collect candidate assets from the project.

Typical candidate classes:
- StaticMesh
- Blueprint
- SkeletalMesh when relevant
- other placeable classes as needed

### 2. Metadata enrichment

Normalize or infer:
- category
- function
- room types
- styles
- mount type
- scale policy
- clearance profile
- shell-sensitive flag

### 3. Trusted-dimension pass

Measure the asset in a validation environment.

This should:
- load or spawn the asset
- reset scale
- read bounds
- compare against category baselines
- assign safe scale limits

### 4. Preview generation

Generate a preview set such as:
- front
- angle
- top

These previews help both indexing and future review workflows.

### 5. Trust scoring

Compute trust score and assign status.

### 6. Metadata write-back

Write the lightweight, stable fields back into Unreal metadata so the editor and MCP queries can use them.

### 7. Catalog export

Save the final catalog into:
- SQLite
- JSONL
- quarantine JSONL

## Tagging model

### Required tags

- category
- function
- room_types
- mount_type
- scale_policy

### Strongly recommended tags

- styles
- shell_sensitive
- clearance_profile
- material_family
- placement_behavior
- repeatability

## Scale policy model

Asset AI should not allow unrestricted scaling.

Use these policies:

- `locked`
- `tight`
- `medium`
- `wide`

### Typical usage

**locked**
Doors, windows, counters, cabinets, stairs

**tight**
Sofas, chairs, tables, lamps, beds

**medium**
Decor, rugs, some clutter

**wide**
Only stylized or intentionally flexible filler assets

## Placement rules

Each asset should also carry or inherit placement rules.

Examples:
- allowed surfaces
- min front clearance
- min side clearance
- back offset
- against wall allowed
- corner allowed
- shell-sensitive behavior

## Shortlist generation

At runtime, Asset AI should never return the full library.

It should filter in stages:

### Stage 1
Hard filter by:
- trust
- room type
- function
- mount type
- style if requested

### Stage 2
Physical fit filter:
- size fit
- clearance fit
- scale limit fit
- shell-sensitive constraints

### Stage 3
Rank remaining candidates by:
- task match
- style match
- dimension fit
- repetition penalty
- trust strength

## Quarantine logic

An asset should be quarantined when:
- its dimensions are clearly broken
- its category or function cannot be trusted
- its metadata is too incomplete
- its measured size is wildly outside baseline ranges
- it repeatedly fails validators
- it is known to break autonomous placement

Quarantine should protect runtime, not permanently erase the asset.

## Incremental updates

Do one heavy indexing pass once, then update only changed assets when possible.

The runtime loop should query the catalog, not re-scan the entire asset registry every cycle.

## What Asset AI does not do

Asset AI does not directly edit the scene.

It does not decide final placement.
It does not mark zones complete.

It prepares trusted options so the rest of the system can operate safely.
