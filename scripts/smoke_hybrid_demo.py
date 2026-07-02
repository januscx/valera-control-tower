from dataclasses import dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.render import render_dashboard_from_replay
from robot.events import EventType
from robot.hybrid_demo import run_hybrid_fixture_mission, write_hybrid_replay
from robot.models import ExecutionMode
from robot.vision import generate_marker_fixture


TASK_ID = "hybrid-fixture-task-001"
OBJECT_ID = "VALERA-CUBE-001"
MARKER_ID = 7


@dataclass(frozen=True)
class SmokeResult:
    task_id: str
    final_status: str
    event_count: int
    replay_path: Path
    dashboard_path: Path
    evidence_paths: list[Path]


def run_hybrid_demo_smoke(output_root: Path) -> SmokeResult:
    output_root = Path(output_root)
    fixture_path = output_root / "tmp" / "hybrid-marker-fixture.png"
    replay_path = output_root / "data" / "runs" / TASK_ID / "replay.json"
    dashboard_path = output_root / "data" / "runs" / TASK_ID / "dashboard.html"

    generate_marker_fixture(fixture_path, marker_id=MARKER_ID)
    event_log = run_hybrid_fixture_mission(
        task_id=TASK_ID,
        object_id=OBJECT_ID,
        evidence_base_path=output_root,
        fixture_path=fixture_path,
    )
    write_hybrid_replay(event_log, replay_path)
    summary = render_dashboard_from_replay(replay_path, dashboard_path)

    _require(replay_path.is_file(), f"replay file is missing: {replay_path}")
    _require(dashboard_path.is_file(), f"dashboard file is missing: {dashboard_path}")
    _require(summary.final_status == "completed", f"expected completed, got {summary.final_status}")
    _require(summary.event_count == 14, f"expected 14 events, got {summary.event_count}")

    object_found = _object_found_event(event_log.events)
    _require(
        object_found.mode == ExecutionMode.REAL_VISION,
        f"object.found mode must be real_vision, got {object_found.mode.value}",
    )
    for field_name in ("marker_id", "detection_score", "corners", "bounding_box"):
        _require(field_name in object_found.payload, f"object.found missing {field_name}")

    evidence_refs = object_found.evidence_refs
    _require(len(evidence_refs) == 2, f"expected 2 evidence refs, got {len(evidence_refs)}")
    for evidence_ref in evidence_refs:
        _require(hasattr(evidence_ref, "relative_path"), "evidence ref is not structured")

    evidence_paths = [evidence_ref.local_path(output_root) for evidence_ref in evidence_refs]
    _require(any(path.name.endswith("-raw.png") for path in evidence_paths), "raw evidence file missing")
    _require(
        any(path.name.endswith("-annotated.png") for path in evidence_paths),
        "annotated evidence file missing",
    )
    for evidence_path in evidence_paths:
        _require(evidence_path.is_file(), f"evidence file is missing: {evidence_path}")

    dashboard_html = dashboard_path.read_text(encoding="utf-8")
    _require('href="../../evidence/' in dashboard_html, "dashboard missing evidence links")
    _require("<img " in dashboard_html, "dashboard missing evidence preview image tags")
    _require('class="evidence-preview"' in dashboard_html, "dashboard missing evidence preview class")
    _require("task.completed" in dashboard_html, "dashboard missing task.completed")

    return SmokeResult(
        task_id=summary.task_id,
        final_status=summary.final_status,
        event_count=summary.event_count,
        replay_path=replay_path,
        dashboard_path=dashboard_path,
        evidence_paths=evidence_paths,
    )


def _object_found_event(events):
    for event in events:
        if event.event_type == EventType.OBJECT_FOUND:
            return event
    raise RuntimeError("object.found event is missing")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    try:
        result = run_hybrid_demo_smoke(PROJECT_ROOT)
    except Exception:
        print("FAIL: Hybrid Evidence Demo smoke verification")
        raise

    print("PASS: Hybrid Evidence Demo smoke verification")
    print(f"Task id: {result.task_id}")
    print(f"Event count: {result.event_count}")
    print(f"Replay path: {result.replay_path}")
    print(f"Dashboard path: {result.dashboard_path}")
    print("Evidence paths:")
    for evidence_path in result.evidence_paths:
        print(f"- {evidence_path}")


if __name__ == "__main__":
    main()
