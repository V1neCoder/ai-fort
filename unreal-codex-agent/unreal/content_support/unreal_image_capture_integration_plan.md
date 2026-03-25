# UnrealImageCapture Integration Plan

## Purpose

This document explains how to use `TimmHess/UnrealImageCapture` as a reference for replacing placeholder capture with real Unreal-backed image generation.

Primary source:

- [TimmHess/UnrealImageCapture](https://github.com/TimmHess/UnrealImageCapture)

## Why this matters

This repo already has:

- capture packet generation
- packet image naming contracts
- placeholder image materialization
- cache and session storage for capture packets

What it does not have yet is a true Unreal render pipeline that produces those images from the editor.

`UnrealImageCapture` is a strong reference for that.

## Important boundary

This is not a Python-only drop-in.

It is a C++/Unreal-side implementation pattern.

So the correct path is:

- keep Python packet orchestration in this repo
- replace the Unreal-side placeholder capture implementation with a real Unreal capture subsystem or plugin

## Recommended integration architecture

### Repo side stays responsible for:

- deciding which views are needed
- naming packet files
- storing packet JSON
- storing rendered image paths

### Unreal side becomes responsible for:

- creating capture actors/components
- positioning them
- rendering to disk
- returning final image paths and metadata

## Practical migration plan

### Phase 1: Preserve the current contract

Keep these packet labels stable:

- `local_object`
- `room_context`
- `left_angle` or `right_angle`
- `top_view`
- `closeup_detail`
- shell-specific views when needed

That means higher-level logic does not need to change when capture becomes real.

### Phase 2: Replace placeholder-only materialization

Current file:

- [ue_capture_views.py](/C:/AI%20Fort/unreal-codex-agent/unreal/python/ue_capture_views.py)

Current behavior:

- writes placeholder images

Next behavior:

- dispatch to a real Unreal capture implementation
- keep the same packet JSON shape

### Phase 3: Add Unreal plugin or project module work

This is where `UnrealImageCapture` ideas come in.

Expected work:

- add required Unreal-side modules
- build capture actors or components
- support writing images to disk
- return deterministic paths back to Python

### Phase 4: Expose backend mode clearly

The repo already has a capture backend seam.

Use it to distinguish:

- `placeholder`
- `unreal_python`
- `mcp`
- future plugin-backed capture mode

## Recommended success criteria

The first real implementation does not need to be fancy.

It only needs to:

- generate the required files on disk
- match the packet labels
- be stable and repeatable

## Honest note

This plan is intentionally explicit about the C++/plugin boundary.

The repo should not pretend Python alone can replace a full Unreal image capture implementation.
