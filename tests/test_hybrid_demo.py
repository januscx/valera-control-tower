import json
from pathlib import Path

import pytest

pytest.importorskip("cv2")
pytest.importorskip("cv2.aruco")

from dashboard.render import render_dashboard_from_replay
from robot.events import EventType
from robot.hybrid_demo import run_hybrid_fixture_mission, write_hybrid_replay
from robot.models import ExecutionMode
from robot.sim_executor import APPROVED_SUCCESS_EVENT_SEQUENCE
from robot.vision import generate_marker_fixture


def run_sample_hybrid(tmp_path: Path):
    fixture_path = tmp_path / "fixture.png"
    generate_marker_fixture(fixture_path, marker_id=7)
    return run_hybrid_fixture_mission(
        task_id="hybrid-task-001",
        object_id="VALERA-CUBE-001",
        evidence_base_path=tmp_path,
        fixture_path=fixture_path,
    )


def test_hybrid_mission_emits_approved_success_sequence(tmp_path: Path):
    event_log = run_sample_hybrid(tmp_path)

    event_types = [event.event_type for event in event_log.events]
    sequences = [event.sequence for event in event_log.events]

    assert len(event_log.events) == 14
    assert event_types == list(APPROVED_SUCCESS_EVENT_SEQUENCE)
    assert sequences == list(range(1, 15))


def test_hybrid_mission_uses_one_task_and_correlation_id(tmp_path: Path):
    event_log = run_sample_hybrid(tmp_path)

    assert {event.task_id for event in event_log.events} == {"hybrid-task-001"}
    assert len({event.correlation_id for event in event_log.events}) == 1


def test_hybrid_object_found_uses_real_vision_payload_and_evidence(tmp_path: Path):
    event_log = run_sample_hybrid(tmp_path)

    object_found = next(
        event for event in event_log.events if event.event_type == EventType.OBJECT_FOUND
    )

    assert object_found.mode == ExecutionMode.REAL_VISION
    assert object_found.payload["marker_id"] == 7
    assert object_found.payload["detection_score"] == 1.0
    assert len(object_found.payload["corners"]) == 4
    assert object_found.payload["bounding_box"]["width"] > 0
    assert len(object_found.evidence_refs) == 2
    assert any(ref.relative_path.endswith("-raw.png") for ref in object_found.evidence_refs)
    assert any(ref.relative_path.endswith("-annotated.png") for ref in object_found.evidence_refs)
    for evidence_ref in object_found.evidence_refs:
        assert evidence_ref.relative_path.startswith("data/evidence/hybrid-task-001/")
        assert evidence_ref.exists(tmp_path)


def test_hybrid_keeps_route_grasp_delivery_simulated_and_terminal_completed(tmp_path: Path):
    event_log = run_sample_hybrid(tmp_path)

    simulated_types = {
        EventType.ROUTE_STARTED,
        EventType.ROUTE_ARRIVED,
        EventType.GRASP_STARTED,
        EventType.OBJECT_GRASPED,
        EventType.DELIVERY_STARTED,
        EventType.OBJECT_RELEASED,
        EventType.DELIVERY_COMPLETED,
    }
    for event in event_log.events:
        if event.event_type in simulated_types:
            assert event.mode == ExecutionMode.SIMULATION

    assert event_log.events[-1].event_type == EventType.TASK_COMPLETED
    event_log.validate()


def test_hybrid_replay_serializes_and_dashboard_renders(tmp_path: Path):
    event_log = run_sample_hybrid(tmp_path)
    replay_path = tmp_path / "runs" / "hybrid" / "replay.json"
    dashboard_path = tmp_path / "runs" / "hybrid" / "dashboard.html"

    write_hybrid_replay(event_log, replay_path)
    summary = render_dashboard_from_replay(replay_path, dashboard_path)

    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    object_found = next(event for event in replay if event["event_type"] == "object.found")
    assert replay_path.is_file()
    assert dashboard_path.is_file()
    assert summary.task_id == "hybrid-task-001"
    assert summary.final_status == "completed"
    assert isinstance(object_found["evidence_refs"][0], dict)
    assert object_found["evidence_refs"][0]["relative_path"].startswith(
        "data/evidence/hybrid-task-001/"
    )


def test_hybrid_replay_dashboard_includes_evidence_links_and_previews(tmp_path: Path):
    event_log = run_sample_hybrid(tmp_path)
    replay_path = tmp_path / "data" / "runs" / "hybrid-task-001" / "replay.json"
    dashboard_path = tmp_path / "data" / "runs" / "hybrid-task-001" / "dashboard.html"

    write_hybrid_replay(event_log, replay_path)
    render_dashboard_from_replay(replay_path, dashboard_path)

    html = dashboard_path.read_text(encoding="utf-8")
    assert 'href="../../evidence/hybrid-task-001/' in html
    assert 'src="../../evidence/hybrid-task-001/' in html
    assert 'class="evidence-preview"' in html
