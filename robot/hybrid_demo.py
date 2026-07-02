import json
from pathlib import Path

from robot.events import EventType
from robot.models import ExecutionMode, Task, Zone
from robot.sim_executor import run_simulated_mission
from robot.state_machine import TaskEventLog
from robot.vision import run_fixture_detection


def run_hybrid_fixture_mission(
    *,
    task_id: str,
    object_id: str,
    evidence_base_path: Path,
    fixture_path: Path,
) -> TaskEventLog:
    simulation_task = Task(
        task_id=task_id,
        object_id=object_id,
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.SIMULATION,
        description="Hybrid fixture mission with simulated movement and real vision",
    )
    simulated_log = run_simulated_mission(simulation_task)
    object_found_event = next(
        event for event in simulated_log.events if event.event_type == EventType.OBJECT_FOUND
    )

    vision_task = Task(
        task_id=task_id,
        object_id=object_id,
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.REAL_VISION,
        description="Hybrid fixture object detection",
    )
    vision_event = run_fixture_detection(
        task=vision_task,
        image_path=fixture_path,
        sequence=object_found_event.sequence,
        correlation_id=object_found_event.correlation_id,
        evidence_base_path=evidence_base_path,
        occurred_at=object_found_event.occurred_at,
    )

    hybrid_log = TaskEventLog(task_id)
    for event in simulated_log.events:
        if event.event_type == EventType.OBJECT_FOUND:
            hybrid_log.append(vision_event)
        else:
            hybrid_log.append(event)

    hybrid_log.validate()
    return hybrid_log


def write_hybrid_replay(event_log: TaskEventLog, replay_path: Path) -> None:
    replay_path.parent.mkdir(parents=True, exist_ok=True)
    replay_path.write_text(
        json.dumps([event.to_dict() for event in event_log.events], indent=2) + "\n",
        encoding="utf-8",
    )
