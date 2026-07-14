import json
import math
from pathlib import Path

import pytest

from robot.vr_gateway import wire
from robot.vr_gateway.adapter import VrGatewayAdapter
from robot.vr_gateway.gateway import VrGateway
from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    EmptyPayload,
    EventName,
    GatewayState,
    GatewayStateEvent,
    ModeSetPayload,
    NeckTargetEvent,
    PosePayload,
    Position,
    Quaternion,
    RejectionCode,
    SafetyStopEvent,
    SessionStartPayload,
    StopReason,
)
from robot.vr_gateway.neck import NeckControlConfig, NeckController


def _neck() -> NeckController:
    return NeckController(
        NeckControlConfig(
            center_pan_degrees=0.0,
            center_tilt_degrees=0.0,
            initial_pan_degrees=0.0,
            initial_tilt_degrees=0.0,
            pan_gain=1.0,
            tilt_gain=1.0,
            filter_time_constant_seconds=0.0,
            max_pan_rate_degrees_per_second=1_000.0,
            max_tilt_rate_degrees_per_second=1_000.0,
            min_pan_degrees=-180.0,
            max_pan_degrees=180.0,
            min_tilt_degrees=-90.0,
            max_tilt_degrees=90.0,
        )
    )


class FakeClock:
    def __init__(self) -> None:
        self.now_ns = 0

    def __call__(self) -> int:
        return self.now_ns

    def advance_ms(self, value: int) -> None:
        self.now_ns += value * 1_000_000


def _gateway() -> tuple[VrGateway, FakeClock]:
    clock = FakeClock()
    return VrGateway(_neck(), clock=clock), clock


def _adapter() -> tuple[VrGatewayAdapter, VrGateway, FakeClock]:
    gateway, clock = _gateway()
    return VrGatewayAdapter(gateway), gateway, clock


# Canonical Unity-compatible JSON fixtures, shaped exactly like the v0.1 wire
# contract the Unity client emits.
SESSION_START_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "session.start",
        "session_id": "unity-head-001",
        "sequence": 1,
        "timestamp_ms": 0,
        "payload": {"requested_mode": "head"},
    }
)
SESSION_STOP_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "session.stop",
        "session_id": "unity-head-001",
        "sequence": 4,
        "timestamp_ms": 3,
        "payload": {},
    }
)
MODE_SET_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "mode.set",
        "session_id": "unity-head-001",
        "sequence": 4,
        "timestamp_ms": 3,
        "payload": {"mode": "head"},
    }
)
HEAD_POSE_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "head.pose",
        "session_id": "unity-head-001",
        "sequence": 3,
        "timestamp_ms": 2,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0.0, "y": 0.1, "z": 0.0, "w": 1.0},
            "position": {"x": 0.0, "y": 1.5, "z": -2.0},
        },
    }
)
HEAD_POSE_NO_POSITION_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "head.pose",
        "session_id": "unity-head-001",
        "sequence": 3,
        "timestamp_ms": 2,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0.0, "y": 0.1, "z": 0.0, "w": 1.0},
        },
    }
)
HEAD_POSE_NULL_POSITION_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "head.pose",
        "session_id": "unity-head-001",
        "sequence": 3,
        "timestamp_ms": 2,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0.0, "y": 0.1, "z": 0.0, "w": 1.0},
            "position": None,
        },
    }
)
HEAD_RECENTER_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "head.recenter",
        "session_id": "unity-head-001",
        "sequence": 2,
        "timestamp_ms": 1,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }
)
EMERGENCY_STOP_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "emergency_stop",
        "session_id": "operator-stop",
        "sequence": 99,
        "timestamp_ms": 50,
        "payload": {},
    }
)


def _round_trip_envelope(raw: str) -> CommandEnvelope:
    return wire.decode_command(raw)


def test_decodes_all_six_command_wire_shapes():
    command = _round_trip_envelope(SESSION_START_JSON)
    assert command.command is CommandName.SESSION_START
    assert isinstance(command.payload, SessionStartPayload)
    assert command.payload.requested_mode == "head"

    command = _round_trip_envelope(SESSION_STOP_JSON)
    assert command.command is CommandName.SESSION_STOP
    assert isinstance(command.payload, EmptyPayload)

    command = _round_trip_envelope(MODE_SET_JSON)
    assert command.command is CommandName.MODE_SET
    assert isinstance(command.payload, ModeSetPayload)
    assert command.payload.mode == "head"

    command = _round_trip_envelope(HEAD_POSE_JSON)
    assert command.command is CommandName.HEAD_POSE
    assert isinstance(command.payload, PosePayload)
    assert command.payload.frame == "quest_local"
    assert command.payload.orientation == Quaternion(0.0, 0.1, 0.0, 1.0)
    assert command.payload.position == Position(0.0, 1.5, -2.0)

    command = _round_trip_envelope(HEAD_RECENTER_JSON)
    assert command.command is CommandName.HEAD_RECENTER
    assert isinstance(command.payload, PosePayload)
    assert command.payload.position is None

    command = _round_trip_envelope(EMERGENCY_STOP_JSON)
    assert command.command is CommandName.EMERGENCY_STOP
    assert isinstance(command.payload, EmptyPayload)


def test_head_pose_optional_position_round_trips_when_absent_or_null():
    absent = _round_trip_envelope(HEAD_POSE_NO_POSITION_JSON).payload
    null = _round_trip_envelope(HEAD_POSE_NULL_POSITION_JSON).payload
    assert isinstance(absent, PosePayload) and absent.position is None
    assert isinstance(null, PosePayload) and null.position is None


def test_decode_rejects_duplicate_keys():
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"s","sequence":1,"timestamp_ms":0,'
        '"payload":{"requested_mode":"head","requested_mode":"arm"}}'
    )
    with pytest.raises(wire.WireError, match="duplicate"):
        wire.decode_command(raw)


def test_decode_rejects_nan_and_infinity_literals():
    raw = (
        '{"schema_version":"0.1","command":"head.pose",'
        '"session_id":"s","sequence":3,"timestamp_ms":2,'
        '"payload":{"frame":"quest_local",'
        '"orientation":{"x":NaN,"y":0.0,"z":0.0,"w":1.0}}}'
    )
    with pytest.raises(wire.WireError):
        wire.decode_command(raw)


def test_decode_rejects_trailing_data():
    raw = SESSION_START_JSON + " {}"
    with pytest.raises(wire.WireError, match="trailing"):
        wire.decode_command(raw)


@pytest.mark.parametrize(
    "override",
    [
        lambda d: d.update({"schema_version": "0.2"}),
        lambda d: d.pop("payload"),
        lambda d: d.update({"extra": 1}),
        lambda d: d.__setitem__("session_id", 1),
        lambda d: d.__setitem__("session_id", ""),
        lambda d: d.__setitem__("sequence", 0),
        lambda d: d.__setitem__("sequence", 1.0),
        lambda d: d.__setitem__("sequence", True),
        lambda d: d.__setitem__("timestamp_ms", -1),
        lambda d: d.__setitem__("timestamp_ms", 0.0),
        lambda d: d.__setitem__("command", "teleport"),
        lambda d: d.__setitem__("payload", "head"),
    ],
)
def test_decode_rejects_envelope_field_violations(override):
    document = json.loads(SESSION_START_JSON)
    override(document)
    raw = json.dumps(document)
    with pytest.raises(wire.WireError):
        wire.decode_command(raw)


def test_decode_rejects_unknown_command_discriminator():
    document = json.loads(SESSION_START_JSON)
    document["command"] = "session.teleport"
    raw = json.dumps(document)
    with pytest.raises(wire.WireError, match="discriminator"):
        wire.decode_command(raw)


@pytest.mark.parametrize(
    "payload",
    [
        {"requested_mode": ""},
        {"requested_mode": 1},
        {"requested_mode": "head", "extra": 1},
        {},
    ],
)
def test_decode_rejects_session_start_payload_violations(payload):
    document = json.loads(SESSION_START_JSON)
    document["payload"] = payload
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))


@pytest.mark.parametrize(
    "payload",
    [
        {"frame": "unity_world", "orientation": {"x": 0, "y": 0, "z": 0, "w": 1}},
        {"orientation": {"x": 0, "y": 0, "z": 0, "w": 1}},
        {"frame": "quest_local", "orientation": {"x": 0, "y": 0, "z": 0, "w": 1, "q": 0}},
        {"frame": "quest_local", "orientation": {"x": 0, "y": 0, "z": 0}},
        {"frame": "quest_local", "orientation": "identity"},
        {"frame": "quest_local", "orientation": {"x": 0, "y": 0, "z": 0, "w": 1}, "position": 5},
        {"frame": "quest_local", "orientation": {"x": 0, "y": 0, "z": 0, "w": 1}, "position": {}},
    ],
)
def test_decode_rejects_pose_payload_violations(payload):
    document = json.loads(HEAD_POSE_JSON)
    document["payload"] = payload
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))


def test_decode_rejects_non_empty_stop_and_estop_payloads():
    stop = json.loads(SESSION_STOP_JSON)
    stop["payload"] = {"unexpected": 1}
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(stop))

    estop = json.loads(EMERGENCY_STOP_JSON)
    estop["payload"] = {"unexpected": 1}
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(estop))


def test_decode_rejects_non_object_envelope_and_non_string_input():
    with pytest.raises(wire.WireError):
        wire.decode_command("[]")
    with pytest.raises(wire.WireError):
        wire.decode_command("not json")
    with pytest.raises(wire.WireError):
        wire.decode_command(b"raw bytes")  # type: ignore[arg-type]


def test_encode_event_serializes_all_four_event_types_with_exact_keys():
    from robot.vr_gateway.messages import CommandRejectedEvent

    state_event = GatewayStateEvent(11, GatewayState.HEAD_ACTIVE, "s-1", 2)
    neck_event = NeckTargetEvent(22, "s-1", 3, 1.25, -2.5)
    stop_event = SafetyStopEvent(33, StopReason.WATCHDOG, "s-1", 4)
    rejected_event = CommandRejectedEvent(
        44, RejectionCode.INVALID_PAYLOAD, "invalid", None, None
    )

    state_doc = json.loads(wire.encode_event(state_event))
    assert state_doc == {
        "gateway_monotonic_ns": 11,
        "state": "HEAD_ACTIVE",
        "session_id": "s-1",
        "sequence": 2,
        "schema_version": "0.1",
        "event_type": EventName.GATEWAY_STATE.value,
    }
    neck_doc = json.loads(wire.encode_event(neck_event))
    assert neck_doc == {
        "gateway_monotonic_ns": 22,
        "session_id": "s-1",
        "sequence": 3,
        "pan_degrees": 1.25,
        "tilt_degrees": -2.5,
        "hold": False,
        "schema_version": "0.1",
        "event_type": EventName.NECK_TARGET.value,
    }
    stop_doc = json.loads(wire.encode_event(stop_event))
    assert stop_doc == {
        "gateway_monotonic_ns": 33,
        "reason": "WATCHDOG",
        "session_id": "s-1",
        "sequence": 4,
        "neck_action": "HOLD_LAST_POSITION",
        "base_action": "STOP",
        "arm_action": "HOLD",
        "schema_version": "0.1",
        "event_type": EventName.SAFETY_STOP.value,
    }
    rejected_doc = json.loads(wire.encode_event(rejected_event))
    assert rejected_doc == {
        "gateway_monotonic_ns": 44,
        "code": "INVALID_PAYLOAD",
        "message": "invalid",
        "session_id": None,
        "sequence": None,
        "schema_version": "0.1",
        "event_type": EventName.COMMAND_REJECTED.value,
    }


def test_encode_event_serializes_nullable_event_correlation_as_null():
    event = GatewayStateEvent(5, GatewayState.IDLE, None, None)
    doc = json.loads(wire.encode_event(event))
    assert doc["session_id"] is None
    assert doc["sequence"] is None
    assert "session_id" in doc and "sequence" in doc


def test_adapter_malformed_json_routes_through_gateway_fail_closed():
    adapter, gateway, _ = _adapter()

    events_json = adapter.handle_command("{not valid json")

    assert len(events_json) == 1
    document = json.loads(events_json[0])
    assert document["event_type"] == EventName.COMMAND_REJECTED.value
    assert document["code"] == RejectionCode.INVALID_PAYLOAD.value
    assert document["session_id"] is None
    assert document["sequence"] is None
    assert gateway.state is GatewayState.IDLE


def test_adapter_malformed_json_does_not_synthesize_safety_stop():
    adapter, _, _ = _adapter()

    events_json = adapter.handle_command("null")

    assert len(events_json) == 1
    document = json.loads(events_json[0])
    assert document["event_type"] == EventName.COMMAND_REJECTED.value
    assert document["code"] == RejectionCode.INVALID_PAYLOAD.value


def test_adapter_accepts_valid_stream_and_returns_encoded_events_in_order():
    adapter, gateway, _ = _adapter()

    start_events = adapter.handle_command(SESSION_START_JSON)
    recenter_events = adapter.handle_command(HEAD_RECENTER_JSON)
    pose_events = adapter.handle_command(HEAD_POSE_JSON)

    assert [json.loads(e)["event_type"] for e in start_events] == ["gateway.state"]
    assert json.loads(start_events[0])["state"] == "AWAITING_RECENTER"
    assert [json.loads(e)["event_type"] for e in recenter_events] == ["gateway.state"]
    assert json.loads(recenter_events[0])["state"] == "HEAD_ACTIVE"
    assert [json.loads(e)["event_type"] for e in pose_events] == ["neck.target"]
    assert gateway.state is GatewayState.HEAD_ACTIVE


def test_adapter_preserves_order_of_multiple_events_from_session_stop():
    adapter, gateway, _ = _adapter()
    adapter.handle_command(SESSION_START_JSON)
    adapter.handle_command(HEAD_RECENTER_JSON)

    events_json = adapter.handle_command(SESSION_STOP_JSON)
    documents = [json.loads(e) for e in events_json]

    assert [d["event_type"] for d in documents] == [
        EventName.GATEWAY_STATE.value,
        EventName.SAFETY_STOP.value,
    ]
    assert documents[0]["state"] == "IDLE"
    assert documents[1]["reason"] == "SESSION_STOPPED"


def test_adapter_handshake_timeout_via_poll_returns_state_event_only():
    adapter, gateway, clock = _adapter()
    adapter.handle_command(SESSION_START_JSON)
    assert gateway.poll() == ()
    clock.advance_ms(10_000)

    events_json = adapter.poll()

    documents = [json.loads(e) for e in events_json]
    assert [d["event_type"] for d in documents] == [EventName.GATEWAY_STATE.value]
    assert documents[0]["state"] == "IDLE"
    assert not any(d["event_type"] == EventName.SAFETY_STOP.value for d in documents)


def test_adapter_watchdog_stop_via_poll_returns_state_then_safety_stop():
    adapter, gateway, clock = _adapter()
    adapter.handle_command(SESSION_START_JSON)
    adapter.handle_command(HEAD_RECENTER_JSON)
    adapter.handle_command(HEAD_POSE_JSON)
    clock.advance_ms(250)

    events_json = adapter.poll()

    documents = [json.loads(e) for e in events_json]
    assert [d["event_type"] for d in documents] == [
        EventName.GATEWAY_STATE.value,
        EventName.SAFETY_STOP.value,
    ]
    assert documents[0]["state"] == "SAFE_STOPPED"
    assert documents[1]["reason"] == "WATCHDOG"


def test_adapter_poll_emits_nothing_when_no_deadline():
    adapter, _, _ = _adapter()

    assert adapter.poll() == []


def test_core_codec_has_no_ros_or_hardware_imports():
    package_dir = Path(__file__).resolve().parents[1] / "robot" / "vr_gateway"
    forbidden_substrings = (
        "rclpy",
        "roslibpy",
        "std_msgs",
        "serial",
        "lerobot",
        "websockets",
        "socket",
        "cv2",
        "numpy",
        "rcl_interfaces",
        "geometry_msgs",
    )
    offenders: list[str] = []
    for source in ("wire.py", "adapter.py"):
        text = (package_dir / source).read_text(encoding="utf-8")
        for token in forbidden_substrings:
            if token in text:
                offenders.append(f"{source}:{token}")
    assert offenders == [], offenders


def test_core_codec_only_imports_allowlisted_roots():
    import ast

    allowed_roots = {
        "__future__",
        "dataclasses",
        "enum",
        "json",
        "math",
        "robot",
        "typing",
    }
    package_dir = Path(__file__).resolve().parents[1] / "robot" / "vr_gateway"
    found: set[str] = set()
    for source in ("wire.py", "adapter.py"):
        tree = ast.parse((package_dir / source).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    found.add("<relative-import>")
                else:
                    found.add(node.module.split(".", 1)[0])
    assert found <= allowed_roots, found - allowed_roots