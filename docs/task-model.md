# Task Model

## Initial Robot Task Model

A task describes requested robot work in a way that can be validated, simulated, logged, and later mapped to real hardware commands.

The model should stay practical and boring. It should capture what the system needs to know without pretending the robot can already navigate, grasp, inspect, or report with production reliability.

## Task Fields

| Field | Type | Purpose |
|---|---|---|
| `task_id` | string | Stable identifier for logs and status updates. |
| `task_type` | string | High-level task category, such as `inspection` or `pick_and_report`. |
| `requested_by` | string | Person, agent, or system that requested the task. |
| `mode` | string | Execution mode: `simulation` first, `hardware` later only with safety gates. |
| `target` | object | Named destination, object, or area for the task. |
| `steps` | array | Ordered task steps in business-readable language. |
| `constraints` | object | Limits such as maximum duration or simulation-only requirements. |
| `state` | string | Current task lifecycle state. |
| `created_at` | string | ISO 8601 timestamp for auditability. |

## Task States

```text
draft -> validated -> queued -> running -> succeeded
                         |          |
                         |          +-> failed
                         |
                         +-> cancelled
```

- `draft`: task has been created but not checked.
- `validated`: task shape and constraints are acceptable.
- `queued`: task is ready for an execution adapter.
- `running`: adapter is processing the task.
- `succeeded`: task completed and produced a result.
- `failed`: task could not complete.
- `cancelled`: task was stopped before completion.

## Example JSON Task

```json
{
  "task_id": "task-0001",
  "task_type": "inspection",
  "requested_by": "local-operator",
  "mode": "simulation",
  "target": {
    "name": "inspection-point-a",
    "description": "Simulated checkpoint near the workbench"
  },
  "steps": [
    "move to the inspection point",
    "capture simulated robot state",
    "report task result"
  ],
  "constraints": {
    "simulation_only": true,
    "max_duration_seconds": 120
  },
  "state": "draft",
  "created_at": "2026-07-01T00:00:00Z"
}
```
