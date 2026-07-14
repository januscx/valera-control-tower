from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.probe_cameras import (
    DEFAULT_PROFILES,
    CameraProfile,
    build_parser,
    probe_camera,
    select_profiles,
    write_report,
)


@pytest.fixture
def local_profile(tmp_path):
    """Return a CameraProfile whose path lives under tmp_path for safe symlink creation."""
    by_id_path = tmp_path / "dev" / "v4l" / "by-id" / "usb-test_camera-video-index0"
    return CameraProfile(
        name="test_camera",
        path=str(by_id_path),
        width=1920,
        height=1080,
        fps=30,
        fourcc="MJPG",
    )


def test_select_profiles_defaults_when_no_args():
    profiles = select_profiles(None)
    assert [p.name for p in profiles] == ["innomaker", "astra_pro"]


def test_select_profiles_single_name():
    profiles = select_profiles(["innomaker"])
    assert [p.name for p in profiles] == ["innomaker"]


def test_select_profiles_comma_separated():
    profiles = select_profiles(["astra_pro,innomaker"])
    assert [p.name for p in profiles] == ["astra_pro", "innomaker"]


def test_select_profiles_repeatable_args():
    profiles = select_profiles(["innomaker", "astra_pro"])
    assert [p.name for p in profiles] == ["innomaker", "astra_pro"]


def test_select_profiles_deduplicates():
    profiles = select_profiles(["innomaker", "innomaker"])
    assert [p.name for p in profiles] == ["innomaker"]


def test_select_profiles_rejects_unknown_camera():
    with pytest.raises(ValueError, match="unknown camera 'webcam'"):
        select_profiles(["webcam"])


def test_build_parser_parses_output_dir_and_camera():
    parser = build_parser()
    args = parser.parse_args(["--output-dir", "out", "--camera", "innomaker"])
    assert args.output_dir == "out"
    assert args.cameras == ["innomaker"]


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

    def get(self, prop):
        if prop == 3:  # CAP_PROP_FRAME_WIDTH
            return 1920
        if prop == 4:  # CAP_PROP_FRAME_HEIGHT
            return 1080
        if prop == 5:  # CAP_PROP_FPS
            return 30
        return 0

    def read(self):
        return self.read_ok, self.frame

    def release(self):
        self.released = True


def _make_fake_cv2(capture, imwrite_returns=True):
    return SimpleNamespace(
        VideoCapture=lambda *args: capture,
        CAP_V4L2=200,
        CAP_PROP_FOURCC=6,
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_FPS=5,
        VideoWriter_fourcc=lambda *chars: 1196444237,
        imwrite=lambda *args: imwrite_returns,
    )


def test_probe_camera_writes_frame_and_reports_ok(tmp_path, local_profile):
    output_path = tmp_path / "test_camera.jpg"
    frame = object()
    capture = FakeCapture(opened=True, frame=frame)
    fake_cv2 = _make_fake_cv2(capture)

    # Create the by-id symlink and its target so the existence check passes.
    device_path = tmp_path / "video2"
    device_path.touch()
    by_id_path = Path(local_profile.path)
    by_id_path.parent.mkdir(parents=True, exist_ok=True)
    by_id_path.symlink_to(device_path)

    result = probe_camera(local_profile, output_path, cv2_module=fake_cv2)

    assert result["ok"] is True
    assert result["frame_path"] == str(output_path)
    assert result["resolved_path"] == str(device_path)
    assert result["actual_width"] == 1920
    assert result["actual_height"] == 1080
    assert result["actual_fps"] == 30
    assert capture.released is True
    assert (fake_cv2.CAP_PROP_FOURCC, 1196444237) in capture.properties
    assert (fake_cv2.CAP_PROP_FRAME_WIDTH, local_profile.width) in capture.properties
    assert (fake_cv2.CAP_PROP_FRAME_HEIGHT, local_profile.height) in capture.properties
    assert (fake_cv2.CAP_PROP_FPS, local_profile.fps) in capture.properties


def test_probe_camera_reports_missing_path(tmp_path, local_profile):
    output_path = tmp_path / "test_camera.jpg"
    fake_cv2 = _make_fake_cv2(FakeCapture())

    result = probe_camera(local_profile, output_path, cv2_module=fake_cv2)

    assert result["ok"] is False
    assert "device path does not exist" in result["error"]


def test_probe_camera_reports_open_failure(tmp_path, local_profile):
    output_path = tmp_path / "test_camera.jpg"
    device_path = tmp_path / "video2"
    device_path.touch()
    by_id_path = Path(local_profile.path)
    by_id_path.parent.mkdir(parents=True, exist_ok=True)
    by_id_path.symlink_to(device_path)

    capture = FakeCapture(opened=False)
    fake_cv2 = _make_fake_cv2(capture)

    result = probe_camera(local_profile, output_path, cv2_module=fake_cv2)

    assert result["ok"] is False
    assert "could not open" in result["error"]
    assert capture.released is True


def test_probe_camera_reports_read_failure(tmp_path, local_profile):
    output_path = tmp_path / "test_camera.jpg"
    device_path = tmp_path / "video2"
    device_path.touch()
    by_id_path = Path(local_profile.path)
    by_id_path.parent.mkdir(parents=True, exist_ok=True)
    by_id_path.symlink_to(device_path)

    capture = FakeCapture(opened=True, frame=None, read_ok=False)
    fake_cv2 = _make_fake_cv2(capture)

    result = probe_camera(local_profile, output_path, cv2_module=fake_cv2)

    assert result["ok"] is False
    assert "could not read one frame" in result["error"]
    assert capture.released is True


def test_probe_camera_reports_write_failure(tmp_path, local_profile):
    output_path = tmp_path / "test_camera.jpg"
    device_path = tmp_path / "video2"
    device_path.touch()
    by_id_path = Path(local_profile.path)
    by_id_path.parent.mkdir(parents=True, exist_ok=True)
    by_id_path.symlink_to(device_path)

    capture = FakeCapture(opened=True, frame=object())
    fake_cv2 = _make_fake_cv2(capture, imwrite_returns=False)

    result = probe_camera(local_profile, output_path, cv2_module=fake_cv2)

    assert result["ok"] is False
    assert "failed to write frame" in result["error"]
    assert capture.released is True


def test_probe_camera_reports_videocapture_constructor_failure(tmp_path, local_profile):
    output_path = tmp_path / "test_camera.jpg"
    device_path = tmp_path / "video2"
    device_path.touch()
    by_id_path = Path(local_profile.path)
    by_id_path.parent.mkdir(parents=True, exist_ok=True)
    by_id_path.symlink_to(device_path)

    class RaisingVideoCapture:
        def __init__(self, *args):
            raise RuntimeError("v4l2 backend unavailable")

    fake_cv2 = SimpleNamespace(
        VideoCapture=RaisingVideoCapture,
        CAP_V4L2=200,
    )

    result = probe_camera(local_profile, output_path, cv2_module=fake_cv2)

    assert result["ok"] is False
    assert "v4l2 backend unavailable" in result["error"]


def test_write_report_creates_markdown_summary(tmp_path):
    results = [
        {
            "name": "innomaker",
            "configured_path": "/dev/by-id/innomaker",
            "resolved_path": "/dev/video2",
            "requested_width": 1920,
            "requested_height": 1080,
            "requested_fps": 30,
            "requested_fourcc": "MJPG",
            "ok": True,
            "frame_path": str(tmp_path / "innomaker.jpg"),
            "error": None,
            "actual_width": 1920,
            "actual_height": 1080,
            "actual_fps": 30,
        },
        {
            "name": "astra_pro",
            "configured_path": "/dev/by-id/astra",
            "resolved_path": "/dev/video0",
            "requested_width": 1280,
            "requested_height": 720,
            "requested_fps": 30,
            "requested_fourcc": "MJPG",
            "ok": False,
            "frame_path": None,
            "error": "could not open",
        },
    ]
    report_path = tmp_path / "report.md"
    write_report(results, report_path)

    text = report_path.read_text(encoding="utf-8")
    assert "# Dual-camera probe report" in text
    assert "innomaker" in text
    assert "astra_pro" in text
    assert "could not open" in text
    assert "1920x1080" in text
