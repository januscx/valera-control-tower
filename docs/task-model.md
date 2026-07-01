# Task Model

## Purpose

The task model describes a robot task at a level that is useful for operators, agents, and enterprise workflows.

It should describe intent and expected outcomes, not direct hardware commands.

## Initial Task Fields

| Field | Type | Description |
|---|---|---|
| `task_id` | string | Stable identifier for tracking the task. |
| `title` | string | Short human-readable task name. |
| `description` | string | Practical description of the requested work. |
| `task_type` | string | Category such as `inspection`, `transport`, or `manipulation`. |
| `target_location` | object | Named location or simulated coordinates. |
| `target_object` | object or null | Optional object involved in the task. |
| `requested_actions` | array | Ordered business-level actions to attempt. |
| `priority` | string | Initial priority such as `low`, `normal`, or `high`. |
| `state` | string | Current task lifecycle state. |
| `created_by` | string | User, agent, or system that created the task. |
| `created_at` | string | ISO 8601 timestamp when the task was created. |
| `notes` | array | Optional human-readable assumptions or constraints. |

## Task States

| State | Meaning |
|---|---|
| `created` | Task has been defined but not validated. |
| `validated` | Task has passed basic model checks. |
| `planned` | A simulation or execution plan has been prepared. |
| `running` | The task is being executed by an adapter. |
| `succeeded` | The task completed successfully. |
| `failed` | The task could not be completed. |
| `cancelled` | The task was stopped before completion. |

Hardware-specific safety states may be added later when real hardware adapters exist.

## Example JSON Task

```json
{
  "task_id": "task-0001",
  "title": "Inspect workbench area",
  "description": "Move to the simulated workbench inspection point, capture state, and report the result.",
  "task_type": "inspection",
  "target_location": {
    "name": "workbench",
    "simulated_coordinates": {
      "x": 2.0,
      "y": 1.5
    }
  },
  "target_object": {
    "label": "sample-part",
    "expected_action": "point"
  },
  "requested_actions": [
    "move_to_location",
    "capture_state",
    "point_at_target",
    "report_result"
  ],
  "priority": "normal",
  "state": "created",
  "created_by": "demo-user",
  "created_at": "2026-07-01T00:00:00Z",
  "notes": [
    "Simulation only.",
    "No real hardware control is implied."
  ]
}
```
