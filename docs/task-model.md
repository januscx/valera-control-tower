# Task Model

## Initial robot task model

A robot task describes a requested unit of work for Valera. The model should be understandable by humans, agents, simulation code, and enterprise integration examples.

The initial model is deliberately small. It captures what should happen, where it should happen, how it should be tracked, and whether the result is simulated or hardware-backed.

## Task fields

| Field | Required | Purpose |
|---|---:|---|
| `task_id` | Yes | Stable identifier for logs and status updates |
| `title` | Yes | Short human-readable task name |
| `description` | No | Additional context for operators or agents |
| `mode` | Yes | Execution mode, initially `simulation` |
| `requested_by` | No | Source user, agent, or enterprise process |
| `target` | No | Named location, inspection point, or object reference |
| `steps` | Yes | Ordered high-level actions to simulate or execute |
| `priority` | No | Simple scheduling hint such as `low`, `normal`, or `high` |
| `state` | Yes | Current lifecycle state |
| `created_at` | No | Timestamp supplied by the caller or runtime |
| `result` | No | Final summary after completion, cancellation, or failure |

## Task states

| State | Meaning |
|---|---|
| `draft` | Task is being prepared and has not been accepted |
| `queued` | Task is accepted and waiting to run |
| `validating` | Task is being checked against known capabilities and constraints |
| `running` | Task is in progress |
| `completed` | Task finished successfully |
| `failed` | Task could not complete |
| `cancelled` | Task was stopped before completion |

Future hardware tasks may need additional safety states. Those should be added only when the hardware adapter design exists.

## Example JSON task

```json
{
  "task_id": "task-001",
  "title": "Simulated inspection point check",
  "description": "Move to a named inspection point, capture simulated state, and report the result.",
  "mode": "simulation",
  "requested_by": "demo-user",
  "target": {
    "type": "inspection_point",
    "name": "bench-a"
  },
  "steps": [
    {
      "action": "move_to",
      "target": "bench-a"
    },
    {
      "action": "capture_state"
    },
    {
      "action": "report_result"
    }
  ],
  "priority": "normal",
  "state": "draft",
  "created_at": "2026-07-01T00:00:00Z",
  "result": null
}
```
