from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robot.models import ExecutionMode, Task, Zone
from robot.sim_executor import run_simulated_mission


def main() -> None:
    task = Task(
        task_id="sample-task-001",
        object_id="VALERA-CUBE-001",
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.SIMULATION,
        description="Sample simulated pickup and delivery task",
    )
    event_log = run_simulated_mission(task)
    event_log.validate()
    print(f"Validated sample task {task.task_id} with {len(event_log.events)} events.")


if __name__ == "__main__":
    main()
