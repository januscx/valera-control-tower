import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.collect_hardware_inventory import (
    CommandResult,
    collect_inventory,
    render_markdown,
    write_reports,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "collect_hardware_inventory.py"


def test_inventory_report_files_are_created(tmp_path):
    dev_root = _fake_dev_root(tmp_path)
    output_dir = tmp_path / "reports"

    report = collect_inventory(
        dev_root=dev_root,
        output_dir=output_dir,
        command_resolver=_resolver({"lsusb": "/usr/bin/lsusb"}),
        command_runner=_runner({("lsusb",): "Bus 001 Device 002: ID 2bc5:0403 Orbbec"}),
        now=lambda: datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc),
    )
    json_path, markdown_path = write_reports(report, output_dir)

    assert json_path.is_file()
    assert markdown_path.is_file()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["timestamp"] == "2026-07-02T12:00:00+00:00"
    assert saved["output_paths"]["json"].endswith("latest.json")


def test_missing_optional_commands_are_reported_without_failure(tmp_path):
    report = collect_inventory(
        dev_root=_fake_dev_root(tmp_path),
        output_dir=tmp_path / "reports",
        command_resolver=_resolver({}),
        command_runner=_runner({}),
    )

    assert report["commands"]["lsusb"]["available"] is False
    assert report["commands"]["v4l2-ctl"]["available"] is False
    assert report["usb_devices"]["available"] is False
    assert report["v4l2_devices"]["available"] is False
    assert report["errors"] == []


def test_generated_json_has_expected_top_level_keys(tmp_path):
    report = collect_inventory(
        dev_root=_fake_dev_root(tmp_path),
        output_dir=tmp_path / "reports",
        command_resolver=_resolver({}),
        command_runner=_runner({}),
    )

    assert {
        "schema_version",
        "timestamp",
        "hostname",
        "current_user",
        "groups",
        "platform",
        "kernel",
        "devices",
        "commands",
        "python",
        "cv2",
        "usb_devices",
        "pci_devices",
        "v4l2_devices",
        "candidates",
        "safety",
        "errors",
        "output_paths",
    }.issubset(report.keys())


def test_markdown_report_includes_safety_note(tmp_path):
    report = collect_inventory(
        dev_root=_fake_dev_root(tmp_path),
        output_dir=tmp_path / "reports",
        command_resolver=_resolver({}),
        command_runner=_runner({}),
    )

    markdown = render_markdown(report)

    assert "Safety note: inventory only, no devices opened, no commands sent." in markdown
    assert "## Candidate Notes" in markdown


def test_candidate_labels_are_heuristic_only(tmp_path):
    dev_root = _fake_dev_root(tmp_path)
    serial_dir = dev_root / "serial" / "by-id"
    (serial_dir / "usb-SO-ARM-servo-controller").symlink_to("../../ttyUSB0")
    (serial_dir / "usb-base-motor-controller").symlink_to("../../ttyUSB1")

    report = collect_inventory(
        dev_root=dev_root,
        output_dir=tmp_path / "reports",
        command_resolver=_resolver({"lsusb": "/usr/bin/lsusb"}),
        command_runner=_runner({("lsusb",): "Orbbec depth camera"}),
    )

    assert set(report["candidates"]) == {
        "possible_orbbec_camera",
        "possible_so_arm_serial",
        "possible_tracked_base_serial",
    }
    assert report["candidates"]["possible_orbbec_camera"]["candidate"] is True
    for data in report["candidates"].values():
        assert "heuristic" in data["note"].lower() or "confirm manually" in data["note"].lower()


def test_source_does_not_open_cameras_or_serial_ports():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    forbidden_snippets = [
        "cv2.VideoCapture",
        "serial.Serial",
        "pyserial",
        "--enable-live-camera",
        "run_live_camera_probe",
        "run_physical_demo",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in source


def _fake_dev_root(tmp_path):
    dev_root = tmp_path / "dev"
    (dev_root / "serial" / "by-id").mkdir(parents=True)
    (dev_root / "serial" / "by-path").mkdir(parents=True)
    (dev_root / "video0").touch()
    (dev_root / "ttyUSB0").touch()
    (dev_root / "ttyUSB1").touch()
    return dev_root


def _resolver(available):
    def resolve(name):
        return available.get(name)

    return resolve


def _runner(outputs):
    def run(args):
        key = tuple(args)
        return CommandResult(returncode=0, stdout=outputs.get(key, ""), stderr="")

    return run
