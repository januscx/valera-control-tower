import json
from pathlib import Path

import pytest

from robot.arm_commands import (
    ArmCommand,
    ArmCommandEnvelope,
    ArmCommandStatus,
    ArmCommandType,
    dry_run_arm_command,
)
from robot.adapters.sim_arm import SimArmAdapter
from robot.adapters.so_arm_metadata import MetadataOnlySOArmAdapter


def make_command(
    command_type: ArmCommandType = ArmCommandType.NOOP,
    *,
    target: dict[str, object] | None = None,
    reason: str = "verification preview",
    requested_by: str = "pytest",
    dry_run: bool = True,
) -> ArmCommandEnvelope:
    return ArmCommandEnvelope(
        command_id="cmd-001",
        command_type=command_type,
        target={} if target is None else target,
        reason=reason,
        requested_by=requested_by,
        dry_run=dry_run,
    )


def test_valid_noop_dry_run_is_accepted_and_never_executable():
    result = dry_run_arm_command(make_command(), SimArmAdapter())

    assert result.accepted is True
    assert result.executable_now is False
    assert result.status == ArmCommandStatus.ACCEPTED_DRY_RUN
    assert result.schema_valid is True
    assert result.safety_valid is True
    assert result.required_capabilities == []
    assert result.unavailable_capabilities == []
    assert result.safety_flags == {
        "serial_opened": False,
        "serial_commands_sent": False,
        "torque_enabled": False,
        "movement_commanded": False,
        "actuator_calls": False,
    }
    assert result.evidence["adapter_mode"] == "simulation"
    assert result.evidence["dry_run_status"] == "accepted_dry_run"


def test_arm_command_can_be_wrapped_in_evidence_envelope():
    command = ArmCommand(
        command_type=ArmCommandType.MOVE_TO_POSE,
        target={"pose_id": "inspection"},
    )
    envelope = ArmCommandEnvelope.from_command(
        command_id="cmd-from-intent",
        command=command,
        reason="preview a named pose",
        requested_by="pytest",
    )

    result = dry_run_arm_command(envelope, SimArmAdapter())

    assert result.accepted is True
    assert result.command_id == "cmd-from-intent"
    assert result.command_type == "move_to_pose"


@pytest.mark.parametrize(
    ("command_type", "target", "required_capabilities"),
    [
        (ArmCommandType.HOME, {"profile": "safe_home"}, ["can_move"]),
        (ArmCommandType.OPEN_GRIPPER, {"width_intent": "wide"}, ["can_move"]),
        (ArmCommandType.MOVE_TO_POSE, {"pose_id": "inspection"}, ["can_move"]),
    ],
)
def test_motion_intents_are_valid_dry_run_but_not_executable(
    command_type: ArmCommandType,
    target: dict[str, object],
    required_capabilities: list[str],
):
    result = dry_run_arm_command(
        make_command(command_type, target=target),
        SimArmAdapter(),
    )

    assert result.accepted is True
    assert result.executable_now is False
    assert result.status == ArmCommandStatus.ACCEPTED_DRY_RUN
    assert result.required_capabilities == required_capabilities
    assert "Phase 4 is dry-run only" in result.messages
    assert result.evidence["blocked_reason"] == "execution_not_available_in_phase_4"


def test_metadata_only_so_arm_blocks_execution_capabilities_but_accepts_safe_intent(tmp_path):
    device = tmp_path / "ttyUSB0"
    device.write_text("", encoding="utf-8")
    adapter = MetadataOnlySOArmAdapter(device_path=str(device))

    result = dry_run_arm_command(
        make_command(ArmCommandType.HOME, target={"profile": "safe_home"}),
        adapter,
    )

    assert result.accepted is True
    assert result.executable_now is False
    assert result.status == ArmCommandStatus.ACCEPTED_DRY_RUN
    assert result.unavailable_capabilities == ["can_move"]
    assert result.evidence["adapter_id"] == "metadata-only-so-arm"
    assert result.evidence["adapter_mode"] == "probe"


@pytest.mark.parametrize(
    "command",
    [
        make_command(reason=""),
        make_command(requested_by=""),
        make_command(dry_run=False),
        make_command(ArmCommandType.MOVE_TO_POSE, target={"joint_angles": [0, 1, 2]}),
        make_command(ArmCommandType.OPEN_GRIPPER, target={"raw_serial_bytes": "00ff"}),
        make_command(ArmCommandType.CLOSE_GRIPPER, target={"torque": 1.0}),
        make_command(ArmCommandType.HOLD_POSITION, target={"current": 0.2}),
    ],
)
def test_invalid_or_unsafe_commands_are_rejected(command: ArmCommandEnvelope):
    result = dry_run_arm_command(command, SimArmAdapter())

    assert result.accepted is False
    assert result.executable_now is False
    assert result.status in {
        ArmCommandStatus.REJECTED_SCHEMA,
        ArmCommandStatus.REJECTED_SAFETY,
    }
    assert all(flag is False for flag in result.safety_flags.values())


def test_unknown_command_type_is_rejected_when_building_from_cli_value():
    result = dry_run_arm_command(
        ArmCommandEnvelope.from_command_name(
            command_id="cmd-unknown",
            command_name="teleport",
            target={},
            reason="verification preview",
            requested_by="pytest",
        ),
        SimArmAdapter(),
    )

    assert result.accepted is False
    assert result.status == ArmCommandStatus.REJECTED_SCHEMA
    assert "unknown command type" in " ".join(result.messages)


def test_non_object_target_is_rejected_as_schema_invalid():
    command = ArmCommandEnvelope(
        command_id="cmd-bad-target",
        command_type=ArmCommandType.NOOP,
        target=[],  # type: ignore[arg-type]
        reason="verification preview",
        requested_by="pytest",
    )

    result = dry_run_arm_command(command, SimArmAdapter())

    assert result.accepted is False
    assert result.status == ArmCommandStatus.REJECTED_SCHEMA
    assert "target must be an object" in result.messages


def test_dry_run_result_is_json_serializable():
    result = dry_run_arm_command(make_command(), SimArmAdapter())

    encoded = json.dumps(result.to_dict(), sort_keys=True)

    assert '"serial_opened": false' in encoded
    assert '"command_type": "noop"' in encoded


def test_arm_command_module_has_no_hardware_execution_operations():
    source = Path("robot/arm_commands.py").read_text(encoding="utf-8")

    forbidden_snippets = [
        "serial.Serial",
        "import serial",
        "from serial",
        "os.open(",
        "open(",
        ".write(",
        ".read(",
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
