from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robot.models import ExecutionMode, Task, Zone
from robot.vision import generate_marker_fixture, run_fixture_detection


FIXTURE_PATH = PROJECT_ROOT / "tmp" / "vision-marker-fixture.png"


def main() -> None:
    task = Task(
        task_id="vision-fixture-task-001",
        object_id="VALERA-CUBE-001",
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.REAL_VISION,
        description="Fixture-based real_vision marker detection",
    )

    generate_marker_fixture(FIXTURE_PATH, marker_id=7)
    event = run_fixture_detection(
        task=task,
        image_path=FIXTURE_PATH,
        sequence=1,
        correlation_id=f"{task.task_id}-real-vision-fixture",
        evidence_base_path=PROJECT_ROOT,
    )

    print(f"Event type: {event.event_type.value}")
    print(f"Task id: {event.task_id}")
    print(f"Object id: {event.payload['object_id']}")
    if "marker_id" in event.payload:
        print(f"Marker id: {event.payload['marker_id']}")
    print("Evidence paths:")
    for evidence_ref in event.evidence_refs:
        print(f"- {evidence_ref.relative_path}")


if __name__ == "__main__":
    main()
