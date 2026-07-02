from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
pytest.importorskip("cv2.aruco")

from robot.events import EventType
from robot.models import ExecutionMode, FailureCode, Task, ValidationError, Zone
from robot.vision import (
    VISION_SOURCE,
    generate_marker_fixture,
    generate_no_marker_fixture,
    run_fixture_detection,
)


def make_task(mode=ExecutionMode.REAL_VISION) -> Task:
    return Task(
        task_id="vision-task-001",
        object_id="VALERA-CUBE-001",
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=mode,
        description="Fixture-based vision test",
    )


def test_marker_fixture_produces_object_found(tmp_path):
    image_path = tmp_path / "marker.png"
    generate_marker_fixture(image_path, marker_id=7)

    event = run_fixture_detection(
        make_task(),
        image_path,
        sequence=3,
        correlation_id="corr-vision-001",
        evidence_base_path=tmp_path,
    )

    assert event.event_type == EventType.OBJECT_FOUND
    assert event.mode == ExecutionMode.REAL_VISION
    assert event.source == VISION_SOURCE
    assert {ref.source_adapter for ref in event.evidence_refs} == {VISION_SOURCE}
    assert event.payload["object_id"] == "VALERA-CUBE-001"
    assert event.payload["marker_id"] == 7
    assert event.payload["detection_score"] == 1.0
    assert event.payload["pickup_zone"] == Zone.PICKUP_ZONE.value
    assert event.payload["delivery_zone"] == Zone.DELIVERY_ZONE.value
    assert event.payload["current_target_zone"] == Zone.PICKUP_ZONE.value
    assert event.payload["status"] == "found"
    assert len(event.payload["corners"]) == 4
    assert len(event.evidence_refs) == 2


def test_no_marker_fixture_produces_object_not_found(tmp_path):
    image_path = tmp_path / "blank.png"
    generate_no_marker_fixture(image_path)

    event = run_fixture_detection(
        make_task(),
        image_path,
        sequence=4,
        correlation_id="corr-vision-002",
        evidence_base_path=tmp_path,
    )

    assert event.event_type == EventType.OBJECT_NOT_FOUND
    assert event.mode == ExecutionMode.REAL_VISION
    assert event.source == VISION_SOURCE
    assert event.error.code == FailureCode.OBJECT_NOT_FOUND
    assert event.error.message == "no ArUco marker detected in fixture image"
    assert event.payload == {"object_id": "VALERA-CUBE-001", "status": "not_found"}
    assert len(event.evidence_refs) == 1
    assert event.evidence_refs[0].source_adapter == VISION_SOURCE


def test_structured_evidence_refs_serialize_through_event_envelope(tmp_path):
    image_path = tmp_path / "marker.png"
    generate_marker_fixture(image_path, marker_id=11)

    event = run_fixture_detection(
        make_task(),
        image_path,
        sequence=5,
        correlation_id="corr-vision-003",
        evidence_base_path=tmp_path,
    )

    serialized_refs = event.to_dict()["evidence_refs"]
    assert all(isinstance(ref, dict) for ref in serialized_refs)
    assert {ref["capture_mode"] for ref in serialized_refs} == {"real_vision"}
    assert {ref["source_adapter"] for ref in serialized_refs} == {VISION_SOURCE}


def test_evidence_paths_stay_under_task_directory_and_annotated_file_is_created(tmp_path):
    task = make_task()
    image_path = tmp_path / "marker.png"
    generate_marker_fixture(image_path, marker_id=12)

    event = run_fixture_detection(
        task,
        image_path,
        sequence=6,
        correlation_id="corr-vision-004",
        evidence_base_path=tmp_path,
    )

    for evidence_ref in event.evidence_refs:
        evidence_ref.validate_for_task(task.task_id)
        assert evidence_ref.relative_path.startswith(f"data/evidence/{task.task_id}/")
        assert Path(evidence_ref.relative_path).suffix == ".png"
        assert evidence_ref.exists(tmp_path)

    annotated_refs = [
        ref for ref in event.evidence_refs if ref.relative_path.endswith("-annotated.png")
    ]
    assert len(annotated_refs) == 1
    assert annotated_refs[0].exists(tmp_path)


def test_missing_image_path_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="vision fixture image is missing"):
        run_fixture_detection(
            make_task(),
            tmp_path / "missing.png",
            sequence=7,
            correlation_id="corr-vision-005",
            evidence_base_path=tmp_path,
        )


def test_vision_adapter_rejects_simulation_mode(tmp_path):
    image_path = tmp_path / "marker.png"
    generate_marker_fixture(image_path, marker_id=7)

    with pytest.raises(ValidationError) as exc:
        run_fixture_detection(
            make_task(ExecutionMode.SIMULATION),
            image_path,
            sequence=8,
            correlation_id="corr-vision-006",
            evidence_base_path=tmp_path,
        )

    assert exc.value.code == FailureCode.INVALID_TASK


def test_hardware_mode_remains_fail_closed_and_is_not_accepted_by_vision_adapter(tmp_path):
    with pytest.raises(ValidationError) as task_exc:
        make_task(ExecutionMode.HARDWARE)
    assert task_exc.value.code == FailureCode.HARDWARE_MODE_NOT_ENABLED

    image_path = tmp_path / "marker.png"
    generate_marker_fixture(image_path, marker_id=7)
    task = object.__new__(Task)
    task.task_id = "hardware-vision-task-001"
    task.object_id = "VALERA-CUBE-001"
    task.pickup_zone = Zone.PICKUP_ZONE
    task.delivery_zone = Zone.DELIVERY_ZONE
    task.mode = ExecutionMode.HARDWARE
    task.description = ""

    with pytest.raises(ValidationError) as vision_exc:
        run_fixture_detection(
            task,
            image_path,
            sequence=9,
            correlation_id="corr-vision-007",
            evidence_base_path=tmp_path,
        )

    assert vision_exc.value.code == FailureCode.HARDWARE_MODE_NOT_ENABLED
