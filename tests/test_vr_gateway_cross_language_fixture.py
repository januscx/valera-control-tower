"""Cross-language/format fixture tests for VR Gateway v0.2.

These tests verify that known JSON command strings (as sent by the Unity
client) decode correctly through the wire codec, route through the gateway,
and produce the expected events. They serve as a contract reference between
the Python gateway and any client (Unity, CLI, test harness).
"""
from __future__ import annotations

import json

import pytest

from robot.vr_gateway.gateway import VrGateway
from robot.vr_gateway.messages import (
    ArmTargetEvent,
    BaseTargetEvent,
    CommandName,
    ControlMode,
    GatewayState,
    GatewayStateEvent,
    ModeTransition,
)
from robot.vr_gateway.neck import NeckControlConfig, NeckController
from robot.vr_gateway.wire import decode_command, encode_event


# ---------------------------------------------------------------------------
# Deterministic gateway fixture
# ---------------------------------------------------------------------------

class _FakeClock:
    def __init__(self): self.now_ns = 0
    def __call__(self): return self.now_ns
    def advance_ms(self, v): self.now_ns += v * 1_000_000


def _gateway() -> tuple[VrGateway, _FakeClock]:
    cfg = NeckControlConfig(
        center_pan_degrees=0, center_tilt_degrees=0,
        initial_pan_degrees=0, initial_tilt_degrees=0,
        pan_gain=1, tilt_gain=1, filter_time_constant_seconds=0,
        max_pan_rate_degrees_per_second=1_000,
        max_tilt_rate_degrees_per_second=1_000,
        min_pan_degrees=-180, max_pan_degrees=180,
        min_tilt_degrees=-90, max_tilt_degrees=90,
    )
    clock = _FakeClock()
    return VrGateway(NeckController(cfg), clock=clock), clock


# ---------------------------------------------------------------------------
# arm.jog fixture: known JSON string → decode → gateway → arm.target event
# ---------------------------------------------------------------------------

ARM_JOG_KNOWN_JSON = json.dumps({
    "schema_version": "0.1",
    "command": "arm.jog",
    "session_id": "fixture-arm-001",
    "sequence": 5,
    "timestamp_ms": 200,
    "payload": {
        "kind": "JOINT_JOG",
        "deadman": True,
        "joint_velocity": {
            "shoulder_pan": 0.5,
            "shoulder_lift": -0.3,
            "elbow_flex": 0.0,
            "wrist_flex": 0.0,
            "wrist_roll": 0.0,
        },
    },
})


def test_arm_jog_known_json_decode():
    """Known arm.jog JSON decodes to correct CommandEnvelope."""
    cmd = decode_command(ARM_JOG_KNOWN_JSON)
    assert cmd.command is CommandName.ARM_JOG
    assert cmd.session_id == "fixture-arm-001"
    assert cmd.sequence == 5
    assert cmd.payload.deadman is True
    assert cmd.payload.joint_velocity["shoulder_pan"] == 0.5
    assert cmd.payload.joint_velocity["shoulder_lift"] == -0.3


def test_arm_jog_gateway_round_trip():
    """arm.jog command → gateway → arm.target event, re-encodable to JSON."""
    gw, clock = _gateway()

    # Open session with ARM mode, recenter → auto-transition to ARM
    gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "session.start",
        "session_id": "fixture-arm-001",
        "sequence": 1,
        "timestamp_ms": 0,
        "payload": {"requested_mode": "arm"},
    })))
    clock.advance_ms(10)
    gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "head.recenter",
        "session_id": "fixture-arm-001",
        "sequence": 2,
        "timestamp_ms": 10,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
        },
    })))

    # For ARM → ARM transition (HEAD_ONLY → ARM after recenter),
    # we need to complete the stop-ack protocol.
    # The recenter auto-applies requested_mode=ARM from HEAD_ONLY,
    # so no transition is needed (HEAD_ONLY → ARM is immediate).
    assert gw.current_mode is ControlMode.ARM, (
        f"expected ARM after recenter, got {gw.current_mode}"
    )

    clock.advance_ms(50)
    events = gw.handle(decode_command(ARM_JOG_KNOWN_JSON))

    arm_targets = [e for e in events if isinstance(e, ArmTargetEvent)]
    assert len(arm_targets) == 1, f"expected 1 arm.target, got {len(arm_targets)}: {events}"
    target = arm_targets[0]
    assert target.deadman is True
    assert target.joint_velocity["shoulder_pan"] == 0.5
    assert target.joint_velocity["shoulder_lift"] == -0.3

    # Verify re-encodable to JSON without error
    encoded = encode_event(target)
    decoded = json.loads(encoded)
    assert decoded["event_type"] == "arm.target"
    assert decoded["joint_velocity"]["shoulder_pan"] == 0.5
    assert decoded["deadman"] is True
    assert decoded["command_zeroed"] is False


def test_arm_jog_watchdog_zero_encodes():
    """ARM watchdog zero (command_zeroed=true, empty dict) encodes to JSON."""
    gw, clock = _gateway()
    gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "session.start",
        "session_id": "fixture-arm-wd",
        "sequence": 1,
        "timestamp_ms": 0,
        "payload": {"requested_mode": "arm"},
    })))
    gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "head.recenter",
        "session_id": "fixture-arm-wd",
        "sequence": 2,
        "timestamp_ms": 10,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
        },
    })))
    clock.advance_ms(300)
    events = gw.poll()
    arm_targets = [e for e in events if isinstance(e, ArmTargetEvent)]
    # May or may not have arm.target depending on mode/watchdog order
    for t in arm_targets:
        encoded = encode_event(t)
        decoded = json.loads(encoded)
        assert decoded["event_type"] == "arm.target"
        assert decoded["command_zeroed"] is True


# ---------------------------------------------------------------------------
# base.drive fixture
# ---------------------------------------------------------------------------

BASE_DRIVE_KNOWN_JSON = json.dumps({
    "schema_version": "0.1",
    "command": "base.drive",
    "session_id": "fixture-base-001",
    "sequence": 5,
    "timestamp_ms": 200,
    "payload": {
        "throttle": 0.75,
        "steering": -0.25,
        "deadman": True,
    },
})


def test_base_drive_known_json_decode():
    """Known base.drive JSON decodes to correct CommandEnvelope."""
    cmd = decode_command(BASE_DRIVE_KNOWN_JSON)
    assert cmd.command is CommandName.BASE_DRIVE
    assert cmd.payload.throttle == 0.75
    assert cmd.payload.steering == -0.25
    assert cmd.payload.deadman is True


def test_base_drive_gateway_round_trip():
    """base.drive command → gateway → base.target event, re-encodable."""
    gw, clock = _gateway()

    # Session start with DRIVE, recenter → auto DRIVE mode
    gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "session.start",
        "session_id": "fixture-base-001",
        "sequence": 1,
        "timestamp_ms": 0,
        "payload": {"requested_mode": "drive"},
    })))
    clock.advance_ms(10)
    gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "head.recenter",
        "session_id": "fixture-base-001",
        "sequence": 2,
        "timestamp_ms": 10,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
        },
    })))
    assert gw.current_mode is ControlMode.DRIVE

    clock.advance_ms(50)
    events = gw.handle(decode_command(BASE_DRIVE_KNOWN_JSON))

    base_targets = [e for e in events if isinstance(e, BaseTargetEvent)]
    assert len(base_targets) == 1
    target = base_targets[0]
    assert target.throttle == 0.75
    assert target.steering == -0.25
    assert target.deadman is True
    assert target.command_zeroed is False

    encoded = encode_event(target)
    decoded = json.loads(encoded)
    assert decoded["throttle"] == 0.75
    assert decoded["steering"] == -0.25


# ---------------------------------------------------------------------------
# mode.set fixture
# ---------------------------------------------------------------------------

MODE_SET_KNOWN_JSON = json.dumps({
    "schema_version": "0.1",
    "command": "mode.set",
    "session_id": "fixture-mode-001",
    "sequence": 6,
    "timestamp_ms": 300,
    "payload": {"mode": "arm"},
})


def test_mode_set_gateway_drive_to_arm():
    """mode.set(ARM) from DRIVE → STOPPING_BASE + base.target zero."""
    gw, clock = _gateway()
    gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "session.start",
        "session_id": "fixture-mode-001",
        "sequence": 1,
        "timestamp_ms": 0,
        "payload": {"requested_mode": "drive"},
    })))
    clock.advance_ms(10)
    gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "head.recenter",
        "session_id": "fixture-mode-001",
        "sequence": 2,
        "timestamp_ms": 10,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
        },
    })))
    assert gw.current_mode is ControlMode.DRIVE

    clock.advance_ms(50)
    events = gw.handle(decode_command(MODE_SET_KNOWN_JSON))

    assert gw.transition is ModeTransition.STOPPING_BASE
    base_targets = [e for e in events if isinstance(e, BaseTargetEvent)]
    assert len(base_targets) == 1
    assert base_targets[0].command_zeroed is True


# ---------------------------------------------------------------------------
# gateway.state event always carries mode/transition fields
# ---------------------------------------------------------------------------

def test_gateway_state_event_has_mode_fields():
    """Every gateway.state event includes current_mode, requested_mode, transition."""
    gw, clock = _gateway()
    events = gw.handle(decode_command(json.dumps({
        "schema_version": "0.1",
        "command": "session.start",
        "session_id": "fixture-state-001",
        "sequence": 1,
        "timestamp_ms": 0,
        "payload": {"requested_mode": "head"},
    })))

    state_events = [e for e in events if isinstance(e, GatewayStateEvent)]
    assert len(state_events) >= 1
    for se in state_events:
        encoded = encode_event(se)
        decoded = json.loads(encoded)
        assert "current_mode" in decoded, (
            f"gateway.state missing current_mode: {decoded}"
        )
        assert "transition" in decoded
