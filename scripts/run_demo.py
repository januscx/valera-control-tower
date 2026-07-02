import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robot.models import ExecutionMode, Task, Zone
from robot.sim_executor import run_simulated_mission


REPLAY_PATH = PROJECT_ROOT / "data" / "replay" / "sample-success.json"


def make_sample_task() -> Task:
    return Task(
        task_id="sample-task-001",
        object_id="VALERA-CUBE-001",
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.SIMULATION,
        description="Sample simulated pickup and delivery task",
    )


def write_replay(event_log, path: Path = REPLAY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([event.to_dict() for event in event_log.events], indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    task = make_sample_task()
    event_log = run_simulated_mission(task)
    event_log.validate()
    write_replay(event_log)

    print(f"Mission {task.task_id}: {event_log.terminal_event_type.value}")
    print(f"Object: {task.object_id}")
    print(f"Route: {task.pickup_zone.value} -> {task.delivery_zone.value}")
    print(f"Events: {len(event_log.events)} written to {REPLAY_PATH}")


if __name__ == "__main__":
    main()
