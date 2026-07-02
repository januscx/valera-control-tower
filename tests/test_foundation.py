from datetime import datetime, timezone

import pytest

from robot.events import EventEnvelope, EventType
from robot.models import ExecutionMode, FailureCode, Task, ValidationError, Zone
from robot.state_machine import TaskEventLog


def make_event(
    event_type=EventType.TASK_CREATED,
    sequence=1,
    task_id="task-001",
    mode=ExecutionMode.SIMULATION,
):
    return EventEnvelope(
        event_id=f"event-{sequence}",
        task_id=task_id,
        correlation_id="corr-001",
        sequence=sequence,
        event_type=event_type,
        occurred_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        source="pytest",
        mode=mode,
        payload={"status": "ok"},
    )


def test_event_envelope_requires_core_fields():
    with pytest.raises(ValidationError, match="event_id"):
        EventEnvelope(
            event_id="",
            task_id="task-001",
            correlation_id="corr-001",
            sequence=1,
            event_type=EventType.TASK_CREATED,
            occurred_at=datetime.now(timezone.utc),
            source="pytest",
            mode=ExecutionMode.SIMULATION,
            payload={},
        )


def test_event_type_validation_rejects_unknown_values():
    with pytest.raises(ValidationError, match="event_type"):
        make_event(event_type="task.teleported")


def test_approved_event_catalog_is_available():
    assert {event_type.value for event_type in EventType} == {
        "task.created",
        "task.accepted",
        "plan.created",
        "route.started",
        "route.arrived",
        "object.search_started",
        "object.found",
        "object.not_found",
        "grasp.started",
        "object.grasped",
        "grasp.failed",
        "delivery.started",
        "object.released",
        "delivery.completed",
        "task.completed",
        "task.failed",
    }


def test_execution_mode_validation_rejects_unknown_values():
    with pytest.raises(ValidationError, match="mode"):
        Task(
            task_id="task-001",
            object_id="VALERA-CUBE-001",
            pickup_zone=Zone.PICKUP_ZONE,
            delivery_zone=Zone.DELIVERY_ZONE,
            mode="magic",
        )


def test_task_requires_object_id():
    with pytest.raises(ValidationError, match="object_id"):
        Task(
            task_id="task-001",
            object_id="",
            pickup_zone=Zone.PICKUP_ZONE,
            delivery_zone=Zone.DELIVERY_ZONE,
            mode=ExecutionMode.SIMULATION,
        )


def test_unknown_zones_are_rejected():
    with pytest.raises(ValidationError, match="pickup_zone"):
        Task(
            task_id="task-001",
            object_id="VALERA-CUBE-001",
            pickup_zone="garage",
            delivery_zone=Zone.DELIVERY_ZONE,
            mode=ExecutionMode.SIMULATION,
        )


def test_hardware_mode_fails_closed_for_mvp():
    with pytest.raises(ValidationError) as exc:
        Task(
            task_id="task-001",
            object_id="VALERA-CUBE-001",
            pickup_zone=Zone.PICKUP_ZONE,
            delivery_zone=Zone.DELIVERY_ZONE,
            mode=ExecutionMode.HARDWARE,
        )

    assert exc.value.code == FailureCode.HARDWARE_MODE_NOT_ENABLED


def test_event_envelope_hardware_mode_fails_closed_for_mvp():
    with pytest.raises(ValidationError) as exc:
        make_event(mode=ExecutionMode.HARDWARE)

    assert exc.value.code == FailureCode.HARDWARE_MODE_NOT_ENABLED


def test_terminal_completed_and_failed_states_are_mutually_exclusive():
    event_log = TaskEventLog("task-001")
    event_log.append(make_event(EventType.TASK_CREATED, 1))
    event_log.append(make_event(EventType.TASK_COMPLETED, 2))

    with pytest.raises(ValidationError, match="terminal"):
        event_log.append(make_event(EventType.TASK_FAILED, 3))


def test_no_event_can_be_appended_after_terminal_event():
    event_log = TaskEventLog("task-001")
    event_log.append(make_event(EventType.TASK_CREATED, 1))
    event_log.append(make_event(EventType.TASK_FAILED, 2))

    with pytest.raises(ValidationError, match="terminal"):
        event_log.append(make_event(EventType.TASK_ACCEPTED, 3))


def test_event_sequence_must_be_monotonic_per_task():
    event_log = TaskEventLog("task-001")
    event_log.append(make_event(EventType.TASK_CREATED, 1))

    with pytest.raises(ValidationError, match="sequence"):
        event_log.append(make_event(EventType.TASK_ACCEPTED, 1))
