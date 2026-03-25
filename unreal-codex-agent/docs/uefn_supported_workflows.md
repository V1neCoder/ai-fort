# UEFN Supported Workflows

## Why the architecture changed

This repo now treats UEFN as the primary runtime target.

The supported scripting and authored-runtime workflows we align with are:

- Verse-authored devices
- Fortnite devices
- Scene Graph

That means the local Python scaffold should plan, validate, export, and review.
It should not assume unsupported live control paths as the main architecture.

## Official references

- [Create your own device using Verse](https://dev.epicgames.com/documentation/en-us/uefn/modify-and-run-your-first-verse-program-in-unreal-editor-for-fortnite)
- [Getting started in Scene Graph](https://dev.epicgames.com/documentation/en-us/uefn/getting-started-in-scene-graph-in-fortnite)
- [Transforms in Scene Graph](https://dev.epicgames.com/documentation/en-us/uefn/transforms-in-scene-graph-in-unreal-editor-for-fortnite)

## Repo mapping

The repo now maps those supported workflows like this:

- local planner and validator loop: `apps/`
- UEFN backend/runtime selection: `apps/integrations/uefn_backend.py`
- Verse/device scaffold export: `apps/uefn/`
- generated Verse output: `uefn/verse/generated/`
- per-cycle handoff artifacts: `data/sessions/<session_id>/uefn_bridge/`

## Current handoff contract

Each cycle can export:

- a placement intent JSON
- a cycle manifest JSON
- a generated Verse placement coordinator
- a generated Verse scene monitor

These are meant to be reviewed and wired into the UEFN project rather than treated as a hidden runtime hack.
