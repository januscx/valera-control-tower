from __future__ import annotations

from pathlib import Path
from typing import Any

from robot.events import EventEnvelope
from robot.models import ExecutionMode, Task, Zone
from robot.vision import run_fixture_detection


LIVE_CAMERA_SOURCE = "valera.live_camera_probe"


class LiveCameraDisabledError(RuntimeError):
    """Raised when live camera access is requested without explicit opt-in."""


def capture_live_camera_frame(
    *,
    camera_index: int,
    output_path: Path,
    enabled: bool,
    cv2_module: Any | None = None,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    fourcc: str = "MJPG",
) -> Path:
    if not enabled:
        raise LiveCameraDisabledError(
            "live camera capture requires enabled=True; pass --enable-live-camera to opt in"
        )

    cv2 = cv2_module or _require_cv2()
    capture = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    try:
        if not capture.isOpened():
            raise RuntimeError(f"could not open live camera index {camera_index}")

        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_FPS, fps)

        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"could not read one frame from live camera index {camera_index}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), frame):
            raise OSError(f"failed to write live camera frame: {output_path}")
        return output_path
    finally:
        capture.release()


def run_live_camera_marker_probe(
    *,
    task_id: str,
    object_id: str,
    camera_index: int,
    enabled: bool,
    output_root: Path,
    sequence: int = 1,
    correlation_id: str | None = None,
) -> EventEnvelope:
    if not enabled:
        raise LiveCameraDisabledError(
            "live camera marker probe requires --enable-live-camera before camera access"
        )

    output_root = Path(output_root)
    frame_path = output_root / "tmp" / "live-camera-probe-frame.png"
    capture_live_camera_frame(
        camera_index=camera_index,
        output_path=frame_path,
        enabled=enabled,
    )

    task = Task(
        task_id=task_id,
        object_id=object_id,
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.REAL_VISION,
        description="Live camera marker probe; perception only, no robot movement",
    )
    return run_fixture_detection(
        task=task,
        image_path=frame_path,
        sequence=sequence,
        correlation_id=correlation_id or task_id,
        evidence_base_path=output_root,
        source_adapter=LIVE_CAMERA_SOURCE,
        image_context="live camera frame",
    )


def _require_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is required for live camera capture. Install requirements-dev.txt."
        ) from exc

    return cv2
