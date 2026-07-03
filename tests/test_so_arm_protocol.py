import json
from pathlib import Path

from robot.so_arm_protocol import (
    build_default_identity_query_plan,
    execute_confirmed_identity_query,
    parse_feetech_status_response,
)


def test_default_feetech_ping_plan_reports_exact_request_bytes():
    plan = build_default_identity_query_plan(servo_id=1)

    assert plan.protocol_candidate.name == "Feetech serial bus servo protocol"
    assert plan.request.query_name == "feetech_ping_servo_id_1"
    assert plan.request.request_bytes_hex == "ff ff 01 02 01 fb"
    assert plan.request.query_is_passive is False
    assert plan.safety.torque_required is False
    assert plan.safety.movement_required is False
    assert plan.safety.homing_required is False
    assert plan.safety.actuator_calls is False
    assert plan.execution_approved is False
    assert json.loads(json.dumps(plan.to_dict()))["request"]["bytes_to_write"] == 6


def test_parse_mocked_feetech_ping_response_detects_identity():
    result = parse_feetech_status_response(bytes.fromhex("ff ff 01 02 00 fc"), expected_servo_id=1)

    assert result.status == "identity_query_response_valid"
    assert result.identity_detected is True
    assert result.identity_summary == {"servo_id": 1, "status_error": 0}
    assert result.identity_response_bytes_read == 6
    assert result.torque_enabled is False
    assert result.movement_commanded is False
    assert result.actuator_calls is False


def test_parse_mocked_timeout_and_unexpected_response_fail_closed():
    timeout = parse_feetech_status_response(b"", expected_servo_id=1)
    wrong_id = parse_feetech_status_response(bytes.fromhex("ff ff 02 02 00 fb"), expected_servo_id=1)

    assert timeout.status == "identity_query_timeout"
    assert timeout.identity_detected is False
    assert wrong_id.status == "identity_query_unexpected_response"
    assert wrong_id.identity_detected is False


def test_confirmed_identity_query_uses_mock_backend_and_counts_bytes():
    calls = {"opened": 0, "closed": 0, "read": 0, "write": 0}

    class FakeSerial:
        def __init__(self, port, baudrate, timeout, write_timeout):
            calls["opened"] += 1
            self.port = port
            self.baudrate = baudrate
            self.timeout = timeout
            self.write_timeout = write_timeout

        def write(self, payload):
            calls["write"] += 1
            assert payload == bytes.fromhex("ff ff 01 02 01 fb")
            return len(payload)

        def read(self, size):
            calls["read"] += 1
            assert size == 6
            return bytes.fromhex("ff ff 01 02 00 fc")

        def close(self):
            calls["closed"] += 1

    plan = build_default_identity_query_plan(servo_id=1)
    result = execute_confirmed_identity_query(
        plan,
        device_path="/tmp/fake-ttyUSB0",
        serial_factory=FakeSerial,
        execution_approved=True,
    )

    assert result.status == "identity_query_response_valid"
    assert result.serial_open_attempted is True
    assert result.serial_opened is True
    assert result.serial_closed is True
    assert result.serial_commands_sent is True
    assert result.identity_query_bytes_written == 6
    assert result.identity_response_bytes_read == 6
    assert result.identity_detected is True
    assert result.safety_flags["torque_enabled"] is False
    assert result.safety_flags["movement_commanded"] is False
    assert result.safety_flags["actuator_calls"] is False
    assert calls == {"opened": 1, "closed": 1, "read": 1, "write": 1}


def test_identity_query_without_approval_does_not_open_or_send():
    class ForbiddenSerial:
        def __init__(self, *args, **kwargs):
            raise AssertionError("unapproved identity query must not open serial")

    plan = build_default_identity_query_plan(servo_id=1)
    result = execute_confirmed_identity_query(
        plan,
        device_path="/tmp/fake-ttyUSB0",
        serial_factory=ForbiddenSerial,
        execution_approved=False,
    )

    assert result.status == "identity_query_approval_required"
    assert result.serial_open_attempted is False
    assert result.serial_commands_sent is False
    assert result.identity_query_bytes_written == 0
    assert result.identity_response_bytes_read == 0


def test_protocol_module_keeps_hardware_control_surface_narrow():
    source = Path("robot/so_arm_protocol.py").read_text(encoding="utf-8")

    forbidden_snippets = [
        "import lerobot",
        "from lerobot",
        "enable_torque(",
        "home(",
        "move(",
        "calibrate(",
        "set_goal",
        "goal_position",
        "--execute",
        "--live",
        "--enable-motion",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in source

    assert source.count(".write(") == 1
    assert source.count(".read(") == 1
    assert "def execute_confirmed_identity_query(" in source
