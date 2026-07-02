from datetime import datetime, timezone

import pytest

from robot.evidence import EvidenceRef, create_evidence_ref
from robot.events import EventEnvelope, EventType
from robot.models import ExecutionMode, ValidationError


def test_evidence_ref_requires_core_fields():
    with pytest.raises(ValidationError, match="evidence_id"):
        EvidenceRef(
            evidence_id="",
            relative_path="data/evidence/task-001/evidence-001-raw.png",
            media_type="image/png",
            capture_mode="simulation",
            source_adapter="sim-evidence-adapter",
            linked_event_id="event-001",
        )


def test_evidence_relative_path_is_required_and_not_absolute():
    with pytest.raises(ValidationError, match="relative_path"):
        EvidenceRef(
            evidence_id="evidence-001",
            relative_path="",
            media_type="image/png",
            capture_mode="simulation",
            source_adapter="sim-evidence-adapter",
            linked_event_id="event-001",
        )

    with pytest.raises(ValidationError, match="relative_path must be relative"):
        EvidenceRef(
            evidence_id="evidence-001",
            relative_path="/tmp/evidence-001-raw.png",
            media_type="image/png",
            capture_mode="simulation",
            source_adapter="sim-evidence-adapter",
            linked_event_id="event-001",
        )


def test_created_evidence_path_stays_under_task_directory():
    evidence = create_evidence_ref(
        task_id="task-001",
        evidence_id="evidence-001",
        variant="raw",
        media_type="image/png",
        capture_mode="simulation",
        source_adapter="sim-evidence-adapter",
        linked_event_id="event-001",
    )

    assert evidence.relative_path == "data/evidence/task-001/evidence-001-raw.png"

    with pytest.raises(ValidationError, match="data/evidence/task-001"):
        EvidenceRef(
            evidence_id="evidence-001",
            relative_path="data/evidence/task-002/evidence-001-raw.png",
            media_type="image/png",
            capture_mode="simulation",
            source_adapter="sim-evidence-adapter",
            linked_event_id="event-001",
        ).validate_for_task("task-001")

    with pytest.raises(ValidationError, match="must not contain parent traversal"):
        EvidenceRef(
            evidence_id="evidence-001",
            relative_path="data/evidence/task-001/../evidence-001-raw.png",
            media_type="image/png",
            capture_mode="simulation",
            source_adapter="sim-evidence-adapter",
            linked_event_id="event-001",
        )


def test_evidence_ref_serializes_to_dict():
    evidence = create_evidence_ref(
        task_id="task-001",
        evidence_id="evidence-001",
        variant="annotated",
        media_type="image/png",
        capture_mode="simulation",
        source_adapter="sim-evidence-adapter",
        linked_event_id="event-001",
        checksum="sha256:example",
    )

    assert evidence.to_dict() == {
        "evidence_id": "evidence-001",
        "relative_path": "data/evidence/task-001/evidence-001-annotated.png",
        "media_type": "image/png",
        "capture_mode": "simulation",
        "source_adapter": "sim-evidence-adapter",
        "linked_event_id": "event-001",
        "checksum": "sha256:example",
    }


def test_missing_evidence_file_is_reported_clearly(tmp_path):
    evidence = create_evidence_ref(
        task_id="task-001",
        evidence_id="evidence-001",
        variant="raw",
        media_type="image/png",
        capture_mode="simulation",
        source_adapter="sim-evidence-adapter",
        linked_event_id="event-001",
    )

    assert evidence.exists(tmp_path) is False
    with pytest.raises(FileNotFoundError, match="data/evidence/task-001/evidence-001-raw.png"):
        evidence.require_exists(tmp_path)


def test_existing_evidence_file_is_found(tmp_path):
    evidence = create_evidence_ref(
        task_id="task-001",
        evidence_id="evidence-001",
        variant="raw",
        media_type="image/png",
        capture_mode="simulation",
        source_adapter="sim-evidence-adapter",
        linked_event_id="event-001",
    )
    evidence_path = tmp_path / evidence.relative_path
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text("placeholder evidence\n", encoding="utf-8")

    assert evidence.exists(tmp_path) is True
    evidence.require_exists(tmp_path)


def test_event_envelope_serializes_string_and_structured_evidence_refs():
    evidence = create_evidence_ref(
        task_id="task-001",
        evidence_id="evidence-001",
        variant="raw",
        media_type="image/png",
        capture_mode="simulation",
        source_adapter="sim-evidence-adapter",
        linked_event_id="event-001",
    )
    event = EventEnvelope(
        event_id="event-001",
        task_id="task-001",
        correlation_id="corr-001",
        sequence=1,
        event_type=EventType.OBJECT_FOUND,
        occurred_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        source="pytest",
        mode=ExecutionMode.SIMULATION,
        payload={"status": "found"},
        evidence_refs=["legacy-ref", evidence],
    )

    assert event.to_dict()["evidence_refs"] == ["legacy-ref", evidence.to_dict()]
