import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.check_physical_demo_output import (
    LIVE_CAMERA_SOURCE,
    PhysicalDemoOutputError,
    check_physical_demo_output,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "physical-demo-001"
EVENT_TYPES = [
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
]


def test_passing_physical_demo_output_validates_successfully(tmp_path):
    write_valid_output(tmp_path)

    result = check_physical_demo_output(project_root=tmp_path)

    assert result.task_id == TASK_ID
    assert result.event_count == 13
    assert result.object_found_source == LIVE_CAMERA_SOURCE
    assert len(result.evidence_files) == 2


def test_missing_replay_fails(tmp_path):
    write_valid_output(tmp_path)
    (tmp_path / "data" / "runs" / TASK_ID / "replay.json").unlink()

    assert_check_fails(tmp_path, "replay JSON is missing")


def test_missing_dashboard_fails(tmp_path):
    write_valid_output(tmp_path)
    (tmp_path / "data" / "runs" / TASK_ID / "dashboard.html").unlink()

    assert_check_fails(tmp_path, "dashboard HTML is missing")


def test_wrong_event_count_fails(tmp_path):
    replay = valid_replay()
    write_output(tmp_path, replay[:-1])

    assert_check_fails(tmp_path, "expected 13 events, got 12")


def test_wrong_event_sequence_fails(tmp_path):
    replay = valid_replay()
    replay[8]["event_type"] = "delivery.started"
    write_output(tmp_path, replay)

    assert_check_fails(tmp_path, "event types do not match")


def test_non_monotonic_occurred_at_fails(tmp_path):
    replay = valid_replay()
    replay[5]["occurred_at"] = "2026-07-02T14:00:10+00:00"
    replay[6]["occurred_at"] = "2026-07-02T14:00:09+00:00"
    write_output(tmp_path, replay)

    assert_check_fails(tmp_path, "occurred_at values must be monotonic")


def test_object_found_wrong_source_fails(tmp_path):
    replay = valid_replay()
    replay[6]["source"] = "valera.real_vision_fixture"
    write_output(tmp_path, replay)

    assert_check_fails(tmp_path, "object.found source")


def test_object_found_missing_evidence_fails(tmp_path):
    replay = valid_replay()
    replay[6]["evidence_refs"] = []
    write_output(tmp_path, replay)

    assert_check_fails(tmp_path, "expected 2 object.found evidence refs")


def test_missing_evidence_file_fails(tmp_path):
    replay = valid_replay()
    write_output(tmp_path, replay)
    (tmp_path / "data" / "evidence" / TASK_ID / "physical-demo-001-007-raw.png").unlink()

    assert_check_fails(tmp_path, "evidence file is missing")


def test_dashboard_missing_live_source_or_preview_fails(tmp_path):
    write_output(
        tmp_path,
        valid_replay(),
        dashboard_html=valid_dashboard_html().replace("valera.live_camera_probe", "missing-source"),
    )

    assert_check_fails(tmp_path, f"dashboard missing {LIVE_CAMERA_SOURCE}")

    write_output(
        tmp_path,
        valid_replay(),
        dashboard_html=valid_dashboard_html().replace("<img ", "<span "),
    )

    assert_check_fails(tmp_path, "dashboard missing evidence preview imgs")


def test_cli_exits_0_on_valid_tmp_path_output(tmp_path):
    write_valid_output(tmp_path)

    result = run_cli(tmp_path)

    assert result.returncode == 0
    assert "PASS: Physical demo output verification" in result.stdout
    assert "Object found source: valera.live_camera_probe" in result.stdout


def test_cli_exits_non_zero_on_invalid_tmp_path_output(tmp_path):
    write_output(tmp_path, valid_replay()[:-1])

    result = run_cli(tmp_path)

    assert result.returncode == 1
    assert "FAIL: Physical demo output verification" in result.stdout
    assert "expected 13 events, got 12" in result.stdout


def assert_check_fails(project_root, expected_text):
    try:
        check_physical_demo_output(project_root=project_root)
    except PhysicalDemoOutputError as exc:
        assert expected_text in str(exc)
    else:
        raise AssertionError("expected physical demo output check to fail")


def run_cli(project_root):
    return subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "check_physical_demo_output.py"),
            "--project-root",
            str(project_root),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def write_valid_output(project_root):
    write_output(project_root, valid_replay())


def write_output(project_root, replay, dashboard_html=None):
    run_dir = project_root / "data" / "runs" / TASK_ID
    evidence_dir = project_root / "data" / "evidence" / TASK_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "replay.json").write_text(json.dumps(replay, indent=2) + "\n", encoding="utf-8")
    (run_dir / "dashboard.html").write_text(
        dashboard_html if dashboard_html is not None else valid_dashboard_html(),
        encoding="utf-8",
    )
    for name in ("physical-demo-001-007-raw.png", "physical-demo-001-007-annotated.png"):
        (evidence_dir / name).write_bytes(b"fake png")


def valid_replay():
    started_at = datetime(2026, 7, 2, 14, 0, tzinfo=timezone.utc)
    events = []
    for index, event_type in enumerate(EVENT_TYPES, start=1):
        events.append(
            {
                "event_id": f"physical-demo-001-{index:03d}",
                "task_id": TASK_ID,
                "correlation_id": "physical-demo-001-physical-demo",
                "sequence": index,
                "event_type": event_type,
                "occurred_at": (started_at + timedelta(seconds=index - 1)).isoformat(),
                "source": "valera.physical_demo",
                "mode": "real_vision",
                "schema_version": "1.0",
                "payload": {"status": "completed"} if event_type == "task.completed" else {},
                "evidence_refs": [],
            }
        )
    object_found = deepcopy(events[6])
    object_found["source"] = LIVE_CAMERA_SOURCE
    object_found["payload"] = {
        "object_id": "VALERA-CUBE-001",
        "marker_id": 7,
        "detection_score": 1.0,
        "status": "found",
    }
    object_found["evidence_refs"] = [
        evidence_ref("physical-demo-001-007-raw.png"),
        evidence_ref("physical-demo-001-007-annotated.png"),
    ]
    events[6] = object_found
    return events


def evidence_ref(filename):
    return {
        "evidence_id": "physical-demo-001-007",
        "relative_path": f"data/evidence/{TASK_ID}/{filename}",
        "media_type": "image/png",
        "capture_mode": "real_vision",
        "source_adapter": LIVE_CAMERA_SOURCE,
        "linked_event_id": "physical-demo-001-007",
        "checksum": f"sha256:{filename}",
    }


def valid_dashboard_html():
    return """<!doctype html>
<html>
<body>
<div><span>Final status</span>completed</div>
<table>
<tr><td>7</td><td>object.found</td><td>valera.live_camera_probe</td></tr>
<tr><td>13</td><td>task.completed</td></tr>
</table>
<a href="../../evidence/physical-demo-001/physical-demo-001-007-raw.png">Open evidence file</a>
<img src="../../evidence/physical-demo-001/physical-demo-001-007-raw.png" class="evidence-preview">
</body>
</html>
"""
