# UnrealValidationFramework Setup Guide

## Purpose

This document explains how to bring `Netflix-Skunkworks/UnrealValidationFramework` into the Unreal side of this scaffold in a realistic way.

Primary source:

- [Netflix-Skunkworks/UnrealValidationFramework](https://github.com/Netflix-Skunkworks/UnrealValidationFramework)

## Why this plugin is relevant

This repo already has:

- local validation rules
- Unreal-side validator helper scripts
- report-oriented session history

`UnrealValidationFramework` is a good fit when you want richer Unreal-native validation results and consistent report generation from inside the editor.

## Important boundary

This is an Unreal plugin integration.

It is not something this Python repo can “import” and use by itself without the Unreal project also installing and loading the plugin.

## Recommended setup path

### 1. Add the plugin to your Unreal project

Preferred approach:

- download the release or clone the repo
- place it under your Unreal project `Plugins/` folder

Typical path:

`<YourUnrealProject>/Plugins/UnrealValidationFramework`

### 2. Regenerate project files if needed

If your project is C++-backed:

- regenerate project files
- open the solution
- build the project/plugin

### 3. Enable the plugin in Unreal

Inside Unreal Editor:

- open `Edit -> Plugins`
- confirm the plugin is enabled
- restart if required

### 4. Map plugin output into this repo

The repo-side goal is not to replace local validation entirely.

The better pattern is:

- UnrealValidationFramework produces Unreal-native validation output
- Unreal-side Python gathers or exports that report
- this repo ingests the report into session history and orchestrator decisions

## Suggested repo integration point

Use the plugin as an upstream signal for:

- shell-sensitive checks
- asset metadata correctness
- placement or project-specific validation policies
- structured report export

Best place to connect that output:

- [unreal/validators](/C:/AI%20Fort/unreal-codex-agent/unreal/validators)
- [run_validators.py](/C:/AI%20Fort/unreal-codex-agent/apps/validation/run_validators.py)
- session validation history in `data/sessions/<session_id>/validation_history.jsonl`

## Recommended staged rollout

### Phase 1

- install plugin
- validate project compiles
- run plugin manually inside Unreal

### Phase 2

- add a small Unreal Python wrapper that exports plugin results to JSON

### Phase 3

- teach repo validators to merge local checks with Unreal-native checks

## Honest note

This guide is intentionally a setup guide, not a fake direct integration.

The plugin belongs in the Unreal project, not inside this Python scaffold.
