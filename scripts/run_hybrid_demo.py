from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.render import render_dashboard_from_replay
from robot.events import EventType
from robot.hybrid_demo import run_hybrid_fixture_mission, write_hybrid_replay
from robot.vision import generate_marker_fixture


TASK_ID = "hybrid-fixture-task-001"
OBJECT_ID = "VALERA-CUBE-001"
FIXTURE_PATH = PROJECT_ROOT / "tmp" / "hybrid-marker-fixture.png"
RUN_DIR = PROJECT_ROOT / "data" / "runs" / TASK_ID
REPLAY_PATH = RUN_DIR / "replay.json"
DASHBOARD_PATH = RUN_DIR / "dashboard.html"


def main() -> None:
    generate_marker_fixture(FIXTURE_PATH, marker_id=7)
    event_log = run_hybrid_fixture_mission(
        task_id=TASK_ID,
        object_id=OBJECT_ID,
        evidence_base_path=PROJECT_ROOT,
        fixture_path=FIXTURE_PATH,
    )
    write_hybrid_replay(event_log, REPLAY_PATH)
    summary = render_dashboard_from_replay(REPLAY_PATH, DASHBOARD_PATH)

    object_found = next(
        event for event in event_log.events if event.event_type == EventType.OBJECT_FOUND
    )

    print(f"Task id: {summary.task_id}")
    print(f"Final status: {summary.final_status}")
    print(f"Event count: {summary.event_count}")
    print(f"Replay path: {REPLAY_PATH}")
    print(f"Dashboard path: {DASHBOARD_PATH}")
    print("Evidence paths:")
    for evidence_ref in object_found.evidence_refs:
        print(f"- {evidence_ref.relative_path}")


if __name__ == "__main__":
    main()
