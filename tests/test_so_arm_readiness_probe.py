import json
import os
import stat
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
    assert "No serial port opened. No bytes sent. Metadata only." in result.stdout
    assert "Status: fail_closed" in result.stdout
    assert "Exit code: 2" in result.stdout
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
            "--enable-metadata-check",
            "--device",
            str(fake_device),
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert f"Requested device: {fake_device}" in result.stdout
    assert "Exists: True" in result.stdout
    assert "Opt-in acknowledged: this implementation only checked path metadata." in result.stdout
    assert "No serial port opened. No bytes sent. Metadata only." in result.stdout


def test_help_text_makes_metadata_only_boundary_obvious():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    normalized_stdout = " ".join(result.stdout.split())

    assert result.returncode == 0
    assert "--enable-metadata-check" in result.stdout
    assert "--enable-serial-open" in result.stdout
    assert "Compatibility alias for --enable-metadata-check" in result.stdout
    assert "metadata only" in result.stdout
    assert "never opens serial and never sends bytes" in normalized_stdout
    assert "does not prove the arm is safe to move" in normalized_stdout
    assert "--enable-permission-check" in result.stdout


def test_missing_opt_in_fake_path_returns_not_ready(tmp_path):
    fake_device = tmp_path / "missing-so-arm-controller"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--enable-metadata-check",
            "--device",
            str(fake_device),
            "--output-dir",
            str(tmp_path / "reports"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert f"Requested device: {fake_device}" in result.stdout
    assert "Exists: False" in result.stdout
    assert "Status: device_path_missing" in result.stdout
    assert "Exit code: 1" in result.stdout
    assert "Check USB connection, power, and /dev/serial/by-id path." in result.stdout


def test_metadata_check_writes_json_and_markdown_reports_to_output_dir(tmp_path):
    fake_device = tmp_path / "fake-so-arm-controller"
    fake_device.write_text("", encoding="utf-8")
    output_dir = tmp_path / "so-arm-readiness"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--enable-metadata-check",
            "--device",
            str(fake_device),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    json_path = output_dir / "latest.json"
    markdown_path = output_dir / "latest.md"
    report = json.loads(json_path.read_text(encoding="utf-8"))

    assert result.returncode == 0
    assert json_path.is_file()
    assert markdown_path.is_file()
    assert f"JSON report: {json_path}" in result.stdout
    assert f"Markdown report: {markdown_path}" in result.stdout
    assert report["known_controller_path"] == probe.KNOWN_SO_ARM_DEVICE
    assert report["requested_device"] == str(fake_device)
    assert report["identity_basis"] == probe.IDENTITY_BASIS
    assert report["phase_1_note"] == probe.PHASE_1_NOTE
    assert report["status"] == "metadata_checked"
    assert report["exit_code"] == 0
    assert "protocol/library discovery" in report["next_operator_action"]
    assert report["path_metadata"]["exists"] is True
    assert report["path_metadata"]["readable"] is True
    assert report["path_metadata"]["writable"] is True
    assert report["safety_flags"] == probe.SAFETY_FLAGS

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# SO-ARM Readiness Phase 1" in markdown
    assert "Phase 1 does not open serial and sends no bytes." in markdown
    assert "- Status: `metadata_checked`" in markdown
    assert "- Exit code: `0`" in markdown
    assert "Next operator action:" in markdown
    assert "- serial_opened: false" in markdown
    assert "- actuator_calls: false" in markdown


def test_permission_check_report_recommends_group_membership_when_user_lacks_device_group(
    tmp_path, monkeypatch
):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")

    monkeypatch.setattr(probe.getpass, "getuser", lambda: "janus-test")
    monkeypatch.setattr(probe.os, "getuid", lambda: 1000)
    monkeypatch.setattr(probe.os, "getgid", lambda: 1000)
    monkeypatch.setattr(probe.os, "getgroups", lambda: [1000])
    monkeypatch.setattr(
        probe.pwd,
        "getpwuid",
        lambda uid: type("User", (), {"pw_name": "root" if uid == 0 else "janus-test"})(),
    )
    monkeypatch.setattr(
        probe.grp,
        "getgrgid",
        lambda gid: type("Group", (), {"gr_name": "dialout" if gid == 20 else "janus-test"})(),
    )

    readiness = probe.inspect_permission_readiness(
        str(fake_device),
        access_fn=lambda device, mode: False,
        stat_fn=lambda path: os.stat_result(
            (
                stat.S_IFCHR | 0o660,
                1,
                1,
                1,
                0,
                20,
                0,
                0,
                0,
                0,
            )
        ),
    )
    status = probe.determine_phase_2_status(readiness)
    report = probe.build_report(readiness.path_metadata, status, permission_readiness=readiness)

    assert status.status == "permission_check_operator_action_required"
    assert status.exit_code == 0
    assert readiness.owner_name == "root"
    assert readiness.group_name == "dialout"
    assert readiness.user_in_device_group is False
    assert readiness.operator_action_required is True
    assert readiness.recommended_operator_commands == ['sudo usermod -aG dialout "$USER"']
    assert readiness.recommended_relogin_required is True
    assert report["phase"] == "phase_2_permissions_operator_readiness"
    assert report["operator_readiness"]["operator_action_required"] is True
    assert report["operator_readiness"]["recommended_operator_commands"] == [
        'sudo usermod -aG dialout "$USER"'
    ]
    assert "does not confirm that the arm is safe to move" in report["phase_2_limitations"]


def test_permission_check_reports_group_ready_without_motion_readiness(tmp_path, monkeypatch):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")

    monkeypatch.setattr(probe.getpass, "getuser", lambda: "janus-test")
    monkeypatch.setattr(probe.os, "getuid", lambda: 1000)
    monkeypatch.setattr(probe.os, "getgid", lambda: 1000)
    monkeypatch.setattr(probe.os, "getgroups", lambda: [20, 1000])
    monkeypatch.setattr(
        probe.pwd,
        "getpwuid",
        lambda uid: type("User", (), {"pw_name": "root" if uid == 0 else "janus-test"})(),
    )
    monkeypatch.setattr(
        probe.grp,
        "getgrgid",
        lambda gid: type("Group", (), {"gr_name": "dialout" if gid == 20 else "janus-test"})(),
    )

    readiness = probe.inspect_permission_readiness(
        str(fake_device),
        access_fn=lambda device, mode: True,
        stat_fn=lambda path: os.stat_result(
            (
                stat.S_IFCHR | 0o660,
                1,
                1,
                1,
                0,
                20,
                0,
                0,
                0,
                0,
            )
        ),
    )
    status = probe.determine_phase_2_status(readiness)
    markdown = probe.render_markdown(
        probe.build_report(readiness.path_metadata, status, permission_readiness=readiness)
    )

    assert status.status == "permission_check_ready_for_future_identity_phase"
    assert readiness.user_in_device_group is True
    assert readiness.operator_action_required is False
    assert readiness.recommended_operator_commands == []
    assert "This is not a hardware movement readiness result." in markdown
    assert "does not confirm torque/motor readiness" in markdown


def test_permission_check_recommends_relogin_when_group_file_is_updated_but_session_is_not(
    tmp_path, monkeypatch
):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")

    monkeypatch.setattr(probe.getpass, "getuser", lambda: "janus-test")
    monkeypatch.setattr(probe.os, "getuid", lambda: 1000)
    monkeypatch.setattr(probe.os, "getgid", lambda: 1000)
    monkeypatch.setattr(probe.os, "getgroups", lambda: [1000])
    monkeypatch.setattr(
        probe.pwd,
        "getpwuid",
        lambda uid: type("User", (), {"pw_name": "root" if uid == 0 else "janus-test"})(),
    )
    monkeypatch.setattr(
        probe.grp,
        "getgrgid",
        lambda gid: type(
            "Group",
            (),
            {
                "gr_name": "dialout" if gid == 20 else "janus-test",
                "gr_mem": ["janus-test"] if gid == 20 else [],
            },
        )(),
    )

    readiness = probe.inspect_permission_readiness(
        str(fake_device),
        access_fn=lambda device, mode: False,
        stat_fn=lambda path: os.stat_result(
            (
                stat.S_IFCHR | 0o660,
                1,
                1,
                1,
                0,
                20,
                0,
                0,
                0,
                0,
            )
        ),
    )

    assert readiness.user_in_device_group is False
    assert readiness.user_listed_in_device_group is True
    assert readiness.operator_action_required is True
    assert readiness.recommended_operator_commands == []
    assert readiness.recommended_relogin_required is True
    assert "Log out and back in, or reboot" in readiness.operator_action_reason


def test_permission_check_missing_device_recommends_safe_discovery_command(tmp_path):
    missing_device = tmp_path / "missing-ttyUSB0"

    readiness = probe.inspect_permission_readiness(str(missing_device))
    status = probe.determine_phase_2_status(readiness)

    assert status.status == "permission_check_device_path_missing"
    assert status.exit_code == 1
    assert readiness.path_exists is False
    assert readiness.operator_action_required is True
    assert readiness.recommended_operator_commands == ["ls -l /dev/ttyUSB* /dev/ttyACM*"]
    assert readiness.recommended_relogin_required is False


def test_backward_compatible_serial_open_flag_is_metadata_only(tmp_path):
    fake_device = tmp_path / "fake-so-arm-controller"
    fake_device.write_text("", encoding="utf-8")
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--enable-serial-open",
            "--device",
            str(fake_device),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert (output_dir / "latest.json").is_file()
    assert "No serial port opened. No bytes sent. Metadata only." in result.stdout
    assert "Opt-in acknowledged: this implementation only checked path metadata." in result.stdout


def test_5A_success_uses_mock_backend_without_read_write(tmp_path):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")
    calls = {"opened": 0, "closed": 0, "read": 0, "write": 0}

    class FakeSerial:
        def __init__(self, port, baudrate, timeout, write_timeout):
            calls["opened"] += 1
            self.port = port
            self.baudrate = baudrate
            self.timeout = timeout
            self.write_timeout = write_timeout

        def close(self):
            calls["closed"] += 1

        def read(self, _size=1):
            calls["read"] += 1
            raise AssertionError("Phase 5A must not read")

        def write(self, _payload):
            calls["write"] += 1
            raise AssertionError("Phase 5A must not write")

    readiness = probe.inspect_permission_readiness(str(fake_device))
    result = probe.perform_serial_open_close_check(
        readiness,
        serial_factory=FakeSerial,
        timeout_seconds=0.25,
    )

    assert result.exit_code == 0
    assert result.status == "serial_open_close_ready"
    assert result.serial_open_attempted is True
    assert result.serial_opened is True
    assert result.serial_closed is True
    assert result.serial_backend == "pyserial"
    assert result.serial_timeout_seconds == 0.25
    assert result.serial_bytes_written == 0
    assert result.serial_bytes_read == 0
    assert result.safety_flags["serial_opened"] is True
    assert result.safety_flags["serial_commands_sent"] is False
    assert calls == {"opened": 1, "closed": 1, "read": 0, "write": 0}


def test_phase_5a_serial_open_failure_fails_closed(tmp_path):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")

    class FailingSerial:
        def __init__(self, port, baudrate, timeout, write_timeout):
            raise PermissionError("denied")

    readiness = probe.inspect_permission_readiness(str(fake_device))
    result = probe.perform_serial_open_close_check(readiness, serial_factory=FailingSerial)

    assert result.exit_code == 1
    assert result.status == "serial_open_close_failed"
    assert result.serial_open_attempted is True
    assert result.serial_opened is False
    assert result.serial_closed is False
    assert result.serial_bytes_written == 0
    assert result.serial_bytes_read == 0
    assert "denied" in result.error
    assert result.safety_flags["serial_opened"] is False
    assert result.safety_flags["torque_enabled"] is False


def test_phase_5a_missing_backend_fails_closed(tmp_path):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")
    readiness = probe.inspect_permission_readiness(str(fake_device))

    result = probe.perform_serial_open_close_check(
        readiness,
        serial_factory_loader=lambda: (_ for _ in ()).throw(ModuleNotFoundError("serial")),
    )

    assert result.exit_code == 1
    assert result.status == "serial_backend_missing"
    assert result.serial_open_attempted is False
    assert result.serial_opened is False
    assert result.serial_closed is False
    assert result.serial_backend == "missing_pyserial"
    assert "pyserial is not installed" in result.next_operator_action


def test_phase_5a_report_contains_limitations_and_serial_evidence(tmp_path):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")

    class FakeSerial:
        def __init__(self, port, baudrate, timeout, write_timeout):
            pass

        def close(self):
            pass

    readiness = probe.inspect_permission_readiness(str(fake_device))
    serial_check = probe.perform_serial_open_close_check(readiness, serial_factory=FakeSerial)
    report = probe.build_report(
        readiness.path_metadata,
        probe.Phase1Status(
            exit_code=serial_check.exit_code,
            status=serial_check.status,
            next_operator_action=serial_check.next_operator_action,
        ),
        permission_readiness=readiness,
        serial_open_close_result=serial_check,
    )
    markdown = probe.render_markdown(report)

    assert report["phase"] == "5A"
    assert report["mode"] == "serial_open_close_check"
    assert report["serial_open_attempted"] is True
    assert report["serial_opened"] is True
    assert report["serial_closed"] is True
    assert report["serial_bytes_written"] == 0
    assert report["serial_bytes_read"] == 0
    assert "does not validate protocol" in report["phase_5a_limitations"]
    assert "# SO-ARM Readiness Phase 5A" in markdown
    assert "- Serial opened: True" in markdown
    assert "- serial_commands_sent: false" in markdown


def test_cli_5A_uses_mocked_backend(tmp_path, monkeypatch):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")
    output_dir = tmp_path / "reports"

    class FakeSerial:
        def __init__(self, port, baudrate, timeout, write_timeout):
            pass

        def close(self):
            pass

    monkeypatch.setattr(probe, "load_serial_factory", lambda: FakeSerial)
    exit_code = probe.main(
        [
            "--enable-serial-open-close-check",
            "--device",
            str(fake_device),
            "--output-dir",
            str(output_dir),
        ]
    )
    report = json.loads((output_dir / "latest.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["phase"] == "5A"
    assert report["serial_opened"] is True
    assert report["serial_closed"] is True
    assert report["serial_bytes_written"] == 0
    assert report["serial_bytes_read"] == 0


def test_identity_state_plan_is_deterministic_and_non_executing(tmp_path):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")
    readiness = probe.inspect_permission_readiness(str(fake_device))

    first = probe.plan_identity_state_query(readiness)
    second = probe.plan_identity_state_query(readiness)

    assert first == second
    assert first.phase == "5B"
    assert first.mode == "identity_state_query_plan"
    assert first.execution_available is False
    assert first.protocol_candidate == "Feetech serial bus servo protocol"
    assert first.library_candidate == "LeRobot Feetech SDK / scservo-compatible SDK"
    assert first.query_requires_bytes is True
    assert first.torque_required is False
    assert first.movement_required is False
    assert first.homing_required is False
    assert first.safe_to_execute_now is False
    assert first.safety_flags == probe.SAFETY_FLAGS
    assert first.recommended_next_commands == [
        ".venv/bin/python scripts/probe_so_arm_readiness.py --plan-identity-state-query",
        ".venv/bin/python scripts/probe_so_arm_readiness.py --enable-serial-open-close-check",
    ]


def test_identity_state_plan_report_is_json_serializable(tmp_path):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")
    readiness = probe.inspect_permission_readiness(str(fake_device))
    plan = probe.plan_identity_state_query(readiness)
    status = probe.Phase1Status(
        exit_code=plan.exit_code,
        status=plan.status,
        next_operator_action=plan.next_operator_action,
    )

    report = probe.build_report(
        readiness.path_metadata,
        status,
        permission_readiness=readiness,
        identity_state_plan=plan,
    )
    encoded = json.dumps(report, sort_keys=True)
    markdown = probe.render_markdown(report)

    assert '"phase": "5B"' in encoded
    assert report["execution_available"] is False
    assert report["query_requires_bytes"] is True
    assert report["safety_flags"]["serial_opened"] is False
    assert report["operator_preconditions"]
    assert "SO-ARM Readiness Phase 5B Plan" in markdown
    assert "Identity/state query is not executed" in markdown


def test_cli_identity_state_plan_writes_report_without_serial_open(tmp_path, monkeypatch):
    fake_device = tmp_path / "ttyUSB0"
    fake_device.write_text("", encoding="utf-8")
    output_dir = tmp_path / "reports"

    def forbidden_serial_loader():
        raise AssertionError("planner must not load serial")

    monkeypatch.setattr(probe, "load_serial_factory", forbidden_serial_loader)
    exit_code = probe.main(
        [
            "--plan-identity-state-query",
            "--device",
            str(fake_device),
            "--output-dir",
            str(output_dir),
        ]
    )
    report = json.loads((output_dir / "latest.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["phase"] == "5B"
    assert report["mode"] == "identity_state_query_plan"
    assert report["execution_available"] is False
    assert report["safe_to_execute_now"] is False
    assert report["safety_flags"] == probe.SAFETY_FLAGS


def test_help_text_exposes_identity_state_planning_without_live_execution():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--plan-identity-state-query" in result.stdout
    assert "--enable-identity-state-query" not in result.stdout
    assert "--execute" not in result.stdout


def test_cli_permission_check_writes_operator_readiness_fields(tmp_path):
    fake_device = tmp_path / "fake-so-arm-controller"
    fake_device.write_text("", encoding="utf-8")
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--enable-permission-check",
            "--device",
            str(fake_device),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    report = json.loads((output_dir / "latest.json").read_text(encoding="utf-8"))

    assert result.returncode == 0
    assert "Phase 2 permission/operator readiness" in result.stdout
    assert "This is not a hardware movement readiness result." in result.stdout
    assert report["phase"] == "phase_2_permissions_operator_readiness"
    assert report["device_path"] == str(fake_device)
    assert "operator_readiness" in report
    assert "recommended_operator_commands" in report["operator_readiness"]
    assert report["safety_flags"] == probe.SAFETY_FLAGS


def test_metadata_report_represents_permission_incomplete_state(tmp_path, monkeypatch):
    fake_device = tmp_path / "fake-so-arm-controller"
    fake_device.write_text("", encoding="utf-8")
    output_dir = tmp_path / "reports"

    monkeypatch.setattr(probe.socket, "gethostname", lambda: "valera-test")
    monkeypatch.setattr(probe.getpass, "getuser", lambda: "janus-test")
    readiness = probe.inspect_path(str(fake_device), access_fn=lambda device, mode: False)
    status = probe.determine_phase_1_status(readiness, metadata_check=True)
    report = probe.build_report(readiness, status)
    json_path, _markdown_path = probe.write_reports(report, output_dir)

    written_report = json.loads(json_path.read_text(encoding="utf-8"))

    assert status.exit_code == 0
    assert written_report["path_metadata"]["exists"] is True
    assert written_report["path_metadata"]["readable"] is False
    assert written_report["path_metadata"]["writable"] is False
    assert written_report["status"] == "metadata_checked_permissions_incomplete"
    assert "dialout" in written_report["next_operator_action"]
    assert "Do not open serial or send commands yet." in written_report["next_operator_action"]


def test_rendered_report_contains_required_phase_1_metadata(tmp_path, monkeypatch):
    fake_device = tmp_path / "fake-so-arm-controller"
    fake_device.write_text("", encoding="utf-8")
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "valera-test")
    monkeypatch.setattr(probe.getpass, "getuser", lambda: "janus-test")
    monkeypatch.setattr(probe.os, "getgroups", lambda: [1000])
    monkeypatch.setattr(probe.grp, "getgrgid", lambda gid: type("Group", (), {"gr_name": "dialout"})())

    readiness = probe.inspect_path(str(fake_device))
    status = probe.determine_phase_1_status(readiness, metadata_check=True)
    report = probe.build_report(readiness, status)
    markdown = probe.render_markdown(report)

    assert report["timestamp"]
    assert report["hostname"] == "valera-test"
    assert report["user"] == "janus-test"
    assert report["groups"] == [{"gid": 1000, "name": "dialout"}]
    assert report["resolved_target"] == str(fake_device)
    assert report["exit_code"] == 0
    assert report["safety_flags"]["torque_enabled"] is False
    assert "- `dialout` (1000)" in markdown


def test_status_model_keeps_metadata_check_from_implying_motion_readiness(tmp_path):
    fake_device = tmp_path / "fake-so-arm-controller"
    fake_device.write_text("", encoding="utf-8")

    readiness = probe.inspect_path(
        str(fake_device),
        access_fn=lambda device, mode: mode == os.R_OK,
    )
    status = probe.determine_phase_1_status(readiness, metadata_check=True)

    assert status.exit_code == 0
    assert status.status == "metadata_checked_permissions_incomplete"
    assert "Phase 2 should check Linux group membership" in status.next_operator_action
    assert "Do not open serial or send commands yet." in status.next_operator_action


def test_source_has_no_serial_or_actuator_operations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    forbidden_snippets = [
        "os.open(",
        "open(",
        ".write(",
        ".read(",
        "enable_torque(",
        "move(",
        "actuate(",
        "import lerobot",
        "from lerobot",
        "LeRobotArmAdapter",
        "run_physical_demo",
        "run_live_camera_probe",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in source

    assert "import_module(\"serial\")" in source
    assert "getattr(serial_module, \"Serial\")" in source
