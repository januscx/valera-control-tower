import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("scripts/dry_run_arm_command.py")


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        text=True,
        capture_output=True,
    )


def test_cli_sim_noop_prints_json_dry_run_result():
    completed = run_cli("--adapter", "sim", "--command", "noop", "--reason", "verification")

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["accepted"] is True
    assert payload["executable_now"] is False
    assert payload["adapter_id"] == "sim-arm"
    assert payload["safety_flags"]["serial_opened"] is False


def test_cli_metadata_only_open_gripper_is_preview_only():
    completed = run_cli(
        "--adapter",
        "metadata-only-so-arm",
        "--command",
        "open-gripper",
        "--reason",
        "verification",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["accepted"] is True
    assert payload["executable_now"] is False
    assert payload["status"] == "accepted_dry_run"
    assert payload["unavailable_capabilities"] == ["can_move"]


def test_cli_invalid_adapter_fails_closed():
    completed = run_cli("--adapter", "hardware", "--command", "noop", "--reason", "verification")

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["accepted"] is False
    assert payload["status"] == "rejected_schema"
    assert "unknown adapter" in " ".join(payload["messages"])


def test_cli_source_has_no_live_execution_flags_or_hardware_calls():
    source = SCRIPT.read_text(encoding="utf-8")

    forbidden_snippets = [
        "serial.Serial",
        "import serial",
        "from serial",
        "os.open(",
        ".write(",
        ".read(",
        "enable_torque",
        "torque_enabled = True",
        "movement_commanded = True",
        "actuator_calls = True",
        "import lerobot",
        "from lerobot",
        "--execute",
        "--live",
        "--enable-motion",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in source
