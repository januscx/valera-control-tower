from datetime import datetime, timedelta, timezone
from typing import Any

from robot.events import EventEnvelope, EventType
from robot.models import ExecutionMode, FailureCode, Task, ValidationError, Zone
from robot.state_machine import TaskEventLog


APPROVED_SUCCESS_EVENT_SEQUENCE = (
    EventType.TASK_CREATED,
    EventType.PLAN_CREATED,
    EventType.TASK_ACCEPTED,
    EventType.ROUTE_STARTED,
    EventType.ROUTE_ARRIVED,
    EventType.OBJECT_SEARCH_STARTED,
    EventType.OBJECT_FOUND,
    EventType.GRASP_STARTED,
    EventType.OBJECT_GRASPED,
    EventType.DELIVERY_STARTED,
    EventType.ROUTE_ARRIVED,
    EventType.OBJECT_RELEASED,
    EventType.DELIVERY_COMPLETED,
    EventType.TASK_COMPLETED,
)

SIMULATION_TIMESTAMP_BASE = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
SIMULATION_SOURCE = "valera.sim_executor"


def run_simulated_mission(task: Task) -> TaskEventLog:
    if task.mode != ExecutionMode.SIMULATION:
        code = (
            FailureCode.HARDWARE_MODE_NOT_ENABLED
            if task.mode == ExecutionMode.HARDWARE
            else FailureCode.INVALID_TASK
        )
        raise ValidationError("simulator only accepts simulation mode tasks", code)

    correlation_id = f"{task.task_id}-simulation-mission"
    event_log = TaskEventLog(task.task_id)

    for sequence, event_type in enumerate(APPROVED_SUCCESS_EVENT_SEQUENCE, start=1):
        event_log.append(
            EventEnvelope(
                event_id=f"{correlation_id}-{sequence:03d}",
                task_id=task.task_id,
                correlation_id=correlation_id,
                sequence=sequence,
                event_type=event_type,
                occurred_at=SIMULATION_TIMESTAMP_BASE + timedelta(seconds=sequence - 1),
                source=SIMULATION_SOURCE,
                mode=ExecutionMode.SIMULATION,
                payload=_payload_for_event(task, event_type, sequence),
            )
        )

    event_log.validate()
    return event_log


def _payload_for_event(task: Task, event_type: EventType, sequence: int) -> dict[str, Any]:
    base: dict[str, Any] = {
        "object_id": task.object_id,
        "pickup_zone": task.pickup_zone.value,
        "delivery_zone": task.delivery_zone.value,
    }

    if event_type == EventType.TASK_CREATED:
        return base | {"status": "created"}
    if event_type == EventType.PLAN_CREATED:
        return base | {
            "status": "planned",
            "planned_route": [
                Zone.BASE.value,
                task.pickup_zone.value,
                task.delivery_zone.value,
            ],
        }
    if event_type == EventType.TASK_ACCEPTED:
        return base | {"status": "accepted"}
    if event_type == EventType.ROUTE_STARTED:
        return base | {"status": "in_transit", "current_target_zone": task.pickup_zone.value}
    if event_type == EventType.ROUTE_ARRIVED:
        return base | {"status": "arrived", "current_target_zone": _arrival_target(task, sequence)}
    if event_type == EventType.OBJECT_SEARCH_STARTED:
        return base | {"status": "searching", "current_target_zone": task.pickup_zone.value}
    if event_type == EventType.OBJECT_FOUND:
        return base | {"status": "found", "current_target_zone": task.pickup_zone.value}
    if event_type == EventType.GRASP_STARTED:
        return base | {"status": "grasping", "current_target_zone": task.pickup_zone.value}
    if event_type == EventType.OBJECT_GRASPED:
        return base | {"status": "secured", "current_target_zone": task.pickup_zone.value}
    if event_type == EventType.DELIVERY_STARTED:
        return base | {"status": "delivering", "current_target_zone": task.delivery_zone.value}
    if event_type == EventType.OBJECT_RELEASED:
        return base | {"status": "released", "current_target_zone": task.delivery_zone.value}
    if event_type == EventType.DELIVERY_COMPLETED:
        return base | {"status": "delivered", "current_target_zone": task.delivery_zone.value}
    if event_type == EventType.TASK_COMPLETED:
        return base | {"status": "completed", "current_target_zone": task.delivery_zone.value}

    return base | {"status": "simulated"}


def _arrival_target(task: Task, sequence: int) -> str:
    # The success sequence has two route.arrived events: pickup first, delivery second.
    if sequence < 10:
        return task.pickup_zone.value
    return task.delivery_zone.value
