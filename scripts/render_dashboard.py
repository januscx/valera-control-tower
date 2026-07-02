from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.render import render_dashboard_from_replay


DEFAULT_REPLAY_PATH = PROJECT_ROOT / "data" / "replay" / "sample-success.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "dashboard" / "index.html"


def main() -> None:
    summary = render_dashboard_from_replay(DEFAULT_REPLAY_PATH, DEFAULT_OUTPUT_PATH)

    print(f"Input replay: {DEFAULT_REPLAY_PATH}")
    print(f"Output dashboard: {DEFAULT_OUTPUT_PATH}")
    print(f"Task id: {summary.task_id}")
    print(f"Final status: {summary.final_status}")
    print(f"Event count: {summary.event_count}")


if __name__ == "__main__":
    main()
