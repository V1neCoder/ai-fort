# Capture Camera Notes

## Purpose

The capture system should review edited zones from multiple angles instead of relying on one weak screenshot.

This file explains how the camera logic should be thought about inside the Unreal side of the project.

## Core idea

Do not capture "the whole scene" every time.

Capture the **dirty zone** and the surrounding context that matters.

That means the camera set should depend on:

- what object changed
- what room or zone it belongs to
- whether it affects inside and outside
- whether detail views are needed

## Camera families

The scaffold is built around two main Unreal capture types:

- `SceneCapture2D`
- `SceneCaptureCube`

Use 2D captures for most practical review views.
Use cube capture for hard cases or surround-style inspection.

## Standard view purposes

### 1. Local object view
Used to inspect:
- the object itself
- its immediate placement
- obvious floating or clipping
- material/detail issues

### 2. Room context view
Used to inspect:
- whether the object fits the room
- spacing
- circulation
- composition

### 3. Side angle
Used to inspect:
- depth
- wall alignment
- object thickness against nearby geometry
- whether things sink into the wall or protrude oddly

### 4. High or top view
Used to inspect:
- layout
- walking space
- relationship to nearby props
- overall footprint fit

### 5. Close-up detail view
Used to inspect:
- seams
- contact with floor or wall
- small clipping
- visual finish around the dirty zone

## Shell-sensitive cases

When an edit touches the building shell, one side is not enough.

Examples:
- windows
- doors
- facade modules
- balconies
- roof edges
- exterior wall lights

For these, the packet should include:

- outside context
- inside context
- cross-boundary or seam view

The system should not mark shell-sensitive edits complete without both sides checked.

## Suggested practical camera behavior

### Standard room edit
Capture:
- local object
- room context
- side angle
- high angle
- close-up

### Tight room edit
Capture:
- local object
- front context
- side angle
- top/high context
- close-up

### Shell-sensitive edit
Capture:
- local object
- outside context
- inside context
- cross-boundary
- high angle
- close-up

## Camera placement guidance

### Local object view
Should be close enough to see the object clearly but not so close that context disappears.

### Room context view
Should show the object and the nearby room arrangement together.

### Side angle
Should reveal depth and intersections that a front view can hide.

### High angle
Should reveal spacing and footprint fit.

### Cross-boundary view
Should clearly show the relevant seam or shell relationship.

## What not to do

Do not:
- use only one camera for everything
- capture from random unrelated angles
- keep every view at the same distance
- ignore inside/outside correlation when shell edits happen

## Placeholder vs real capture

Right now the scaffold can create placeholder packet images so the data flow works.
Later, those placeholders should be replaced by real Unreal capture outputs while keeping the same packet structure and image labels.

That is why the file path and packet contract matter.

## Naming consistency

Use stable labels like:

- `local_object`
- `room_context`
- `left_angle`
- `right_angle`
- `high_angle`
- `closeup_detail`
- `outside_context`
- `inside_context`
- `cross_boundary`
- `cube_surround`

Those names should stay consistent across the repo.

## Minimum practical version

If you want a clean first version, start with:

- 1 local object view
- 1 room context view
- 1 side angle
- 1 high angle
- 1 close-up

Then add shell-specific views only when the zone requires them.
