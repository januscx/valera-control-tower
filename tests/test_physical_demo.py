import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dashboard.render import render_dashboard_from_replay
from robot.events import EventEnvelope, EventError, EventType
from robot.evidence import create_evidence_ref
from robot.live_camera import LIVE_CAMERA_SOURCE, LiveCameraDisabledError
from robot.models import ExecutionMode, FailureCode
from robot.physical_demo import (
    ListConfirmationProvider,
    PHYSICAL_DEMO_SUCCESS_EVENT_SEQUENCE,
    run_physical_demo,
    write_physical_demo_replay,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_physical_demo_fails_closed_without_live_camera_and_does_not_probe(tmp_path):
    opened = False

    def probe_runner(**kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("probe should not run")

    try:
        run_physical_demo(
            task_id="physical-test-closed",
            object_id="VALERA-CUBE-001",
            camera_index=0,
            enable_live_camera=False,
            output_root=tmp_path,
            confirmation_provider=ListConfirmationProvider([True]),
            live_probe_runner=probe_runner,
        )
    except LiveCameraDisabledError as exc:
        assert "--enable-live-camera" in str(exc)
    else:
        raise AssertionError("expected LiveCameraDisabledError")

    assert opened is False


def test_physical_demo_success_emits_completed_sequence_and_validates(tmp_path):
    event_log = run_physical_demo(
        task_id="physical-test-success",
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enable_live_camera=True,
        output_root=tmp_path,
        confirmation_provider=ListConfirmationProvider([True, True, True, True, True]),
        run_started_at=datetime(2026, 7, 2, 14, 0, tzinfo=timezone.utc),
        live_probe_runner=_found_probe,
    )

    assert [event.event_type for event in event_log.events] == list(
        PHYSICAL_DEMO_SUCCESS_EVENT_SEQUENCE
    )
    assert [event.sequence for event in event_log.events] == list(range(1, 14))
    assert [event.occurred_at for event in event_log.events] == [
        datetime(2026, 7, 2, 14, 0, index, tzinfo=timezone.utc) for index in range(13)
    ]
    assert event_log.events[-1].event_type == EventType.TASK_COMPLETED
    event_log.validate()


def test_physical_demo_occurred_at_is_monotonic_by_sequence(tmp_path):
    event_log = run_physical_demo(
        task_id="physical-test-monotonic-time",
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enable_live_camera=True,
        output_root=tmp_path,
        confirmation_provider=ListConfirmationProvider([True, True, True, True, True]),
        run_started_at=datetime(2026, 7, 2, 16, 30, tzinfo=timezone.utc),
        live_probe_runner=_found_probe,
    )

    occurred_at_values = [event.occurred_at for event in event_log.events]
    assert occurred_at_values == sorted(occurred_at_values)
    assert event_log.events[6].event_type == EventType.OBJECT_FOUND
    assert event_log.events[6].occurred_at == datetime(
        2026, 7, 2, 16, 30, 6, tzinfo=timezone.utc
    )


def test_physical_demo_object_not_found_fails_before_confirmations(tmp_path):
    confirmations = []

    def confirm(step_name, prompt):
        confirmations.append(step_name)
        return True

    event_log = run_physical_demo(
        task_id="physical-test-not-found",
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enable_live_camera=True,
        output_root=tmp_path,
        confirmation_provider=confirm,
        live_probe_runner=_not_found_probe,
    )

    assert [event.event_type for event in event_log.events] == [
        EventType.TASK_CREATED,
        EventType.TASK_ACCEPTED,
        EventType.PLAN_CREATED,
        EventType.ROUTE_STARTED,
        EventType.ROUTE_ARRIVED,
        EventType.OBJECT_SEARCH_STARTED,
        EventType.OBJECT_NOT_FOUND,
        EventType.TASK_FAILED,
    ]
    assert confirmations == []
    assert event_log.events[-1].payload["reason"] == "live camera did not find the target object"
    event_log.validate()


def test_physical_demo_operator_cancellation_emits_task_failed_and_stops(tmp_path):
    event_log = run_physical_demo(
        task_id="physical-test-cancel",
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enable_live_camera=True,
        output_root=tmp_path,
        confirmation_provider=ListConfirmationProvider([True, False, True, True, True]),
        live_probe_runner=_found_probe,
    )

    assert [event.event_type for event in event_log.events] == [
        EventType.TASK_CREATED,
        EventType.TASK_ACCEPTED,
        EventType.PLAN_CREATED,
        EventType.ROUTE_STARTED,
        EventType.ROUTE_ARRIVED,
        EventType.OBJECT_SEARCH_STARTED,
        EventType.OBJECT_FOUND,
        EventType.GRASP_STARTED,
        EventType.TASK_FAILED,
    ]
    assert event_log.events[-1].error.code == FailureCode.MANUAL_CANCELLED
    assert "confirm_object_grasped" in event_log.events[-1].payload["reason"]
    event_log.validate()


def test_physical_demo_replay_dashboard_success_includes_live_evidence(tmp_path):
    task_id = "physical-test-dashboard-success"
    event_log = run_physical_demo(
        task_id=task_id,
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enable_live_camera=True,
        output_root=tmp_path,
        confirmation_provider=ListConfirmationProvider([True, True, True, True, True]),
        live_probe_runner=_found_probe,
    )
    replay_path = tmp_path / "data" / "runs" / task_id / "replay.json"
    dashboard_path = tmp_path / "data" / "runs" / task_id / "dashboard.html"

    write_physical_demo_replay(event_log, replay_path)
    summary = render_dashboard_from_replay(replay_path, dashboard_path)
    html = dashboard_path.read_text(encoding="utf-8")
    replay = json.loads(replay_path.read_text(encoding="utf-8"))

    assert replay_path.is_file()
    assert dashboard_path.is_file()
    assert summary.final_status == "completed"
    assert replay[-1]["event_type"] == "task.completed"
    assert "valera.live_camera_probe" in html
    assert 'href="../../evidence/physical-test-dashboard-success/' in html
    assert 'src="../../evidence/physical-test-dashboard-success/' in html
    assert 'class="evidence-preview"' in html


def test_physical_demo_dashboard_failure_status_is_failed(tmp_path):
    task_id = "physical-test-dashboard-failed"
    event_log = run_physical_demo(
        task_id=task_id,
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enable_live_camera=True,
        output_root=tmp_path,
        confirmation_provider=ListConfirmationProvider([True, True, True, True, True]),
        live_probe_runner=_not_found_probe,
    )
    replay_path = tmp_path / "data" / "runs" / task_id / "replay.json"
    dashboard_path = tmp_path / "data" / "runs" / task_id / "dashboard.html"

    write_physical_demo_replay(event_log, replay_path)
    summary = render_dashboard_from_replay(replay_path, dashboard_path)

    assert summary.final_status == "failed"
    assert "task.failed" in dashboard_path.read_text(encoding="utf-8")


def test_physical_demo_cli_without_live_camera_fails_closed():
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "run_physical_demo.py")],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "does not move the robot" in result.stdout
    assert "fail-closed" in result.stdout
    assert "--enable-live-camera" in result.stdout


def _found_probe(**kwargs):
    event = _probe_event(EventType.OBJECT_FOUND, kwargs)
    raw_ref = create_evidence_ref(
        task_id=kwargs["task_id"],
        evidence_id=event.event_id,
        variant="raw",
        media_type="image/png",
        capture_mode="real_vision",
        source_adapter=LIVE_CAMERA_SOURCE,
        linked_event_id=event.event_id,
        checksum="sha256:test-raw",
    )
    annotated_ref = create_evidence_ref(
        task_id=kwargs["task_id"],
        evidence_id=event.event_id,
        variant="annotated",
        media_type="image/png",
        capture_mode="real_vision",
        source_adapter=LIVE_CAMERA_SOURCE,
        linked_event_id=event.event_id,
        checksum="sha256:test-annotated",
    )
    event.evidence_refs.extend([raw_ref, annotated_ref])
    for ref in event.evidence_refs:
        path = tmp_root(kwargs) / ref.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake png")
    return event


def _not_found_probe(**kwargs):
    return _probe_event(
        EventType.OBJECT_NOT_FOUND,
        kwargs,
        payload={"object_id": kwargs["object_id"], "status": "not_found"},
        error=EventError(
            code=FailureCode.OBJECT_NOT_FOUND,
            message="no ArUco marker detected in live camera frame",
        ),
    )


def _probe_event(event_type, kwargs, payload=None, error=None):
    return EventEnvelope(
        event_id=f"{kwargs['correlation_id']}-{kwargs['sequence']:03d}",
        task_id=kwargs["task_id"],
        correlation_id=kwargs["correlation_id"],
        sequence=kwargs["sequence"],
        event_type=event_type,
        occurred_at=kwargs["occurred_at"],
        source=LIVE_CAMERA_SOURCE,
        mode=ExecutionMode.REAL_VISION,
        payload=payload
        or {
            "object_id": kwargs["object_id"],
            "status": "found",
            "marker_id": 7,
            "detection_score": 1.0,
        },
        error=error,
    )


def tmp_root(kwargs):
    return Path(kwargs["output_root"])
