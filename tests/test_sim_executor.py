import pytest

from robot.events import EventType
from robot.models import ExecutionMode, FailureCode, Task, ValidationError, Zone
from robot.sim_executor import APPROVED_SUCCESS_EVENT_SEQUENCE, run_simulated_mission


def make_task(mode=ExecutionMode.SIMULATION) -> Task:
    return Task(
        task_id="sample-task-001",
        object_id="VALERA-CUBE-001",
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=mode,
    )


def test_simulated_mission_emits_approved_success_sequence():
    event_log = run_simulated_mission(make_task())

    assert [event.event_type for event in event_log.events] == list(APPROVED_SUCCESS_EVENT_SEQUENCE)


def test_simulated_mission_sequences_are_monotonic_from_one():
    event_log = run_simulated_mission(make_task())

    assert [event.sequence for event in event_log.events] == list(range(1, len(event_log.events) + 1))


def test_simulated_mission_uses_one_task_and_correlation_id():
    event_log = run_simulated_mission(make_task())
    task_ids = {event.task_id for event in event_log.events}
    correlation_ids = {event.correlation_id for event in event_log.events}

    assert task_ids == {"sample-task-001"}
    assert correlation_ids == {"sample-task-001-simulation-mission"}


def test_simulated_mission_ends_with_completed_and_no_later_events():
    event_log = run_simulated_mission(make_task())

    assert event_log.events[-1].event_type == EventType.TASK_COMPLETED
    assert event_log.terminal_event_type == EventType.TASK_COMPLETED
    assert EventType.TASK_COMPLETED not in [event.event_type for event in event_log.events[:-1]]


def test_simulated_mission_payloads_include_object_and_relevant_zones():
    event_log = run_simulated_mission(make_task())

    for event in event_log.events:
        assert event.payload["object_id"] == "VALERA-CUBE-001"
        assert event.payload["pickup_zone"] == Zone.PICKUP_ZONE.value
        assert event.payload["delivery_zone"] == Zone.DELIVERY_ZONE.value
        assert event.payload["status"]

    arrivals = [event for event in event_log.events if event.event_type == EventType.ROUTE_ARRIVED]
    assert [event.payload["current_target_zone"] for event in arrivals] == [
        Zone.PICKUP_ZONE.value,
        Zone.DELIVERY_ZONE.value,
    ]


def test_simulated_mission_uses_deterministic_timestamps():
    event_log = run_simulated_mission(make_task())

    assert event_log.events[0].occurred_at.isoformat() == "2026-07-02T12:00:00+00:00"
    assert event_log.events[-1].occurred_at.isoformat() == "2026-07-02T12:00:13+00:00"


def test_simulator_rejects_non_simulation_mode():
    with pytest.raises(ValidationError) as exc:
        run_simulated_mission(make_task(ExecutionMode.REAL_VISION))

    assert exc.value.code == FailureCode.INVALID_TASK


def test_hardware_mode_still_fails_closed_and_is_not_accepted_by_simulator():
    with pytest.raises(ValidationError) as task_exc:
        make_task(ExecutionMode.HARDWARE)
    assert task_exc.value.code == FailureCode.HARDWARE_MODE_NOT_ENABLED

    task = object.__new__(Task)
    task.task_id = "hardware-task-001"
    task.object_id = "VALERA-CUBE-001"
    task.pickup_zone = Zone.PICKUP_ZONE
    task.delivery_zone = Zone.DELIVERY_ZONE
    task.mode = ExecutionMode.HARDWARE
    task.description = ""

    with pytest.raises(ValidationError) as sim_exc:
        run_simulated_mission(task)
    assert sim_exc.value.code == FailureCode.HARDWARE_MODE_NOT_ENABLED
