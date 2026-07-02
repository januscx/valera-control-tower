from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np

from robot.evidence import EvidenceRef, create_evidence_ref
from robot.events import EventEnvelope, EventError, EventType
from robot.models import ExecutionMode, FailureCode, Task, ValidationError


VISION_SOURCE = "valera.real_vision_fixture"
ARUCO_DICTIONARY = "DICT_4X4_50"


def generate_marker_fixture(path: Path, marker_id: int = 7) -> None:
    cv2 = _require_cv2_with_aruco()
    path.parent.mkdir(parents=True, exist_ok=True)

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = _generate_marker_image(cv2, dictionary, marker_id, side_pixels=180)
    image = np.full((320, 320), 255, dtype=np.uint8)
    image[70:250, 70:250] = marker

    if not cv2.imwrite(str(path), image):
        raise OSError(f"failed to write marker fixture: {path}")


def generate_no_marker_fixture(path: Path) -> None:
    cv2 = _require_cv2_with_aruco()
    path.parent.mkdir(parents=True, exist_ok=True)

    image = np.full((320, 320, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (72, 72), (248, 248), (180, 180, 180), 2)
    cv2.line(image, (96, 160), (224, 160), (180, 180, 180), 2)

    if not cv2.imwrite(str(path), image):
        raise OSError(f"failed to write no-marker fixture: {path}")


def run_fixture_detection(
    task: Task,
    image_path: Path,
    sequence: int,
    correlation_id: str,
    evidence_base_path: Path = Path("."),
) -> EventEnvelope:
    _validate_task_mode(task)
    cv2 = _require_cv2_with_aruco()

    if not image_path.is_file():
        raise FileNotFoundError(f"vision fixture image is missing: {image_path}")

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"vision fixture image is unreadable: {image_path}")

    event_id = f"{correlation_id}-{sequence:03d}-vision"
    evidence_id = f"{event_id}-evidence"
    evidence_base_path = Path(evidence_base_path)

    raw_ref = create_evidence_ref(
        task_id=task.task_id,
        evidence_id=evidence_id,
        variant="raw",
        media_type="image/png",
        capture_mode=ExecutionMode.REAL_VISION.value,
        source_adapter=VISION_SOURCE,
        linked_event_id=event_id,
    )
    _write_image(cv2, raw_ref.local_path(evidence_base_path), image)
    raw_ref.checksum = _sha256_file(raw_ref.local_path(evidence_base_path))

    detections = _detect_markers(cv2, image)
    if not detections:
        return _not_found_event(
            task=task,
            event_id=event_id,
            sequence=sequence,
            correlation_id=correlation_id,
            raw_ref=raw_ref,
        )

    detection = detections[0]
    annotated = image.copy()
    cv2.aruco.drawDetectedMarkers(
        annotated,
        [np.array(detection["corners"], dtype=np.float32).reshape((1, 4, 2))],
        np.array([[detection["marker_id"]]], dtype=np.int32),
    )
    annotated_ref = create_evidence_ref(
        task_id=task.task_id,
        evidence_id=evidence_id,
        variant="annotated",
        media_type="image/png",
        capture_mode=ExecutionMode.REAL_VISION.value,
        source_adapter=VISION_SOURCE,
        linked_event_id=event_id,
    )
    _write_image(cv2, annotated_ref.local_path(evidence_base_path), annotated)
    annotated_ref.checksum = _sha256_file(annotated_ref.local_path(evidence_base_path))

    return EventEnvelope(
        event_id=event_id,
        task_id=task.task_id,
        correlation_id=correlation_id,
        sequence=sequence,
        event_type=EventType.OBJECT_FOUND,
        occurred_at=datetime.now(timezone.utc),
        source=VISION_SOURCE,
        mode=ExecutionMode.REAL_VISION,
        payload={
            "object_id": task.object_id,
            "marker_id": detection["marker_id"],
            "detection_score": 1.0,
            "pickup_zone": task.pickup_zone.value,
            "delivery_zone": task.delivery_zone.value,
            "current_target_zone": task.pickup_zone.value,
            "corners": detection["corners"],
            "bounding_box": detection["bounding_box"],
            "status": "found",
        },
        evidence_refs=[raw_ref, annotated_ref],
    )


def _validate_task_mode(task: Task) -> None:
    if task.mode == ExecutionMode.HARDWARE:
        raise ValidationError(
            "vision fixture adapter does not accept hardware mode",
            FailureCode.HARDWARE_MODE_NOT_ENABLED,
        )
    if task.mode != ExecutionMode.REAL_VISION:
        raise ValidationError(
            "vision fixture adapter only accepts real_vision mode tasks",
            FailureCode.INVALID_TASK,
        )


def _not_found_event(
    *,
    task: Task,
    event_id: str,
    sequence: int,
    correlation_id: str,
    raw_ref: EvidenceRef,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        task_id=task.task_id,
        correlation_id=correlation_id,
        sequence=sequence,
        event_type=EventType.OBJECT_NOT_FOUND,
        occurred_at=datetime.now(timezone.utc),
        source=VISION_SOURCE,
        mode=ExecutionMode.REAL_VISION,
        payload={"object_id": task.object_id, "status": "not_found"},
        evidence_refs=[raw_ref],
        error=EventError(
            code=FailureCode.OBJECT_NOT_FOUND,
            message="no ArUco marker detected in fixture image",
        ),
    )


def _detect_markers(cv2: Any, image: np.ndarray) -> list[dict[str, Any]]:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    if hasattr(cv2.aruco, "ArucoDetector"):
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(dictionary, parameters)
        corners, ids, _ = detector.detectMarkers(image)
    else:
        parameters = cv2.aruco.DetectorParameters_create()
        corners, ids, _ = cv2.aruco.detectMarkers(image, dictionary, parameters=parameters)

    if ids is None:
        return []

    detections: list[dict[str, Any]] = []
    for marker_id, marker_corners in zip(ids.flatten(), corners):
        points = marker_corners.reshape((4, 2))
        x_values = points[:, 0]
        y_values = points[:, 1]
        detections.append(
            {
                "marker_id": int(marker_id),
                "corners": [
                    [int(round(float(x))), int(round(float(y)))] for x, y in points
                ],
                "bounding_box": {
                    "x": int(round(float(x_values.min()))),
                    "y": int(round(float(y_values.min()))),
                    "width": int(round(float(x_values.max() - x_values.min()))),
                    "height": int(round(float(y_values.max() - y_values.min()))),
                },
            }
        )

    return detections


def _generate_marker_image(cv2: Any, dictionary: Any, marker_id: int, side_pixels: int) -> np.ndarray:
    if hasattr(cv2.aruco, "generateImageMarker"):
        return cv2.aruco.generateImageMarker(dictionary, marker_id, side_pixels)

    marker = np.zeros((side_pixels, side_pixels), dtype=np.uint8)
    cv2.aruco.drawMarker(dictionary, marker_id, side_pixels, marker, 1)
    return marker


def _write_image(cv2: Any, path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"failed to write evidence image: {path}")


def _sha256_file(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _require_cv2_with_aruco() -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is required for fixture vision. Install requirements-dev.txt."
        ) from exc

    if not hasattr(cv2, "aruco"):
        raise RuntimeError(
            "OpenCV ArUco support is required. Install opencv-contrib-python from requirements-dev.txt."
        )

    return cv2
