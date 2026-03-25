# Free Plugin Priority Setup

## Purpose

This document keeps the UEFN-side setup focused on free or built-in tools first.

## Recommended order

### 1. Built-in UEFN or engine-side options

Enable first:

- Verse
- Fortnite devices
- Scene Graph when your island uses entity/component workflows
- Geometry Script
- Procedural Content Generation Framework
- Data Validation support where the desktop Unreal side is still used as an offline reference project

These should be the first tools used to strengthen this repo.

### 2. Free external integrations

Add next:

- `UnrealValidationFramework`
- optional `PCG Extended Toolkit`

### 3. Heavier or optional tools

Only add when needed:

- `UnrealImageCapture` style C++ capture work
- prefab systems
- paid marketplace tools
- Houdini-based procedural workflows

## Why this order works

It keeps the project:

- affordable
- easier to maintain
- closer to supported UEFN workflows
- safer to onboard

## Built-in tools and where they help

### PCG

Good for:

- scattering
- structured placement
- graph-driven layout helpers
- biome or room fill logic

### Geometry Script

Good for:

- custom mesh analysis
- footprint reasoning
- geometry-aware editor tooling
- future smart placement helpers

### Data Validation

Good for:

- report-oriented project checks
- editor-native validation signals

## Repo mapping

These free tools align to this repo like this:

- PCG -> future building and placement augmentation
- Geometry Script -> future geometry-aware validators and placement analysis
- Verse + devices + Scene Graph -> supported runtime bridge
- UnrealValidationFramework -> stronger Unreal-native report generation

## Practical rule

Do not block progress waiting for premium tools.

Get the free stack working first.
