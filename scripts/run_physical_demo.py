from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.render import render_dashboard_from_replay
from robot.events import EventType
from robot.physical_demo import (
    CliConfirmationProvider,
    run_physical_demo,
    write_physical_demo_replay,
)


TASK_ID = "physical-demo-001"
OBJECT_ID = "VALERA-CUBE-001"
RUN_DIR = PROJECT_ROOT / "data" / "runs" / TASK_ID
REPLAY_PATH = RUN_DIR / "replay.json"
DASHBOARD_PATH = RUN_DIR / "dashboard.html"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Valera's physical demo with live vision and operator confirmations."
    )
    parser.add_argument(
        "--enable-live-camera",
        action="store_true",
        help="explicitly allow opening the local camera for live marker detection",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index to probe; defaults to 0 for /dev/video0",
    )
    args = parser.parse_args()

    print(
        "Valera physical demo: live camera perception plus operator-confirmed "
        "manipulation steps."
    )
    print("This runner does not move the robot, control the arm, or call actuators.")
    if not args.enable_live_camera:
        print("Live camera access is fail-closed; rerun with --enable-live-camera to opt in.")
        return 2

    event_log = run_physical_demo(
        task_id=TASK_ID,
        object_id=OBJECT_ID,
        camera_index=args.camera_index,
        enable_live_camera=True,
        output_root=PROJECT_ROOT,
        confirmation_provider=CliConfirmationProvider(),
    )
    write_physical_demo_replay(event_log, REPLAY_PATH)
    summary = render_dashboard_from_replay(REPLAY_PATH, DASHBOARD_PATH)

    object_found = next(
        (event for event in event_log.events if event.event_type == EventType.OBJECT_FOUND),
        None,
    )

    print(f"Task id: {summary.task_id}")
    print(f"Final status: {summary.final_status}")
    print(f"Event count: {summary.event_count}")
    print(f"Replay path: {REPLAY_PATH}")
    print(f"Dashboard path: {DASHBOARD_PATH}")
    print("Evidence paths:")
    if object_found is None or not object_found.evidence_refs:
        print("- none")
    else:
        for evidence_ref in object_found.evidence_refs:
            print(f"- {evidence_ref.relative_path}")
    return 0 if event_log.terminal_event_type == EventType.TASK_COMPLETED else 1


if __name__ == "__main__":
    raise SystemExit(main())
