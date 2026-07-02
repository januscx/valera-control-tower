from robot.adapters.base import (
    AdapterFailure,
    AdapterHealth,
    AdapterIdentity,
    AdapterMode,
    AdapterResult,
    AdapterStatus,
    AdapterType,
)


def test_common_adapter_models_are_explicit_and_structured():
    identity = AdapterIdentity(
        adapter_id="sim-arm-001",
        adapter_type=AdapterType.ARM,
        mode=AdapterMode.SIMULATION,
        display_name="Simulated arm",
    )
    health = AdapterHealth(status=AdapterStatus.OK, message="ready")
    failure = AdapterFailure(code="adapter.timeout", message="probe timed out")
    result = AdapterResult(ok=False, identity=identity, health=health, failure=failure)

    assert identity.adapter_type == AdapterType.ARM
    assert identity.mode == AdapterMode.SIMULATION
    assert health.status == AdapterStatus.OK
    assert result.ok is False
    assert result.failure.code == "adapter.timeout"


from robot.adapters.arm import (
    ArmCapabilities,
    ArmCommandResult,
    ArmJointState,
    ArmProbeResult,
    ArmState,
)


def test_arm_probe_result_is_read_only_and_project_owned():
    identity = AdapterIdentity(
        adapter_id="so101-probe",
        adapter_type=AdapterType.ARM,
        mode=AdapterMode.PROBE,
    )
    health = AdapterHealth(status=AdapterStatus.OK, message="controller detected")
    capabilities = ArmCapabilities(
        can_read_state=True,
        can_enable_torque=False,
        can_move=False,
        joint_count=6,
        supported_commands=("probe", "read_state"),
    )
    state = ArmState(
        joints=(
            ArmJointState(name="base", position_deg=0.0),
            ArmJointState(name="shoulder", position_deg=15.0),
        ),
        gripper_open=None,
        torque_enabled=False,
    )
    result = ArmProbeResult(
        ok=True,
        identity=identity,
        health=health,
        capabilities=capabilities,
        state=state,
        runtime="lerobot",
    )

    assert result.capabilities.can_move is False
    assert result.state.torque_enabled is False
    assert result.runtime == "lerobot"


def test_arm_command_result_can_block_motion_without_success():
    identity = AdapterIdentity(
        adapter_id="so101-probe",
        adapter_type=AdapterType.ARM,
        mode=AdapterMode.PROBE,
    )
    health = AdapterHealth(status=AdapterStatus.BLOCKED, message="motion disabled")
    result = ArmCommandResult(
        ok=False,
        identity=identity,
        health=health,
        command_name="move_joints",
        executed=False,
        failure=AdapterFailure(
            code="hardware.motion.blocked",
            message="missing --allow-motion",
        ),
    )

    assert result.ok is False
    assert result.executed is False
    assert result.failure.code == "hardware.motion.blocked"
