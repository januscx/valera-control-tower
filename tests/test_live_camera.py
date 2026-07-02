import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dashboard.render import render_dashboard_from_replay
from robot.events import EventType
from robot.models import ExecutionMode


LIVE_CAMERA_SOURCE = "valera.live_camera_probe"


class FakeCapture:
    def __init__(self, opened=True, frame=None, read_ok=True):
        self.opened = opened
        self.frame = frame
        self.read_ok = read_ok
        self.released = False
        self.properties = []

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        self.properties.append((prop, value))
        return True

    def read(self):
        return self.read_ok, self.frame

    def release(self):
        self.released = True


def test_disabled_live_camera_capture_does_not_open_videocapture(tmp_path):
    from robot.live_camera import LiveCameraDisabledError, capture_live_camera_frame

    opened = False

    def video_capture(*args):
        nonlocal opened
        opened = True
        return FakeCapture()

    fake_cv2 = SimpleNamespace(VideoCapture=video_capture, CAP_V4L2=200)

    with pytest.raises(LiveCameraDisabledError, match="requires enabled=True"):
        capture_live_camera_frame(
            camera_index=0,
            output_path=tmp_path / "frame.png",
            enabled=False,
            cv2_module=fake_cv2,
        )

    assert opened is False


def test_enabled_capture_opens_camera_releases_it_and_writes_frame(tmp_path):
    cv2 = pytest.importorskip("cv2")
    from robot.live_camera import capture_live_camera_frame

    frame = cv2.imread(str(_marker_fixture(tmp_path)))
    capture = FakeCapture(opened=True, frame=frame)
    video_capture_calls = []

    def video_capture(*args):
        video_capture_calls.append(args)
        return capture

    fake_cv2 = SimpleNamespace(
        VideoCapture=video_capture,
        CAP_V4L2=200,
        CAP_PROP_FOURCC=6,
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_FPS=5,
        VideoWriter_fourcc=lambda *chars: 1196444237,
        imwrite=cv2.imwrite,
    )

    output_path = tmp_path / "capture" / "frame.png"
    returned_path = capture_live_camera_frame(
        camera_index=0,
        output_path=output_path,
        enabled=True,
        cv2_module=fake_cv2,
    )

    assert returned_path == output_path
    assert output_path.is_file()
    assert capture.released is True
    assert video_capture_calls == [(0, fake_cv2.CAP_V4L2)]
    assert (fake_cv2.CAP_PROP_FOURCC, 1196444237) in capture.properties
    assert (fake_cv2.CAP_PROP_FRAME_WIDTH, 1280) in capture.properties
    assert (fake_cv2.CAP_PROP_FRAME_HEIGHT, 720) in capture.properties
    assert (fake_cv2.CAP_PROP_FPS, 30) in capture.properties


def test_camera_open_failure_raises_clear_error(tmp_path):
    from robot.live_camera import capture_live_camera_frame

    capture = FakeCapture(opened=False)
    fake_cv2 = _minimal_fake_cv2(capture)

    with pytest.raises(RuntimeError, match="could not open live camera index 0"):
        capture_live_camera_frame(
            camera_index=0,
            output_path=tmp_path / "frame.png",
            enabled=True,
            cv2_module=fake_cv2,
        )

    assert capture.released is True


def test_frame_read_failure_raises_clear_error(tmp_path):
    from robot.live_camera import capture_live_camera_frame

    capture = FakeCapture(opened=True, frame=None, read_ok=False)
    fake_cv2 = _minimal_fake_cv2(capture)

    with pytest.raises(RuntimeError, match="could not read one frame"):
        capture_live_camera_frame(
            camera_index=0,
            output_path=tmp_path / "frame.png",
            enabled=True,
            cv2_module=fake_cv2,
        )

    assert capture.released is True


def test_frame_write_failure_raises_clear_error(tmp_path):
    from robot.live_camera import capture_live_camera_frame

    capture = FakeCapture(opened=True, frame=object())
    fake_cv2 = _minimal_fake_cv2(capture, imwrite=lambda *args: False)

    with pytest.raises(OSError, match="failed to write live camera frame"):
        capture_live_camera_frame(
            camera_index=0,
            output_path=tmp_path / "frame.png",
            enabled=True,
            cv2_module=fake_cv2,
        )

    assert capture.released is True


def test_live_camera_marker_probe_passes_live_source_context(tmp_path, monkeypatch):
    import robot.live_camera as live_camera

    captured = {}

    def fake_capture_live_camera_frame(*, output_path, **kwargs):
        captured["capture_output_path"] = output_path
        return output_path

    def fake_run_fixture_detection(
        *,
        task,
        image_path,
        sequence,
        correlation_id,
        evidence_base_path,
        source_adapter,
        image_context,
    ):
        captured.update(
            {
                "task": task,
                "image_path": image_path,
                "sequence": sequence,
                "correlation_id": correlation_id,
                "evidence_base_path": evidence_base_path,
                "source_adapter": source_adapter,
                "image_context": image_context,
            }
        )
        return object()

    monkeypatch.setattr(live_camera, "capture_live_camera_frame", fake_capture_live_camera_frame)
    monkeypatch.setattr(live_camera, "run_fixture_detection", fake_run_fixture_detection)

    event = live_camera.run_live_camera_marker_probe(
        task_id="live-probe-task-004",
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enabled=True,
        output_root=tmp_path,
        sequence=12,
        correlation_id="corr-live-probe-004",
    )

    assert event is not None
    assert captured["capture_output_path"] == tmp_path / "tmp" / "live-camera-probe-frame.png"
    assert captured["image_path"] == captured["capture_output_path"]
    assert captured["sequence"] == 12
    assert captured["correlation_id"] == "corr-live-probe-004"
    assert captured["evidence_base_path"] == tmp_path
    assert captured["source_adapter"] == LIVE_CAMERA_SOURCE
    assert captured["image_context"] == "live camera frame"


def test_live_camera_marker_probe_emits_real_vision_object_found_for_marker_frame(tmp_path, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    pytest.importorskip("cv2.aruco")
    from robot.live_camera import run_live_camera_marker_probe

    frame = cv2.imread(str(_marker_fixture(tmp_path)))
    _patch_video_capture(monkeypatch, cv2, frame=frame)

    event = run_live_camera_marker_probe(
        task_id="live-probe-task-001",
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enabled=True,
        output_root=tmp_path,
    )

    assert event.event_type == EventType.OBJECT_FOUND
    assert event.mode == ExecutionMode.REAL_VISION
    assert event.source == LIVE_CAMERA_SOURCE
    assert event.payload["object_id"] == "VALERA-CUBE-001"
    assert event.payload["marker_id"] == 7
    assert len(event.evidence_refs) == 2
    assert {ref.source_adapter for ref in event.evidence_refs} == {LIVE_CAMERA_SOURCE}
    assert (tmp_path / "tmp" / "live-camera-probe-frame.png").is_file()


def test_live_camera_marker_probe_emits_object_not_found_for_no_marker_frame(tmp_path, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    pytest.importorskip("cv2.aruco")
    from robot.live_camera import run_live_camera_marker_probe
    from robot.vision import generate_no_marker_fixture

    image_path = tmp_path / "no-marker.png"
    generate_no_marker_fixture(image_path)
    frame = cv2.imread(str(image_path))
    _patch_video_capture(monkeypatch, cv2, frame=frame)

    event = run_live_camera_marker_probe(
        task_id="live-probe-task-002",
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enabled=True,
        output_root=tmp_path,
    )

    assert event.event_type == EventType.OBJECT_NOT_FOUND
    assert event.mode == ExecutionMode.REAL_VISION
    assert event.source == LIVE_CAMERA_SOURCE
    assert event.payload == {"object_id": "VALERA-CUBE-001", "status": "not_found"}
    assert event.error.message == "no ArUco marker detected in live camera frame"
    assert len(event.evidence_refs) == 1
    assert event.evidence_refs[0].source_adapter == LIVE_CAMERA_SOURCE


def test_live_camera_marker_probe_replay_dashboard_rendering(tmp_path, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    pytest.importorskip("cv2.aruco")
    from robot.live_camera import run_live_camera_marker_probe

    frame = cv2.imread(str(_marker_fixture(tmp_path)))
    _patch_video_capture(monkeypatch, cv2, frame=frame)

    event = run_live_camera_marker_probe(
        task_id="live-probe-task-003",
        object_id="VALERA-CUBE-001",
        camera_index=0,
        enabled=True,
        output_root=tmp_path,
    )
    replay_path = tmp_path / "data" / "runs" / "live-probe-task-003" / "replay.json"
    dashboard_path = tmp_path / "data" / "runs" / "live-probe-task-003" / "dashboard.html"
    replay_path.parent.mkdir(parents=True, exist_ok=True)
    replay_path.write_text(json.dumps([event.to_dict()], indent=2) + "\n", encoding="utf-8")

    summary = render_dashboard_from_replay(replay_path, dashboard_path)

    assert replay_path.is_file()
    assert dashboard_path.is_file()
    assert summary.task_id == "live-probe-task-003"
    assert summary.event_count == 1
    assert 'href="../../evidence/live-probe-task-003/' in dashboard_path.read_text(
        encoding="utf-8"
    )


def _marker_fixture(tmp_path: Path) -> Path:
    from robot.vision import generate_marker_fixture

    image_path = tmp_path / "marker.png"
    generate_marker_fixture(image_path, marker_id=7)
    return image_path


def _minimal_fake_cv2(capture, imwrite=None):
    return SimpleNamespace(
        VideoCapture=lambda *args: capture,
        CAP_V4L2=200,
        CAP_PROP_FOURCC=6,
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_FPS=5,
        VideoWriter_fourcc=lambda *chars: 1196444237,
        imwrite=imwrite or (lambda *args: True),
    )


def _patch_video_capture(monkeypatch, cv2, *, frame):
    capture = FakeCapture(opened=True, frame=frame)
    monkeypatch.setattr(cv2, "VideoCapture", lambda *args: capture)
    return capture
