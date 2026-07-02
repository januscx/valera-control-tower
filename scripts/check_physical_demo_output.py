from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASK_ID = "physical-demo-001"
DEFAULT_MARKER_ID = 7
LIVE_CAMERA_SOURCE = "valera.live_camera_probe"
EXPECTED_EVENT_TYPES = (
    "task.created",
    "task.accepted",
    "plan.created",
    "route.started",
    "route.arrived",
    "object.search_started",
    "object.found",
    "grasp.started",
    "object.grasped",
    "delivery.started",
    "object.released",
    "delivery.completed",
    "task.completed",
)


class PhysicalDemoOutputError(RuntimeError):
    pass


@dataclass(frozen=True)
class PhysicalDemoOutputCheck:
    task_id: str
    event_count: int
    replay_path: Path
    dashboard_path: Path
    object_found_source: str
    evidence_files: list[Path]


def check_physical_demo_output(
    *,
    project_root: Path,
    task_id: str = DEFAULT_TASK_ID,
    expected_marker_id: int = DEFAULT_MARKER_ID,
) -> PhysicalDemoOutputCheck:
    project_root = Path(project_root)
    replay_path = project_root / "data" / "runs" / task_id / "replay.json"
    dashboard_path = project_root / "data" / "runs" / task_id / "dashboard.html"

    _require(replay_path.is_file(), f"replay JSON is missing: {replay_path}")
    _require(dashboard_path.is_file(), f"dashboard HTML is missing: {dashboard_path}")

    try:
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PhysicalDemoOutputError(f"replay JSON is invalid: {exc}") from exc

    _require(isinstance(replay, list), "replay JSON must be a list")
    _require(len(replay) == len(EXPECTED_EVENT_TYPES), f"expected 13 events, got {len(replay)}")
    _require(
        [event.get("sequence") for event in replay] == list(range(1, 14)),
        "event sequences must be exactly 1..13",
    )
    _require(
        [event.get("event_type") for event in replay] == list(EXPECTED_EVENT_TYPES),
        "event types do not match the expected physical demo success sequence",
    )
    _require(replay[-1].get("event_type") == "task.completed", "final event must be task.completed")
    _require(_final_status(replay[-1]) == "completed", "final status must infer as completed")
    _require(_occurred_at_values_are_monotonic(replay), "occurred_at values must be monotonic")

    object_found = replay[6]
    _require(object_found.get("event_type") == "object.found", "sequence 7 must be object.found")
    _require(
        object_found.get("source") == LIVE_CAMERA_SOURCE,
        f"object.found source must be {LIVE_CAMERA_SOURCE}",
    )
    _require(object_found.get("mode") == "real_vision", "object.found mode must be real_vision")

    payload = object_found.get("payload")
    _require(isinstance(payload, dict), "object.found payload must be an object")
    _require(payload.get("object_id") == "VALERA-CUBE-001", "object.found object_id is wrong")
    _require(payload.get("marker_id") == expected_marker_id, "object.found marker_id is wrong")
    _require(payload.get("detection_score") == 1.0, "object.found detection_score must be 1.0")
    _require(payload.get("status") == "found", "object.found status must be found")

    evidence_refs = object_found.get("evidence_refs")
    _require(isinstance(evidence_refs, list), "object.found evidence_refs must be a list")
    _require(len(evidence_refs) == 2, f"expected 2 object.found evidence refs, got {len(evidence_refs)}")

    evidence_files = _validate_evidence_refs(project_root, evidence_refs)
    _validate_dashboard(dashboard_path)

    return PhysicalDemoOutputCheck(
        task_id=task_id,
        event_count=len(replay),
        replay_path=replay_path,
        dashboard_path=dashboard_path,
        object_found_source=str(object_found.get("source")),
        evidence_files=evidence_files,
    )


def _validate_evidence_refs(project_root: Path, evidence_refs: list[Any]) -> list[Path]:
    raw_refs = []
    annotated_refs = []
    evidence_files = []

    for ref in evidence_refs:
        _require(isinstance(ref, dict), "evidence refs must be structured objects")
        _require(
            ref.get("source_adapter") == LIVE_CAMERA_SOURCE,
            f"evidence source_adapter must be {LIVE_CAMERA_SOURCE}",
        )
        _require(ref.get("media_type") == "image/png", "evidence media_type must be image/png")

        relative_path = ref.get("relative_path")
        _require(isinstance(relative_path, str), "evidence relative_path must be a string")
        posix_path = PurePosixPath(relative_path)
        _require(not posix_path.is_absolute(), "evidence relative_path must be relative")
        _require(".." not in posix_path.parts, "evidence relative_path must not contain ..")
        _require(
            posix_path.is_relative_to(PurePosixPath("data/evidence")),
            "evidence relative_path must stay under data/evidence",
        )
        _require(posix_path.suffix == ".png", "evidence file must be a PNG")

        evidence_path = project_root / relative_path
        _require(evidence_path.is_file(), f"evidence file is missing: {evidence_path}")
        evidence_files.append(evidence_path)

        if posix_path.name.endswith("-raw.png"):
            raw_refs.append(ref)
        if posix_path.name.endswith("-annotated.png"):
            annotated_refs.append(ref)

    _require(len(raw_refs) == 1, "object.found must have one raw PNG evidence ref")
    _require(len(annotated_refs) == 1, "object.found must have one annotated PNG evidence ref")
    return evidence_files


def _validate_dashboard(dashboard_path: Path) -> None:
    html = dashboard_path.read_text(encoding="utf-8")
    for text in (
        "Final status",
        "completed",
        "object.found",
        LIVE_CAMERA_SOURCE,
        "task.completed",
    ):
        _require(text in html, f"dashboard missing {text}")
    _require("href=" in html, "dashboard missing evidence hrefs")
    _require("<img " in html, "dashboard missing evidence preview imgs")
    _require("evidence-preview" in html, "dashboard missing evidence preview class")


def _occurred_at_values_are_monotonic(events: list[dict[str, Any]]) -> bool:
    previous: datetime | None = None
    for event in events:
        raw_value = event.get("occurred_at")
        if not isinstance(raw_value, str):
            raise PhysicalDemoOutputError("occurred_at must be an ISO timestamp string")
        try:
            current = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PhysicalDemoOutputError(f"occurred_at is invalid: {raw_value}") from exc
        if previous is not None and current < previous:
            return False
        previous = current
    return True


def _final_status(last_event: dict[str, Any]) -> str:
    payload = last_event.get("payload")
    payload_status = payload.get("status") if isinstance(payload, dict) else None
    if last_event.get("event_type") == "task.completed" or payload_status == "completed":
        return "completed"
    return "unknown"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PhysicalDemoOutputError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate already-generated Valera physical demo output files."
    )
    parser.add_argument("--task-id", default=DEFAULT_TASK_ID)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--expected-marker-id", type=int, default=DEFAULT_MARKER_ID)
    args = parser.parse_args(argv)

    try:
        result = check_physical_demo_output(
            project_root=args.project_root,
            task_id=args.task_id,
            expected_marker_id=args.expected_marker_id,
        )
    except PhysicalDemoOutputError as exc:
        print("FAIL: Physical demo output verification")
        print(f"Check failed: {exc}")
        return 1

    print("PASS: Physical demo output verification")
    print(f"Task id: {result.task_id}")
    print(f"Event count: {result.event_count}")
    print(f"Replay path: {result.replay_path}")
    print(f"Dashboard path: {result.dashboard_path}")
    print(f"Object found source: {result.object_found_source}")
    print("Evidence files:")
    for evidence_file in result.evidence_files:
        print(f"- {evidence_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
