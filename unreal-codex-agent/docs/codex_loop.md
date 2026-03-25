# Codex Loop

## Purpose

This document explains how Codex fits into the repeated edit-review cycle.

Codex is not a random chat layer.
It is the planning and review brain that works on top of:
- scene state
- asset shortlists
- capture packets
- validation reports
- action history

## Main Codex roles

Codex has three main jobs:

1. **asset choice**
2. **edit planning**
3. **edit review / completion judgment**

## Why the loop must be repeated

The system should not depend on one giant freeform conversation.

Instead, it should run many short cycles:
- state refresh
- decision
- action
- review
- validation
- score update

This keeps the system grounded in current UEFN truth.

## Cycle phases

### Phase 1: intake
Inputs:
- build goal
- current scene state
- dirty zone
- shortlist if needed
- latest validation report
- score history
- capture packet

### Phase 2: decision
Codex decides one of:
- select asset
- place asset
- move actor
- rotate actor
- scale actor
- replace asset
- request more views
- request state refresh
- no-op

### Phase 3: export / handoff
The orchestrator exports the structured action as a UEFN placement intent plus generated Verse/device scaffold inputs.

### Phase 4: review
After the edit, Codex reviews:
- new state
- new packet
- validator output

Then it decides:
- keep
- revise
- replace
- undo
- incomplete
- complete
- blocked_by_validation

## Prompt structure

The repo uses separate prompt files for:
- system behavior
- asset selection
- edit review
- completion

This keeps each Codex turn focused and easier to parse.

## Required behavior

Codex should:
- use shortlists, not raw asset guessing
- respect trust thresholds
- respect scale limits
- review multiple views together
- treat validators as strong truth signals
- prefer incomplete over false complete
- request more evidence if current evidence is weak

## What Codex should not do

Codex should not:
- invent asset paths
- ignore blocking validators
- assume one camera is enough
- rely on stale scene state
- produce vague responses
- directly control the whole loop without the orchestrator

## Output schema idea

Every Codex response should be parseable.

Typical fields:
- decision
- target zone
- asset path if needed
- transform if needed
- reason
- confidence
- alternatives if relevant
- suggested next action

## Error handling

If Codex returns:
- invalid JSON
- vague language
- unsupported action
- no decision

then the orchestrator should:
1. retry with a stricter schema reminder
2. fall back to no-op or review request if needed
3. avoid unsafe action dispatch

## Review behavior

Review is not only visual.

Codex should combine:
- scene-state facts
- validator output
- asset record info
- capture packet evidence

That is what makes the loop reliable.

## Completion behavior

Codex should only return completion when:
- validator state allows it
- the zone still matches the build goal
- the right views are present
- no obvious blocking issue remains

If the evidence is mixed, prefer:
- incomplete
- needs_more_review

## Human role

The user should mostly:
- set goals
- start sessions
- optionally step in for artistic changes or overrides

The system should do the repeated reasoning and review work automatically.
