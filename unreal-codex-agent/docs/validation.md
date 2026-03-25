# Validation

## Purpose

Validation is the rule-based truth layer of the system.

The visual review loop is useful, but it is not enough by itself.
A scene can look okay from one angle and still be wrong.

Validation exists to block false passes.

## Core rule

A zone is not complete just because an edit succeeded.

A zone is valid only when:
- structural rules pass
- fit rules pass
- shell rules pass when relevant
- asset trust rules pass
- visual review is consistent with those checks

## Validator categories

### 1. Scale sanity
Checks whether the edited object remains inside its allowed scale band.

This should use:
- asset catalog scale limits
- category baselines
- trusted dimensions

### 2. Clearance rules
Checks whether required circulation or spacing still exists.

Examples:
- front clearance for seating
- walkway space around tables
- bed-side clearance
- appliance clearance
- entry path clearance

### 3. Shell alignment
Checks inside/outside consistency for shell-sensitive edits.

Examples:
- window alignment
- wall thickness consistency
- facade/interior agreement
- door opening agreement across both sides

### 4. Trust gate
Checks whether the agent is using an asset that is allowed for autonomous placement.

### 5. Room fit
Checks whether the asset belongs in the room and uses a valid mount type.

### 6. Repetition rules
Checks whether the room is becoming repetitive or visually lazy.
This is often a soft failure, not a hard one.

### 7. Metadata completeness
Checks whether the asset has the minimum useful tags.
Usually a warning unless your pipeline depends on it for that action.

## Blocking vs non-blocking failures

### Blocking failure
A problem that should stop completion and usually trigger revise or undo.

Examples:
- scale outside safe range
- broken shell alignment
- trust below threshold
- room mismatch
- severe clearance failure

### Non-blocking warning
A problem that should lower score or trigger a polish pass but not necessarily force undo.

Examples:
- mild repetition
- missing optional metadata
- weak stylistic fit when physically correct
- low detail completeness

## Validation input

Validators should use:
- current scene state
- dirty zone data
- asset catalog record
- placement profile
- validator rules config

They should not depend only on image review.

## Validation output

A validation report should contain:
- zone ID
- pass/fail per validator
- blocking issue list
- warning list
- suggested next action
- timestamp

## Validation and completion

Completion logic should require:
- no blocking validator failures
- consistent visual evidence
- no unresolved high-priority issue

If validation fails hard, the system should prefer:
- revise
- replace
- undo
- blocked_by_validation

not completion.

## Validation philosophy

Validation should be strict where physical correctness matters and softer where artistic variation matters.

Strict:
- scale
- trust
- room fit
- shell alignment
- clearance

Softer:
- repetition
- visual balance
- detail completeness

## Interaction with Codex

Codex should use validators as truth signals.

When validation conflicts with a visual impression, the system should:
- prefer the validated fact for structural correctness
- request more views if the scene still looks suspicious
- avoid calling the zone complete until both evidence types are acceptable

## What validation does not do

Validation does not:
- choose assets
- decide style by itself
- create captures
- manage session state

It checks whether the result respects system rules.
