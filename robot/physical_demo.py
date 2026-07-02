from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol

from robot.events import EventEnvelope, EventError, EventType
from robot.live_camera import LiveCameraDisabledError, run_live_camera_marker_probe
from robot.models import ExecutionMode, FailureCode, Task, Zone
from robot.state_machine import TaskEventLog


PHYSICAL_DEMO_SOURCE = "valera.physical_demo"
PHYSICAL_DEMO_TIMESTAMP_BASE = datetime(2026, 7, 2, 13, 0, tzinfo=timezone.utc)

PHYSICAL_DEMO_SUCCESS_EVENT_SEQUENCE = (
    EventType.TASK_CREATED,
    EventType.TASK_ACCEPTED,
    EventType.PLAN_CREATED,
    EventType.ROUTE_STARTED,
    EventType.ROUTE_ARRIVED,
    EventType.OBJECT_SEARCH_STARTED,
    EventType.OBJECT_FOUND,
    EventType.GRASP_STARTED,
    EventType.OBJECT_GRASPED,
    EventType.DELIVERY_STARTED,
    EventType.OBJECT_RELEASED,
    EventType.DELIVERY_COMPLETED,
    EventType.TASK_COMPLETED,
)


class ConfirmationProvider(Protocol):
    def confirm(self, step_name: str, prompt: str) -> bool:
        """Return True only when the operator explicitly confirms the step."""


@dataclass
class CliConfirmationProvider:
    def confirm(self, step_name: str, prompt: str) -> bool:
        response = input(f"{prompt} Type yes to confirm {step_name}: ")
        return response.strip().lower() == "yes"


@dataclass
class ListConfirmationProvider:
    confirmations: list[bool]

    def confirm(self, step_name: str, prompt: str) -> bool:
        if not self.confirmations:
            return False
        return self.confirmations.pop(0)


ProbeRunner = Callable[..., EventEnvelope]


def run_physical_demo(
    *,
    task_id: str,
    object_id: str,
    camera_index: int,
    enable_live_camera: bool,
    output_root: Path,
    confirmation_provider: ConfirmationProvider | Callable[[str, str], bool],
    correlation_id: str | None = None,
    live_probe_runner: ProbeRunner = run_live_camera_marker_probe,
) -> TaskEventLog:
    if not enable_live_camera:
        raise LiveCameraDisabledError(
            "physical demo live camera access requires --enable-live-camera before camera access"
        )

    task = Task(
        task_id=task_id,
        object_id=object_id,
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.REAL_VISION,
        description=(
            "Physical demo with live vision and operator-confirmed manipulation; "
            "no robot movement or arm control"
        ),
    )
    correlation = correlation_id or f"{task.task_id}-physical-demo"
    event_log = TaskEventLog(task.task_id)

    for event_type in (
        EventType.TASK_CREATED,
        EventType.TASK_ACCEPTED,
        EventType.PLAN_CREATED,
        EventType.ROUTE_STARTED,
        EventType.ROUTE_ARRIVED,
        EventType.OBJECT_SEARCH_STARTED,
    ):
        event_log.append(_event(task, event_type, correlation, event_log.last_sequence + 1))

    detection_event = live_probe_runner(
        task_id=task.task_id,
        object_id=task.object_id,
        camera_index=camera_index,
        enabled=True,
        output_root=Path(output_root),
        sequence=event_log.last_sequence + 1,
        correlation_id=correlation,
    )
    event_log.append(detection_event)

    if detection_event.event_type == EventType.OBJECT_NOT_FOUND:
        event_log.append(
            _failed_event(
                task,
                correlation,
                event_log.last_sequence + 1,
                "live camera did not find the target object",
                FailureCode.OBJECT_NOT_FOUND,
            )
        )
        event_log.validate()
        return event_log

    if detection_event.event_type != EventType.OBJECT_FOUND:
        event_log.append(
            _failed_event(
                task,
                correlation,
                event_log.last_sequence + 1,
                f"live camera returned unexpected event type: {detection_event.event_type.value}",
                FailureCode.INVALID_TASK,
            )
        )
        event_log.validate()
        return event_log

    for confirmation in _operator_confirmations():
        if not _confirm(confirmation_provider, confirmation.step_name, confirmation.prompt):
            event_log.append(
                _failed_event(
                    task,
                    correlation,
                    event_log.last_sequence + 1,
                    f"operator cancelled during {confirmation.step_name}",
                    FailureCode.MANUAL_CANCELLED,
                )
            )
            event_log.validate()
            return event_log
        event_log.append(
            _event(task, confirmation.event_type, correlation, event_log.last_sequence + 1)
        )

    event_log.append(_event(task, EventType.TASK_COMPLETED, correlation, event_log.last_sequence + 1))
    event_log.validate()
    return event_log


def write_physical_demo_replay(event_log: TaskEventLog, replay_path: Path) -> None:
    replay_path.parent.mkdir(parents=True, exist_ok=True)
    replay_path.write_text(
        json.dumps([event.to_dict() for event in event_log.events], indent=2) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class _OperatorConfirmation:
    step_name: str
    prompt: str
    event_type: EventType


def _operator_confirmations() -> tuple[_OperatorConfirmation, ...]:
    return (
        _OperatorConfirmation(
            "confirm_grasp_started",
            "Confirm the operator has started the physical grasp step.",
            EventType.GRASP_STARTED,
        ),
        _OperatorConfirmation(
            "confirm_object_grasped",
            "Confirm the object is physically grasped or secured.",
            EventType.OBJECT_GRASPED,
        ),
        _OperatorConfirmation(
            "confirm_delivery_started",
            "Confirm the operator has started the delivery step.",
            EventType.DELIVERY_STARTED,
        ),
        _OperatorConfirmation(
            "confirm_object_released",
            "Confirm the object has been physically released.",
            EventType.OBJECT_RELEASED,
        ),
        _OperatorConfirmation(
            "confirm_delivery_completed",
            "Confirm the physical delivery step is complete.",
            EventType.DELIVERY_COMPLETED,
        ),
    )


def _confirm(
    provider: ConfirmationProvider | Callable[[str, str], bool], step_name: str, prompt: str
) -> bool:
    if hasattr(provider, "confirm"):
        return bool(provider.confirm(step_name, prompt))
    return bool(provider(step_name, prompt))


def _event(
    task: Task,
    event_type: EventType,
    correlation_id: str,
    sequence: int,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"{correlation_id}-{sequence:03d}",
        task_id=task.task_id,
        correlation_id=correlation_id,
        sequence=sequence,
        event_type=event_type,
        occurred_at=PHYSICAL_DEMO_TIMESTAMP_BASE + timedelta(seconds=sequence - 1),
        source=PHYSICAL_DEMO_SOURCE,
        mode=ExecutionMode.REAL_VISION,
        payload=_payload_for_event(task, event_type),
    )


def _failed_event(
    task: Task,
    correlation_id: str,
    sequence: int,
    reason: str,
    code: FailureCode,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"{correlation_id}-{sequence:03d}",
        task_id=task.task_id,
        correlation_id=correlation_id,
        sequence=sequence,
        event_type=EventType.TASK_FAILED,
        occurred_at=PHYSICAL_DEMO_TIMESTAMP_BASE + timedelta(seconds=sequence - 1),
        source=PHYSICAL_DEMO_SOURCE,
        mode=ExecutionMode.REAL_VISION,
        payload={"object_id": task.object_id, "status": "failed", "reason": reason},
        error=EventError(code=code, message=reason),
    )


def _payload_for_event(task: Task, event_type: EventType) -> dict[str, object]:
    base = {
        "object_id": task.object_id,
        "pickup_zone": task.pickup_zone.value,
        "delivery_zone": task.delivery_zone.value,
    }
    if event_type == EventType.TASK_CREATED:
        return base | {
            "status": "created",
            "description": task.description,
        }
    if event_type == EventType.TASK_ACCEPTED:
        return base | {"status": "accepted"}
    if event_type == EventType.PLAN_CREATED:
        return base | {
            "status": "planned",
            "planned_route": [Zone.BASE.value, task.pickup_zone.value, task.delivery_zone.value],
            "note": "physical demo uses operator-confirmed positioning",
        }
    if event_type == EventType.ROUTE_STARTED:
        return base | {
            "from_zone": Zone.BASE.value,
            "to_zone": task.pickup_zone.value,
            "status": "started",
            "note": "operator_confirmed / simulated positioning",
        }
    if event_type == EventType.ROUTE_ARRIVED:
        return base | {
            "from_zone": Zone.BASE.value,
            "to_zone": task.pickup_zone.value,
            "status": "arrived",
            "note": "operator_confirmed / simulated positioning",
        }
    if event_type == EventType.OBJECT_SEARCH_STARTED:
        return base | {"status": "searching"}
    if event_type == EventType.GRASP_STARTED:
        return base | {"status": "started", "confirmation": "operator"}
    if event_type == EventType.OBJECT_GRASPED:
        return base | {"status": "grasped", "confirmation": "operator"}
    if event_type == EventType.DELIVERY_STARTED:
        return base | {"status": "started", "confirmation": "operator"}
    if event_type == EventType.OBJECT_RELEASED:
        return base | {"status": "released", "confirmation": "operator"}
    if event_type == EventType.DELIVERY_COMPLETED:
        return base | {"status": "completed", "confirmation": "operator"}
    if event_type == EventType.TASK_COMPLETED:
        return {"object_id": task.object_id, "status": "completed"}
    return base | {"status": event_type.value}
