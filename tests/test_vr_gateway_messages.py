import math

import pytest

from robot.vr_gateway.messages import (
    ArmJogPayload,
    ArmTargetEvent,
    BaseDrivePayload,
    BaseStopAckEvent,
    BaseTargetEvent,
    CommandEnvelope,
    CommandName,
    CommandRejectedEvent,
    ControlMode,
    EmptyPayload,
    EventName,
    GatewayState,
    GatewayStateEvent,
    MessageValidationError,
    ModeSetPayload,
    ModeTransition,
    NeckTargetEvent,
    Position,
    PosePayload,
    Quaternion,
    RejectionCode,
    SafetyStopEvent,
    SessionStartPayload,
    StopReason,
)


def test_envelope_requires_schema_0_1_and_positive_sequence():
    with pytest.raises(MessageValidationError, match="schema_version"):
        CommandEnvelope("0.2", CommandName.MODE_SET, "session-a", 1, 10, ModeSetPayload("head"))
    with pytest.raises(MessageValidationError, match="sequence"):
        CommandEnvelope("0.1", CommandName.MODE_SET, "session-a", 0, 10, ModeSetPayload("head"))


def test_mode_payload_accepts_unknown_nonempty_string_for_gateway_semantics():
    assert ModeSetPayload("banana").mode == "banana"
    with pytest.raises(MessageValidationError, match="mode"):
        ModeSetPayload("")


def test_pose_requires_quest_local_and_finite_nonzero_quaternion():
    with pytest.raises(MessageValidationError, match="frame"):
        PosePayload("unity_world", Quaternion(0.0, 0.0, 0.0, 1.0))
    with pytest.raises(MessageValidationError, match="finite"):
        Quaternion(math.nan, 0.0, 0.0, 1.0)
    with pytest.raises(MessageValidationError, match="zero"):
        Quaternion(0.0, 0.0, 0.0, 0.0)


def test_quaternion_normalized_returns_unit_value():
    value = Quaternion(0.0, 0.0, 0.0, 2.0).normalized()
    assert value == Quaternion(0.0, 0.0, 0.0, 1.0)


def test_message_enum_contract_is_complete():
    assert {item.value for item in CommandName} == {
        "session.start", "session.stop", "mode.set", "head.pose",
        "head.recenter", "emergency_stop", "emergency_stop.reset",
        "base.drive", "arm.jog",
    }
    assert {item.value for item in GatewayState} == {
        "IDLE", "AWAITING_RECENTER", "ACTIVE", "SAFE_STOPPED",
        "ESTOP_LATCHED",
    }
    assert {item.value for item in RejectionCode} == {
        "STALE_SEQUENCE", "STALE_TIMESTAMP", "SESSION_MISMATCH",
        "NO_ACTIVE_SESSION", "MODE_BLOCKED", "UNKNOWN_MODE",
        "WATCHDOG_ACTIVE", "INVALID_PAYLOAD", "ESTOP_LATCHED",
    }
    assert {item.value for item in StopReason} == {
        "WATCHDOG", "EMERGENCY_STOP", "SESSION_STOPPED",
    }
    assert {item.value for item in EventName} == {
        "gateway.state", "neck.target", "safety.stop", "command.rejected",
        "base.target", "arm.target", "base.stop_ack",
    }


def test_output_event_names_and_safe_action_defaults():
    events = (
        GatewayStateEvent(1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None),
        NeckTargetEvent(1, "session", 1, 0.0, 0.0),
        SafetyStopEvent(1, StopReason.WATCHDOG, "session", 1),
        CommandRejectedEvent(
            1,
            RejectionCode.INVALID_PAYLOAD,
            "invalid",
            None,
            None,
        ),
    )
    known = {EventName.GATEWAY_STATE, EventName.NECK_TARGET, EventName.SAFETY_STOP, EventName.COMMAND_REJECTED}
    assert {event.event_type for event in events} == known
    assert events[1].hold is False
    assert (events[2].neck_action, events[2].base_action, events[2].arm_action) == (
        "HOLD_LAST_POSITION", "STOP", "HOLD",
    )


def test_all_payload_models_accept_their_valid_runtime_shapes():
    assert SessionStartPayload("head").requested_mode == "head"
    assert ModeSetPayload("head").mode == "head"
    assert PosePayload(
        "quest_local", Quaternion(0, 0, 0, 1), Position(1, 2.5, -3)
    ) == PosePayload(
        "quest_local", Quaternion(0.0, 0.0, 0.0, 1.0), Position(1.0, 2.5, -3.0)
    )
    assert EmptyPayload() == EmptyPayload()


@pytest.mark.parametrize(
    ("factory", "match"),
    [
        (lambda: SessionStartPayload(1), "requested_mode"),
        (lambda: SessionStartPayload(""), "requested_mode"),
        (lambda: ModeSetPayload(False), "mode"),
        (lambda: ModeSetPayload(""), "mode"),
        (lambda: PosePayload(1, Quaternion(0, 0, 0, 1)), "frame"),
        (lambda: PosePayload("", Quaternion(0, 0, 0, 1)), "frame"),
        (lambda: PosePayload("quest_local", object()), "orientation"),
        (
            lambda: PosePayload("quest_local", Quaternion(0, 0, 0, 1), object()),
            "position",
        ),
    ],
)
def test_payload_models_reject_wrong_runtime_shapes(factory, match):
    with pytest.raises(MessageValidationError, match=match):
        factory()


@pytest.mark.parametrize("value", [True, "1", None, math.nan, math.inf])
def test_pose_numeric_components_reject_non_json_numbers(value):
    with pytest.raises(MessageValidationError):
        Quaternion(value, 0, 0, 1)
    with pytest.raises(MessageValidationError):
        Position(value, 0, 0)


def test_extreme_finite_quaternion_normalizes_without_overflow():
    value = Quaternion(1e308, 0.0, 0.0, 1.0).normalized()
    assert value.norm == pytest.approx(1.0)
    assert value == Quaternion(1.0, 0.0, 0.0, 1e-308)


def test_quaternion_rejects_nonfinite_hypot_result():
    with pytest.raises(MessageValidationError, match="norm"):
        Quaternion(1e308, 1e308, 1e308, 1e308)


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": 1},
        {"schema_version": "0.2"},
        {"command": "head.pose"},
        {"command": GatewayState.IDLE},
        {"session_id": 1},
        {"session_id": ""},
        {"sequence": True},
        {"sequence": 1.0},
        {"sequence": "1"},
        {"timestamp_ms": False},
        {"timestamp_ms": 0.0},
        {"timestamp_ms": math.nan},
        {"payload": object()},
    ],
)
def test_envelope_rejects_every_boundary_field_type(overrides):
    values = {
        "schema_version": "0.1",
        "command": CommandName.HEAD_POSE,
        "session_id": "session-a",
        "sequence": 1,
        "timestamp_ms": 0,
        "payload": PosePayload("quest_local", Quaternion(0, 0, 0, 1)),
    }
    values.update(overrides)
    with pytest.raises(MessageValidationError):
        CommandEnvelope(**values)


# --- v0.2 enum tests ---

def test_control_mode_values():
    assert ControlMode.HEAD_ONLY.value == "HEAD_ONLY"
    assert ControlMode.DRIVE.value == "DRIVE"
    assert ControlMode.ARM.value == "ARM"


def test_mode_transition_values():
    assert ModeTransition.NONE.value == "NONE"
    assert ModeTransition.STOPPING_BASE.value == "STOPPING_BASE"
    assert ModeTransition.STOPPING_ARM.value == "STOPPING_ARM"


# --- v0.2 payload tests ---

def test_base_drive_payload_valid():
    p = BaseDrivePayload(0.5, -0.3, True)
    assert p.throttle == 0.5
    assert p.steering == -0.3
    assert p.deadman is True


def test_base_drive_payload_out_of_range():
    with pytest.raises(MessageValidationError):
        BaseDrivePayload(1.5, 0.0, True)
    with pytest.raises(MessageValidationError):
        BaseDrivePayload(-1.1, 0.0, True)
    with pytest.raises(MessageValidationError):
        BaseDrivePayload(0.0, 1.5, True)
    with pytest.raises(MessageValidationError):
        BaseDrivePayload(0.0, -1.1, True)


def test_base_drive_payload_non_finite():
    with pytest.raises(MessageValidationError):
        BaseDrivePayload(float("nan"), 0.0, True)
    with pytest.raises(MessageValidationError):
        BaseDrivePayload(0.0, float("inf"), True)


def test_base_drive_payload_deadman_type():
    with pytest.raises(MessageValidationError):
        BaseDrivePayload(0.0, 0.0, "true")  # type: ignore[arg-type]


def test_arm_jog_payload_valid():
    p = ArmJogPayload("JOINT_JOG", True, {"shoulder_pan": 0.5})
    assert p.kind == "JOINT_JOG"
    assert p.deadman is True
    assert p.joint_velocity == {"shoulder_pan": 0.5}


def test_arm_jog_payload_invalid_kind():
    with pytest.raises(MessageValidationError, match="kind must be JOINT_JOG"):
        ArmJogPayload("CARTESIAN", True, {"x": 0.1})


def test_arm_jog_payload_empty_dict():
    with pytest.raises(MessageValidationError, match="non-empty"):
        ArmJogPayload("JOINT_JOG", True, {})


def test_arm_jog_payload_not_a_dict():
    with pytest.raises(MessageValidationError, match="non-empty"):
        ArmJogPayload("JOINT_JOG", True, [])  # type: ignore[arg-type]


def test_arm_jog_payload_velocity_out_of_range():
    with pytest.raises(MessageValidationError, match="must be in"):
        ArmJogPayload("JOINT_JOG", True, {"shoulder_pan": 1.5})


def test_arm_jog_payload_velocity_non_finite():
    with pytest.raises(MessageValidationError):
        ArmJogPayload("JOINT_JOG", True, {"shoulder_pan": float("nan")})


def test_arm_jog_payload_deadman_type():
    with pytest.raises(MessageValidationError):
        ArmJogPayload("JOINT_JOG", "yes", {"j": 0.0})  # type: ignore[arg-type]


# --- v0.2 event DTO tests ---

def test_base_target_event_valid():
    e = BaseTargetEvent(
        gateway_monotonic_ns=1000,
        throttle=0.5,
        steering=-0.3,
        deadman=True,
        command_zeroed=False,
    )
    assert e.throttle == 0.5
    assert e.steering == -0.3
    assert e.deadman is True
    assert e.command_zeroed is False
    assert e.schema_version == "0.1"
    assert e.event_type is EventName.BASE_TARGET


def test_base_target_event_out_of_range():
    with pytest.raises(MessageValidationError):
        BaseTargetEvent(0, 1.5, 0.0, True, False)


def test_base_target_event_non_finite():
    with pytest.raises(MessageValidationError):
        BaseTargetEvent(0, float("nan"), 0.0, True, False)


def test_base_target_event_bool_is_rejected_as_number():
    with pytest.raises(MessageValidationError):
        BaseTargetEvent(0, True, 0.0, True, False)  # type: ignore[arg-type]


def test_base_target_event_deadman_type():
    with pytest.raises(MessageValidationError):
        BaseTargetEvent(0, 0.0, 0.0, 1, False)  # type: ignore[arg-type]


def test_base_target_event_command_zeroed_type():
    with pytest.raises(MessageValidationError):
        BaseTargetEvent(0, 0.0, 0.0, True, None)  # type: ignore[arg-type]


def test_base_target_event_negative_ns():
    with pytest.raises(MessageValidationError, match="non-negative"):
        BaseTargetEvent(-1, 0.0, 0.0, True, False)


def test_arm_target_event_valid():
    e = ArmTargetEvent(
        gateway_monotonic_ns=2000,
        kind="JOINT_JOG",
        deadman=True,
        command_zeroed=False,
        joint_velocity={"shoulder_pan": 0.5, "elbow": -0.3},
    )
    assert e.kind == "JOINT_JOG"
    assert e.joint_velocity == {"shoulder_pan": 0.5, "elbow": -0.3}
    assert e.schema_version == "0.1"
    assert e.event_type is EventName.ARM_TARGET


def test_arm_target_event_invalid_kind():
    with pytest.raises(MessageValidationError, match="kind must be JOINT_JOG"):
        ArmTargetEvent(0, "CARTESIAN", True, False, {"x": 0.1})


def test_arm_target_event_empty_dict():
    with pytest.raises(MessageValidationError, match="non-empty"):
        ArmTargetEvent(0, "JOINT_JOG", True, False, {})


def test_arm_target_event_velocity_out_of_range():
    with pytest.raises(MessageValidationError, match="must be in"):
        ArmTargetEvent(0, "JOINT_JOG", True, False, {"j": 1.5})


def test_arm_target_event_velocity_non_finite():
    with pytest.raises(MessageValidationError):
        ArmTargetEvent(0, "JOINT_JOG", True, False, {"j": float("inf")})


def test_arm_target_event_deadman_type():
    with pytest.raises(MessageValidationError):
        ArmTargetEvent(0, "JOINT_JOG", 1, False, {"j": 0.0})  # type: ignore[arg-type]


def test_arm_target_event_command_zeroed_type():
    with pytest.raises(MessageValidationError):
        ArmTargetEvent(0, "JOINT_JOG", True, 0, {"j": 0.0})  # type: ignore[arg-type]


def test_arm_target_event_negative_ns():
    with pytest.raises(MessageValidationError, match="non-negative"):
        ArmTargetEvent(-1, "JOINT_JOG", True, False, {"j": 0.0})


def test_base_stop_ack_event_valid():
    e = BaseStopAckEvent(
        gateway_monotonic_ns=3000,
        command_zeroed=True,
        stationary_verified=False,
    )
    assert e.command_zeroed is True
    assert e.stationary_verified is False
    assert e.schema_version == "0.1"
    assert e.event_type is EventName.BASE_STOP_ACK


def test_base_stop_ack_event_command_zeroed_type():
    with pytest.raises(MessageValidationError):
        BaseStopAckEvent(0, "yes", False)  # type: ignore[arg-type]


def test_base_stop_ack_event_stationary_verified_type():
    with pytest.raises(MessageValidationError):
        BaseStopAckEvent(0, True, "no")  # type: ignore[arg-type]


# --- v0.2 updated GatewayStateEvent ---

def test_gateway_state_event_with_mode():
    e = GatewayStateEvent(
        gateway_monotonic_ns=1000,
        state=GatewayState.ACTIVE,
        current_mode=ControlMode.DRIVE,
        session_id="s1",
        sequence=5,
    )
    assert e.current_mode is ControlMode.DRIVE
    assert e.transition is ModeTransition.NONE
    assert e.requested_mode is None
    assert e.schema_version == "0.1"
    assert e.event_type is EventName.GATEWAY_STATE


def test_gateway_state_event_with_transition():
    e = GatewayStateEvent(
        gateway_monotonic_ns=2000,
        state=GatewayState.SAFE_STOPPED,
        current_mode=ControlMode.HEAD_ONLY,
        session_id="s1",
        sequence=6,
        requested_mode=ControlMode.DRIVE,
        transition=ModeTransition.STOPPING_BASE,
    )
    assert e.requested_mode is ControlMode.DRIVE
    assert e.transition is ModeTransition.STOPPING_BASE


def test_gateway_state_event_defaults():
    e = GatewayStateEvent(
        gateway_monotonic_ns=0,
        state=GatewayState.IDLE,
        current_mode=ControlMode.HEAD_ONLY,
        session_id=None,
        sequence=None,
    )
    assert e.transition is ModeTransition.NONE
    assert e.requested_mode is None
