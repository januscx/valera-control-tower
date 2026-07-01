# Task Model

## Purpose

The task model is the first shared contract in Valera Control Tower. It describes a robot task clearly enough for simulation, status reporting, and future hardware execution without committing to a specific robot API.

## Initial task fields

| Field | Required | Description |
|---|---:|---|
| `task_id` | yes | Stable unique identifier for the task. |
| `task_type` | yes | High-level task category, such as `inspection` or `manipulation_demo`. |
| `description` | yes | Human-readable summary of the requested work. |
| `mode` | yes | Execution mode. Initial value should be `simulation`. |
| `priority` | no | Simple priority such as `low`, `normal`, or `high`. |
| `target` | no | Named location, object, or inspection point. |
| `steps` | yes | Ordered high-level steps the robot should simulate or execute. |
| `requested_by` | no | Person, agent, or system that requested the task. |
| `created_at` | yes | Timestamp supplied by the caller or control tower. |
| `status` | yes | Current task state. |
| `result` | no | Final result summary after completion or failure. |
| `metadata` | no | Extra non-control data for demos, tracing, or enterprise correlation. |

## Task states

Initial states should stay small and explicit:

| State | Meaning |
|---|---|
| `draft` | Task is being prepared and is not ready to run. |
| `accepted` | Task passed validation and can be scheduled. |
| `running` | Task execution has started. |
| `succeeded` | Task completed successfully. |
| `failed` | Task stopped because execution could not complete. |
| `canceled` | Task was stopped by a user, agent, or control-tower rule. |

Allowed first-pass lifecycle:

```text
draft -> accepted -> running -> succeeded
                         |
                         +-> failed
                         |
                         +-> canceled
```

## Example JSON task

```json
{
  "task_id": "task-0001",
  "task_type": "inspection",
  "description": "Move to inspection point A, capture simulated state, and report the result.",
  "mode": "simulation",
  "priority": "normal",
  "target": {
    "location": "inspection-point-a",
    "object": "demo-target"
  },
  "steps": [
    {
      "name": "move_to_location",
      "parameters": {
        "location": "inspection-point-a"
      }
    },
    {
      "name": "capture_state",
      "parameters": {
        "sensor": "simulated-camera"
      }
    },
    {
      "name": "report_result",
      "parameters": {
        "format": "summary"
      }
    }
  ],
  "requested_by": "local-user",
  "created_at": "2026-07-01T00:00:00Z",
  "status": "draft",
  "metadata": {
    "correlation_id": "demo-run-001"
  }
}
```

This example is simulated. It does not claim that a real camera, tracked base, arm, or object detector is available.
