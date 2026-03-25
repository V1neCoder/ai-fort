# Capture Logic

## Purpose

The capture system provides visual evidence for the agent.

It exists because:
- one screenshot is not enough
- one angle can hide errors
- inside/outside edits often need both sides checked
- visual review should be tied to the edited object or dirty zone

The capture system should produce structured image packets, not random screenshots.

## Core principles

### 1. Capture the dirty zone, not the whole world
Capture should focus on what changed and what that change affects.

### 2. Use multiple angles
Every meaningful edit should be reviewed from more than one angle.

### 3. Use context plus detail
A good packet usually needs both:
- local object evidence
- larger room or shell context

### 4. Use shell cross-checks when relevant
If an object affects both inside and outside, review both sides.

## Dirty zone model

A dirty zone is created when:
- an actor is placed
- an actor is moved
- an actor is rotated
- an actor is scaled
- an actor is replaced
- an actor is deleted
- a validator failure points to a local area

A dirty zone should contain:
- zone ID
- actor IDs
- approximate bounds
- room type
- shell-sensitive flag
- capture profile name

## Capture packet model

A capture packet should contain:
- packet ID
- zone ID
- image list
- image labels
- capture profile used
- shell cross-check flag
- timestamp
- optional notes

## Standard view types

Common view labels:
- `local_object`
- `room_context`
- `left_angle`
- `right_angle`
- `high_angle`
- `top_context`
- `closeup_detail`
- `outside_context`
- `inside_context`
- `cross_boundary`
- `cube_surround`

Not every packet needs every label.

## Capture profiles

### default_room
Use for most standard room edits.

Typical views:
- local object
- room context
- side angle
- high angle
- close-up detail

### tight_interior
Use when the room is small or cluttered.

Typical views:
- local object
- front context
- side angle
- top or high context
- close-up detail

### shell_sensitive
Use when the edit touches the building shell.

Typical views:
- local object
- outside context
- inside context
- cross-boundary
- high angle
- close-up detail

### exterior_facade
Use for outer wall and facade work.

Typical views:
- facade front
- facade angle left
- facade angle right
- interior opposite side
- close-up detail

## When to capture

Capture should happen:

- after a scene edit
- after a local revise action
- before a completion check
- after a validator failure in a zone
- on a wider heartbeat when needed

Do not capture the whole scene after every tiny edit unless there is a real need.

## When to request more views

The system should request more views when:
- an important surface or edge is hidden
- the shell is involved but only one side was captured
- the validator report conflicts with the visible evidence
- the object is ambiguous from current angles
- a detail issue needs closer inspection

## Review logic connection

Capture packets are sent into the Codex review loop together with:
- scene state
- dirty zone data
- validation report
- score history if needed

The AI should review the packet as a set, not as isolated images.

## Capture failure behavior

If a packet is incomplete:
- do not pretend the evidence is enough
- request missing views
- refresh scene state if needed
- prefer review delay over false confidence

## What capture logic does not do

Capture logic does not:
- choose final assets
- decide placement rules
- validate scale by itself
- mark zones complete

It only provides the visual evidence needed for those decisions.
