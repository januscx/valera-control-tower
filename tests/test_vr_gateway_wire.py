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
    CommandRejectedEvent,
    ControlMode,
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

    state_event = GatewayStateEvent(11, GatewayState.ACTIVE, ControlMode.HEAD_ONLY, "s-1", 2)
    neck_event = NeckTargetEvent(22, "s-1", 3, 1.25, -2.5)
    stop_event = SafetyStopEvent(33, StopReason.WATCHDOG, "s-1", 4)
    rejected_event = CommandRejectedEvent(
        44, RejectionCode.INVALID_PAYLOAD, "invalid", None, None
    )

    state_doc = json.loads(wire.encode_event(state_event))
    assert state_doc == {
        "gateway_monotonic_ns": 11,
        "state": "ACTIVE",
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
    event = GatewayStateEvent(5, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None)
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
    assert json.loads(recenter_events[0])["state"] == "ACTIVE"
    assert [json.loads(e)["event_type"] for e in pose_events] == ["neck.target"]
    assert gateway.state is GatewayState.ACTIVE


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
    import re

    package_dir = Path(__file__).resolve().parents[1] / "robot" / "vr_gateway"
    forbidden_identifiers = (
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
        for token in forbidden_identifiers:
            pattern = rf"\b{re.escape(token)}\b"
            if re.search(pattern, text):
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


# --- Unicode surrogate handling ---


def test_decode_accepts_valid_surrogate_pair():
    # \uD83E\uDD16 -> 🤖
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"\\uD83E\\uDD16","sequence":1,"timestamp_ms":0,'
        '"payload":{"requested_mode":"head"}}'
    )
    command = wire.decode_command(raw)
    assert command.session_id == "🤖"


def test_decode_accepts_raw_non_bmp_character_within_size_limits():
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"🤖","sequence":1,"timestamp_ms":0,'
        '"payload":{"requested_mode":"head"}}'
    )
    command = wire.decode_command(raw)
    assert command.session_id == "🤖"


@pytest.mark.parametrize(
    "bad_string",
    [
        "\\uD800",  # lone high surrogate
        "\\uDC00",  # lone low surrogate
        "\\uD83E\\u0041",  # high surrogate followed by normal char
        "\\uD83E\\uD83E",  # high/high
        "\\uDD16\\uDD16",  # low/low
    ],
)
def test_decode_rejects_lone_and_malformed_surrogates_in_values(bad_string):
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        f'"session_id":"{bad_string}","sequence":1,"timestamp_ms":0,'
        '"payload":{"requested_mode":"head"}}'
    )
    with pytest.raises(wire.WireError, match="surrogate"):
        wire.decode_command(raw)


def test_decode_rejects_malformed_surrogate_in_object_key():
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"s","sequence":1,"timestamp_ms":0,'
        '"payload":{"\\uD800requested_mode":"head"}}'
    )
    with pytest.raises(wire.WireError, match="surrogate"):
        wire.decode_command(raw)


def test_decode_rejects_malformed_surrogate_in_nested_list():
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"s","sequence":1,"timestamp_ms":0,'
        '"payload":{"requested_mode":"head","extra":["\\uD800"]}}'
    )
    with pytest.raises(wire.WireError, match="surrogate"):
        wire.decode_command(raw)


# --- JSON depth scanner ---


def _build_nested_json(extra_depth: int, kind: str = "object") -> str:
    """Build raw JSON whose total nesting depth is 3 + ``extra_depth``.

    The fixed envelope contributes 3 levels (envelope, payload, extra field).
    ``extra_depth`` is the number of additional nested objects/arrays inside
    the extra field, so the total depth is exactly ``3 + extra_depth``.
    """
    if kind == "object":
        inner = '"x"'
        for _ in range(extra_depth):
            inner = '{"a":' + inner + '}'
    else:
        inner = "1"
        for _ in range(extra_depth):
            inner = "[" + inner + "]"
    return (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"depth","sequence":1,"timestamp_ms":0,'
        f'"payload":{{"requested_mode":"head","extra":{inner}}}}}'
    )


def test_decode_accepts_nesting_depth_of_16():
    # 3 fixed levels + 13 nested objects = total depth 16.
    raw = _build_nested_json(13)
    # Depth is fine; the extra field in payload is rejected later.
    with pytest.raises(wire.WireError, match="requested_mode"):
        wire.decode_command(raw)


def test_decode_rejects_nesting_depth_of_17():
    raw = _build_nested_json(14)
    with pytest.raises(wire.WireError, match="depth"):
        wire.decode_command(raw)


def test_decode_rejects_deeply_nested_arrays_without_recursion_error():
    raw = _build_nested_json(997, kind="array")
    with pytest.raises(wire.WireError, match="depth"):
        wire.decode_command(raw)


def test_decode_depth_scanner_ignores_brackets_inside_strings():
    # Brackets are embedded inside JSON strings; the depth scanner must ignore
    # them. A valid mode.set with a bracket-containing mode string is used.
    raw = (
        '{"schema_version":"0.1","command":"mode.set",'
        '"session_id":"s","sequence":2,"timestamp_ms":1,'
        '"payload":{"mode":"{[[]]}[[["}}'
    )
    command = wire.decode_command(raw)
    assert command.payload.mode == "{[[]]}[[["


def test_decode_depth_scanner_handles_escaped_quotes_inside_strings():
    # The JSON string value contains an escaped quote: mode\".
    # Use mode.set so the bracket-free value is accepted by the wire codec.
    raw = (
        '{"schema_version":"0.1","command":"mode.set",'
        '"session_id":"s","sequence":2,"timestamp_ms":1,'
        '"payload":{"mode":"head\\""}}'
    )
    command = wire.decode_command(raw)
    assert command.payload.mode == 'head"'


def test_decode_rejects_unbalanced_brackets_in_depth_scanner():
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"s","sequence":1,"timestamp_ms":0,'
        '"payload":"}}"}'
    )
    with pytest.raises(wire.WireError, match="brackets|JSON"):
        wire.decode_command(raw)


# --- Exact enum types and whitespace strings ---


def test_encode_event_rejects_plain_string_for_state_enum():
    event = _mutated_event(
        GatewayStateEvent(1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None), state="IDLE"
    )
    with pytest.raises(wire.WireError, match="GatewayState"):
        wire.encode_event(event)


def test_encode_event_rejects_plain_string_for_stop_reason_enum():
    event = _mutated_event(
        SafetyStopEvent(1, StopReason.WATCHDOG, "s-1", 1), reason="WATCHDOG"
    )
    with pytest.raises(wire.WireError, match="StopReason"):
        wire.encode_event(event)


def test_encode_event_rejects_plain_string_for_rejection_code_enum():
    event = _mutated_event(
        CommandRejectedEvent(1, RejectionCode.INVALID_PAYLOAD, "msg", None, None),
        code="INVALID_PAYLOAD",
    )
    with pytest.raises(wire.WireError, match="RejectionCode"):
        wire.encode_event(event)


def test_encode_event_rejects_plain_string_for_event_type_enum():
    event = _mutated_event(
        GatewayStateEvent(1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None),
        event_type="gateway.state",
    )
    with pytest.raises(wire.WireError, match="event_type"):
        wire.encode_event(event)


@pytest.mark.parametrize("message", ["", "   ", "\t", "\n"])
def test_encode_event_rejects_whitespace_only_rejection_message(message):
    event = _mutated_event(
        CommandRejectedEvent(1, RejectionCode.INVALID_PAYLOAD, "msg", None, None),
        message=message,
    )
    with pytest.raises(wire.WireError, match="message"):
        wire.encode_event(event)


@pytest.mark.parametrize("action", ["", "   ", "\t", "\n"])
def test_encode_event_rejects_whitespace_only_safety_action_strings(action):
    event = _mutated_event(
        SafetyStopEvent(1, StopReason.WATCHDOG, "s-1", 1),
        neck_action=action,
    )
    with pytest.raises(wire.WireError, match="neck_action"):
        wire.encode_event(event)


def test_decode_rejects_boolean_values_for_pose_numeric_fields():
    raw = (
        '{"schema_version":"0.1","command":"head.pose",'
        '"session_id":"s","sequence":3,"timestamp_ms":2,'
        '"payload":{"frame":"quest_local",'
        '"orientation":{"x":true,"y":0,"z":0,"w":1}}}'
    )
    with pytest.raises(wire.WireError, match="finite JSON numbers"):
        wire.decode_command(raw)


# --- Cross-contract fixtures matching Unity v0.1 ---


def _session_start(requested_mode="head", session_id="unity-head-001", sequence=1):
    return json.dumps(
        {
            "schema_version": "0.1",
            "command": "session.start",
            "session_id": session_id,
            "sequence": sequence,
            "timestamp_ms": 0,
            "payload": {"requested_mode": requested_mode},
        }
    )


def _mode_set(mode="head", session_id="unity-head-001", sequence=4):
    return json.dumps(
        {
            "schema_version": "0.1",
            "command": "mode.set",
            "session_id": session_id,
            "sequence": sequence,
            "timestamp_ms": 3,
            "payload": {"mode": mode},
        }
    )


def _head_pose(session_id="unity-head-001", sequence=3, position="present"):
    payload = {
        "frame": "quest_local",
        "orientation": {"x": 0.0, "y": 0.1, "z": 0.0, "w": 1.0},
    }
    if position == "present":
        payload["position"] = {"x": 0.0, "y": 1.5, "z": -2.0}
    elif position == "null":
        payload["position"] = None
    return json.dumps(
        {
            "schema_version": "0.1",
            "command": "head.pose",
            "session_id": session_id,
            "sequence": sequence,
            "timestamp_ms": 2,
            "payload": payload,
        }
    )


def _head_recenter(session_id="unity-head-001", sequence=2):
    return json.dumps(
        {
            "schema_version": "0.1",
            "command": "head.recenter",
            "session_id": session_id,
            "sequence": sequence,
            "timestamp_ms": 1,
            "payload": {
                "frame": "quest_local",
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
            },
        }
    )


def test_head_recenter_rejects_position_field():
    document = json.loads(_head_recenter())
    document["payload"]["position"] = {"x": 0.0, "y": 0.0, "z": 0.0}
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))


def test_head_recenter_rejects_null_position_field():
    document = json.loads(_head_recenter())
    document["payload"]["position"] = None
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))


def test_head_pose_accepts_absent_position():
    command = wire.decode_command(_head_pose(position="absent"))
    assert isinstance(command.payload, PosePayload)
    assert command.payload.position is None


def test_head_pose_accepts_null_position():
    command = wire.decode_command(_head_pose(position="null"))
    assert isinstance(command.payload, PosePayload)
    assert command.payload.position is None


@pytest.mark.parametrize(
    "requested_mode",
    ["HEAD", "head ", " head", "drive", "arm", "", "inspection", "head\0"],
)
def test_decode_rejects_session_start_requested_mode_other_than_head(requested_mode):
    with pytest.raises(wire.WireError):
        wire.decode_command(_session_start(requested_mode=requested_mode))


@pytest.mark.parametrize(
    "mode",
    ["", "   ", "\t", "\n", "a" * 65],
)
def test_decode_rejects_mode_set_invalid_mode_strings(mode):
    with pytest.raises(wire.WireError):
        wire.decode_command(_mode_set(mode=mode))


def test_decode_accepts_64_character_mode_string():
    mode = "a" * 64
    command = wire.decode_command(_mode_set(mode=mode))
    assert command.payload.mode == mode


@pytest.mark.parametrize("session_id", ["", "   ", "\t\n", " "])
def test_decode_rejects_whitespace_or_empty_session_id(session_id):
    with pytest.raises(wire.WireError):
        wire.decode_command(_session_start(session_id=session_id))


def test_decode_rejects_integer_above_int64_max():
    document = json.loads(_session_start())
    document["sequence"] = wire.MAX_INT64 + 1
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))

    document = json.loads(_session_start())
    document["timestamp_ms"] = wire.MAX_INT64 + 1
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))


def test_decode_rejects_fractional_integer_literals():
    document = json.loads(_session_start())
    document["sequence"] = 1.0
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))

    document = json.loads(_session_start())
    document["timestamp_ms"] = 0.5
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))


def test_decode_rejects_exponent_integer_literals():
    document = json.loads(_session_start())
    document["sequence"] = 1e3
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))


def test_decode_rejects_boolean_integer_fields():
    document = json.loads(_session_start())
    document["sequence"] = True
    with pytest.raises(wire.WireError):
        wire.decode_command(json.dumps(document))


def test_decode_accepts_int64_max_sequence_and_timestamp():
    document = json.loads(_session_start())
    document["sequence"] = wire.MAX_INT64
    document["timestamp_ms"] = wire.MAX_INT64
    command = wire.decode_command(json.dumps(document))
    assert command.sequence == wire.MAX_INT64
    assert command.timestamp_ms == wire.MAX_INT64


def test_decode_rejects_input_above_max_characters():
    raw = " " * (wire.MAX_INPUT_CHARACTERS + 1)
    with pytest.raises(wire.WireError, match="characters"):
        wire.decode_command(raw)


def test_decode_rejects_input_above_max_utf8_bytes():
    # 4-byte UTF-8 codepoints expand past the byte cap before the char cap.
    raw = "\U0001F600" * (wire.MAX_INPUT_UTF8_BYTES // 4 + 1)
    with pytest.raises(wire.WireError, match="UTF-8"):
        wire.decode_command(raw)


def test_decode_rejects_json_nesting_depth_above_16():
    # Build genuinely nested JSON objects by hand (no json.dumps escaping).
    # 17 levels of `{"a": ...}` nesting inside the payload's extra field.
    nested = '"x"'
    for _ in range(17):
        nested = '{"a":' + nested + '}'
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"depth","sequence":1,"timestamp_ms":0,'
        f'"payload":{{"requested_mode":"head","extra":{nested}}}}}'
    )
    with pytest.raises(wire.WireError, match="depth"):
        wire.decode_command(raw)


def test_decode_accepts_json_nesting_depth_at_16():
    # 16 levels of nesting should be accepted by the depth check.
    nested = '"x"'
    for _ in range(13):
        nested = '{"a":' + nested + '}'
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"depth","sequence":1,"timestamp_ms":0,'
        f'"payload":{{"requested_mode":"head","extra":{nested}}}}}'
    )
    # The depth check passes; the extra field in payload is rejected later.
    with pytest.raises(wire.WireError, match="requested_mode"):
        wire.decode_command(raw)


def test_decode_accepts_leading_and_trailing_whitespace():
    raw = "   " + SESSION_START_JSON + "\n\t"
    command = wire.decode_command(raw)
    assert command.command is CommandName.SESSION_START


def test_decode_rejects_decoded_duplicate_keys_via_unicode_escape():
    raw = (
        '{"schema_version":"0.1","command":"session.start",'
        '"session_id":"s","sequence":1,"timestamp_ms":0,'
        '"payload":{"requested_mode":"head","\\u0072equested_mode":"arm"}}'
    )
    with pytest.raises(wire.WireError, match="duplicate"):
        wire.decode_command(raw)


def test_decode_rejects_unknown_command_discriminator_with_strict_match():
    raw = json.dumps(
        {
            "schema_version": "0.1",
            "command": "session.Start",
            "session_id": "s",
            "sequence": 1,
            "timestamp_ms": 0,
            "payload": {"requested_mode": "head"},
        }
    )
    with pytest.raises(wire.WireError):
        wire.decode_command(raw)


# --- Strict encode_event negative tests ---


def _mutated_event(event, **overrides):
    import dataclasses

    fields = {f.name: getattr(event, f.name) for f in dataclasses.fields(event)}
    fields.update(overrides)
    return type(event)(**fields)


def test_encode_event_rejects_unsupported_object():
    with pytest.raises(wire.WireError, match="approved event DTO"):
        wire.encode_event(object())  # type: ignore[arg-type]


def test_encode_event_rejects_event_with_wrong_event_type():
    event = GatewayStateEvent(1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None)
    bad = _mutated_event(
        event,
        event_type=EventName.NECK_TARGET,
    )
    with pytest.raises(wire.WireError, match="event_type"):
        wire.encode_event(bad)


def test_encode_event_rejects_event_with_wrong_schema_version():
    event = GatewayStateEvent(1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None)
    bad = _mutated_event(event, schema_version="0.2")
    with pytest.raises(wire.WireError, match="schema_version"):
        wire.encode_event(bad)


def test_encode_event_rejects_negative_gateway_monotonic_ns():
    event = GatewayStateEvent(-1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None)
    with pytest.raises(wire.WireError, match="gateway_monotonic_ns"):
        wire.encode_event(event)


def test_encode_event_rejects_overflow_gateway_monotonic_ns():
    event = GatewayStateEvent(wire.MAX_INT64 + 1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None)
    with pytest.raises(wire.WireError, match="gateway_monotonic_ns"):
        wire.encode_event(event)


def test_encode_event_rejects_nan_pan_degrees():
    event = NeckTargetEvent(1, "s-1", 1, float("nan"), 0.0)
    with pytest.raises(wire.WireError, match="finite"):
        wire.encode_event(event)


def test_encode_event_rejects_infinity_tilt_degrees():
    event = NeckTargetEvent(1, "s-1", 1, 0.0, float("inf"))
    with pytest.raises(wire.WireError, match="finite"):
        wire.encode_event(event)


def test_encode_event_rejects_partial_correlation_session_only():
    event = GatewayStateEvent(1, GatewayState.IDLE, ControlMode.HEAD_ONLY, "s-1", None)
    with pytest.raises(wire.WireError, match="correlation"):
        wire.encode_event(event)


def test_encode_event_rejects_partial_correlation_sequence_only():
    event = GatewayStateEvent(1, GatewayState.ACTIVE, ControlMode.HEAD_ONLY, None, 5)
    with pytest.raises(wire.WireError, match="correlation"):
        wire.encode_event(event)


def test_encode_event_rejects_neck_target_with_unavailable_correlation():
    event = NeckTargetEvent(1, None, None, 0.0, 0.0)
    with pytest.raises(wire.WireError, match="required"):
        wire.encode_event(event)


def test_encode_event_rejects_neck_target_with_whitespace_session_id():
    event = NeckTargetEvent(1, "   ", 1, 0.0, 0.0)
    with pytest.raises(wire.WireError, match="session_id"):
        wire.encode_event(event)


def test_encode_event_rejects_neck_target_with_out_of_range_sequence():
    event = NeckTargetEvent(1, "s-1", 0, 0.0, 0.0)
    with pytest.raises(wire.WireError, match="sequence"):
        wire.encode_event(event)


def test_encode_event_rejects_unknown_gateway_state():
    event = _mutated_event(
        GatewayStateEvent(1, GatewayState.IDLE, ControlMode.HEAD_ONLY, None, None), state="FROBNICATING"
    )
    with pytest.raises(wire.WireError, match="state"):
        wire.encode_event(event)


def test_encode_event_rejects_unknown_stop_reason():
    event = _mutated_event(
        SafetyStopEvent(1, StopReason.WATCHDOG, "s-1", 1), reason="VAPORIZED"
    )
    with pytest.raises(wire.WireError, match="StopReason"):
        wire.encode_event(event)


def test_encode_event_rejects_unknown_rejection_code():
    event = _mutated_event(
        CommandRejectedEvent(1, RejectionCode.INVALID_PAYLOAD, "msg", None, None),
        code="VAPORIZED",
    )
    with pytest.raises(wire.WireError, match="RejectionCode"):
        wire.encode_event(event)


def test_encode_event_rejects_empty_rejection_message():
    event = CommandRejectedEvent(
        1, RejectionCode.INVALID_PAYLOAD, "", None, None
    )
    with pytest.raises(wire.WireError, match="message"):
        wire.encode_event(event)


def test_encode_event_rejects_empty_safety_action_string():
    event = SafetyStopEvent(1, StopReason.WATCHDOG, "s-1", 1)
    bad = _mutated_event(event, neck_action="")
    with pytest.raises(wire.WireError, match="neck_action"):
        wire.encode_event(bad)


def test_encode_event_rejects_non_boolean_hold():
    event = NeckTargetEvent(1, "s-1", 1, 0.0, 0.0)
    bad = _mutated_event(event, hold="yes")
    with pytest.raises(wire.WireError, match="hold"):
        wire.encode_event(bad)


def test_encode_event_uses_allow_nan_false_and_serializes_clean_event():
    event = NeckTargetEvent(7, "s-1", 2, 1.25, -2.5)
    text = wire.encode_event(event)
    document = json.loads(text)
    assert document["pan_degrees"] == 1.25
    assert document["hold"] is False