import subprocess
import sys
from pathlib import Path

from scripts import probe_so_arm_readiness as probe


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "probe_so_arm_readiness.py"


def test_default_run_is_fail_closed_and_reports_known_path():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert probe.KNOWN_SO_ARM_DEVICE in result.stdout
    assert "Fail-closed: serial access is disabled by default." in result.stdout
    assert "serial_opened: false" in result.stdout
    assert "serial_commands_sent: false" in result.stdout


def test_default_main_does_not_inspect_real_device_when_injected():
    opened = []

    def fake_stat(path):
        opened.append(path)
        raise FileNotFoundError(path)

    readiness = probe.inspect_path("/tmp/fake-so-arm", stat_fn=fake_stat)

    assert opened == [Path("/tmp/fake-so-arm")]
    assert readiness.exists is False
    assert readiness.readable is False
    assert readiness.writable is False


def test_opt_in_path_uses_fake_file_only(tmp_path):
    fake_device = tmp_path / "fake-so-arm-controller"
    fake_device.write_text("", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--enable-serial-open",
            "--device",
            str(fake_device),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert f"Requested device: {fake_device}" in result.stdout
    assert "Exists: True" in result.stdout
    assert "Opt-in acknowledged: this implementation only checked path metadata." in result.stdout
    assert "No serial port was opened and no bytes were sent." in result.stdout


def test_missing_opt_in_fake_path_returns_not_ready(tmp_path):
    fake_device = tmp_path / "missing-so-arm-controller"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--enable-serial-open",
            "--device",
            str(fake_device),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert f"Requested device: {fake_device}" in result.stdout
    assert "Exists: False" in result.stdout


def test_source_has_no_serial_or_actuator_operations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    forbidden_snippets = [
        "serial.Serial",
        "pyserial",
        ".write(",
        "enable_torque(",
        "move(",
        "actuate(",
        "run_physical_demo",
        "run_live_camera_probe",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in source
