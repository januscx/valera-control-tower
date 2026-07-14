import math

import pytest

from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    MessageValidationError,
    ModeSetPayload,
    PosePayload,
    Quaternion,
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
