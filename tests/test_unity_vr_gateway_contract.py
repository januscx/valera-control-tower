import json

import pytest

from robot.vr_gateway.gateway import VrGateway
from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    EmptyPayload,
    ModeSetPayload,
    PosePayload,
    Quaternion,
    RejectionCode,
    SessionStartPayload,
)
from robot.vr_gateway.neck import NeckControlConfig, NeckController


def _build_gateway(clock=0):
    return VrGateway(
        NeckController(
            NeckControlConfig(0, 0, 0, 0, 1, 1, 0, 10, 10, -10, 10, -10, 10)
        ),
        clock=lambda: clock,
    )


def _start_session(gateway, session_id="unity-session"):
    return gateway.handle(
        CommandEnvelope(
            "0.1",
            CommandName.SESSION_START,
            session_id,
            1,
            0,
            SessionStartPayload("head"),
        )
    )


def test_unknown_unity_mode_is_rejected_by_the_python_gateway():
    gateway = _build_gateway()
    _start_session(gateway)

    events = gateway.handle(
        CommandEnvelope(
            "0.1", CommandName.MODE_SET, "unity-session", 2, 1, ModeSetPayload("inspection")
        )
    )

    assert len(events) == 1
    assert events[0].code is RejectionCode.UNKNOWN_MODE


@pytest.mark.parametrize("mode", ["drive", "arm"])
def test_blocked_unity_modes_are_rejected_by_the_python_gateway(mode):
    gateway = _build_gateway()
    _start_session(gateway)

    events = gateway.handle(
        CommandEnvelope(
            "0.1", CommandName.MODE_SET, "unity-session", 2, 1, ModeSetPayload(mode)
        )
    )

    assert len(events) == 1
    assert events[0].code is RejectionCode.MODE_BLOCKED


def test_session_start_rejects_drive_and_arm_requested_modes():
    gateway = _build_gateway()

    drive_events = gateway.handle(
        CommandEnvelope(
            "0.1", CommandName.SESSION_START, "session-a", 1, 0, SessionStartPayload("drive")
        )
    )
    arm_events = gateway.handle(
        CommandEnvelope(
            "0.1", CommandName.SESSION_START, "session-b", 1, 0, SessionStartPayload("arm")
        )
    )

    assert drive_events[0].code is RejectionCode.MODE_BLOCKED
    assert arm_events[0].code is RejectionCode.MODE_BLOCKED


def test_head_pose_without_position_is_accepted_by_the_python_gateway():
    gateway = _build_gateway()
    _start_session(gateway)
    gateway.handle(
        CommandEnvelope(
            "0.1",
            CommandName.HEAD_RECENTER,
            "unity-session",
            2,
            1,
            PosePayload("quest_local", Quaternion(0.0, 0.0, 0.0, 1.0)),
        )
    )

    events = gateway.handle(
        CommandEnvelope(
            "0.1",
            CommandName.HEAD_POSE,
            "unity-session",
            3,
            2,
            PosePayload("quest_local", Quaternion(0.0, 0.1, 0.0, 1.0)),
        )
    )

    assert len(events) == 1
    assert events[0].event_type.value == "neck.target"


def test_malformed_command_payload_fails_closed_in_python_gateway():
    gateway = _build_gateway()
    _start_session(gateway)

    events = gateway.handle(
        CommandEnvelope(
            "0.1",
            CommandName.HEAD_POSE,
            "unity-session",
            2,
            1,
            EmptyPayload(),
        )
    )

    assert len(events) == 1
    assert events[0].code is RejectionCode.INVALID_PAYLOAD


def test_python_event_correlation_serializes_as_null_when_unavailable():
    from robot.vr_gateway.messages import ControlMode, GatewayState, GatewayStateEvent

    event = GatewayStateEvent(1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None)
    serialized = json.loads(json.dumps({k: v for k, v in event.__dict__.items()}))

    assert serialized["session_id"] is None
    assert serialized["sequence"] is None
    assert "session_id" in serialized
    assert "sequence" in serialized


def test_python_event_correlation_serializes_values_when_available():
    from robot.vr_gateway.messages import ControlMode, GatewayState, GatewayStateEvent

    event = GatewayStateEvent(1, GatewayState.ACTIVE, ControlMode.HEAD_ONLY, "s-1", 2)
    serialized = json.loads(json.dumps({k: v for k, v in event.__dict__.items()}))

    assert serialized["session_id"] == "s-1"
    assert serialized["sequence"] == 2


def test_python_neck_target_always_emits_correlation():
    gateway = _build_gateway()
    _start_session(gateway)
    gateway.handle(
        CommandEnvelope(
            "0.1",
            CommandName.HEAD_RECENTER,
            "unity-session",
            2,
            1,
            PosePayload("quest_local", Quaternion(0.0, 0.0, 0.0, 1.0)),
        )
    )

    events = gateway.handle(
        CommandEnvelope(
            "0.1",
            CommandName.HEAD_POSE,
            "unity-session",
            3,
            2,
            PosePayload("quest_local", Quaternion(0.0, 0.1, 0.0, 1.0)),
        )
    )

    target = events[0]
    assert target.session_id is not None
    assert target.sequence is not None
    assert target.session_id == "unity-session"
    assert target.sequence == 3


def test_unity_codec_does_not_duplicate_session_safety_decisions():
    """Unity accepts and transports any valid non-empty mode string; the Python
    gateway alone decides whether the mode is allowed, blocked, or unknown.
    """
    from robot.vr_gateway.messages import ModeSetPayload

    assert ModeSetPayload("inspection").mode == "inspection"
    assert ModeSetPayload("drive").mode == "drive"
    assert ModeSetPayload("arm").mode == "arm"
