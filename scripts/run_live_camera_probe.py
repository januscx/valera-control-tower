from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.render import render_dashboard_from_replay
from robot.live_camera import run_live_camera_marker_probe


TASK_ID = "live-camera-probe-001"
OBJECT_ID = "VALERA-CUBE-001"
RUN_DIR = PROJECT_ROOT / "data" / "runs" / TASK_ID
REPLAY_PATH = RUN_DIR / "replay.json"
DASHBOARD_PATH = RUN_DIR / "dashboard.html"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Valera's optional one-frame live camera marker probe."
    )
    parser.add_argument(
        "--enable-live-camera",
        action="store_true",
        help="explicitly allow opening the local camera for one frame",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index to probe; defaults to 0 for /dev/video0",
    )
    args = parser.parse_args()

    print("Valera live camera probe: perception only, no robot movement or arm control.")
    if not args.enable_live_camera:
        print("Live camera access is fail-closed; rerun with --enable-live-camera to opt in.")
        return 2

    event = run_live_camera_marker_probe(
        task_id=TASK_ID,
        object_id=OBJECT_ID,
        camera_index=args.camera_index,
        enabled=True,
        output_root=PROJECT_ROOT,
    )

    REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPLAY_PATH.write_text(json.dumps([event.to_dict()], indent=2) + "\n", encoding="utf-8")
    render_dashboard_from_replay(REPLAY_PATH, DASHBOARD_PATH)

    print(f"Task id: {TASK_ID}")
    print(f"Event type: {event.event_type.value}")
    print(f"Mode: {event.mode.value}")
    print(f"Replay path: {REPLAY_PATH}")
    print(f"Dashboard path: {DASHBOARD_PATH}")
    print("Evidence paths:")
    for evidence_ref in event.evidence_refs:
        print(f"- {evidence_ref.relative_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
