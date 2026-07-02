# Valera Control Tower Architecture

The event log is the source of truth. Task execution, replay, evidence display,
and dashboard rendering all derive from ordered task events.

## Current local MVP flow

```text
Task
-> simulated mission
-> fixture real_vision object.found
-> evidence refs
-> replay JSON
-> static dashboard
```

## Hybrid mode

Hybrid mode keeps movement, grasp, and delivery simulated. Object detection
evidence comes from real OpenCV marker detection against a deterministic fixture.
The resulting `object.found` event uses `real_vision` mode and includes marker
metadata plus raw and annotated local evidence references.

## Non-goals

- No live camera yet.
- No hardware control yet.
- No arm control yet.
- No SAP/ERP integration yet.
- No cloud or dashboard server yet.

## Current PR stack

- PR #1: Established the event core foundation and task state model.
- PR #2: Added deterministic simulation execution and replay output.
- PR #3: Added the local evidence store contract.
- PR #4: Added fixture-based `real_vision` OpenCV marker detection.
- PR #5: Added local static dashboard rendering.
- PR #6: Added the hybrid fixture demo runner.
- PR #7: Adds demo documentation and the operator guide.
