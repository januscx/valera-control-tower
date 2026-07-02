from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robot.evidence import create_evidence_ref


def main() -> None:
    task_id = "sample-task-001"
    raw = create_evidence_ref(
        task_id=task_id,
        evidence_id="sample-evidence-001",
        variant="raw",
        media_type="image/png",
        capture_mode="simulation",
        source_adapter="sim-evidence-adapter",
        linked_event_id="sample-event-001",
    )
    annotated = create_evidence_ref(
        task_id=task_id,
        evidence_id="sample-evidence-001",
        variant="annotated",
        media_type="image/png",
        capture_mode="simulation",
        source_adapter="sim-evidence-adapter",
        linked_event_id="sample-event-001",
    )

    raw.validate_for_task(task_id)
    annotated.validate_for_task(task_id)

    print(f"Validated evidence refs for {task_id}:")
    print(f"- {raw.relative_path}")
    print(f"- {annotated.relative_path}")


if __name__ == "__main__":
    main()
