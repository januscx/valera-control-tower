import math

import pytest

from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    CommandRejectedEvent,
    EmptyPayload,
    EventName,
    GatewayState,
    GatewayStateEvent,
    MessageValidationError,
    ModeSetPayload,
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
        "head.recenter", "emergency_stop",
    }
    assert {item.value for item in GatewayState} == {
        "IDLE", "AWAITING_RECENTER", "HEAD_ACTIVE", "SAFE_STOPPED",
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
    }


def test_output_event_names_and_safe_action_defaults():
    events = (
        GatewayStateEvent(1, GatewayState.IDLE, None, None),
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
    assert [event.event_type for event in events] == list(EventName)
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
