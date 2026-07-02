from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robot.events import EventEnvelope, EventType
from robot.models import ExecutionMode, Task, Zone
from robot.state_machine import TaskEventLog


def make_event(task_id: str, sequence: int, event_type: EventType) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"sample-event-{sequence}",
        task_id=task_id,
        correlation_id="sample-correlation-001",
        sequence=sequence,
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc),
        source="validate_sample_task",
        mode=ExecutionMode.SIMULATION,
        payload={},
    )


def main() -> None:
    task = Task(
        task_id="sample-task-001",
        object_id="VALERA-CUBE-001",
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.SIMULATION,
        description="Sample simulated pickup and delivery task",
    )
    event_log = TaskEventLog(task.task_id)

    for sequence, event_type in enumerate(
        (
            EventType.TASK_CREATED,
            EventType.TASK_ACCEPTED,
            EventType.PLAN_CREATED,
            EventType.OBJECT_FOUND,
            EventType.TASK_COMPLETED,
        ),
        start=1,
    ):
        event_log.append(make_event(task.task_id, sequence, event_type))

    event_log.validate()
    print(f"Validated sample task {task.task_id} with {len(event_log.events)} events.")


if __name__ == "__main__":
    main()
