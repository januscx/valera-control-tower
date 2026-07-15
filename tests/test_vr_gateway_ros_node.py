"""Pure-Python tests for the ROS node bridge logic.

These tests import only :mod:`robot.vr_gateway_ros.handlers`, which itself
imports no ROS. They prove the bridge's adapter wiring, publish ordering, and
timer behavior without requiring an installed ROS 2 stack.
"""
import json
from pathlib import Path

import pytest

from robot.vr_gateway.gateway import VrGateway
from robot.vr_gateway.messages import EventName, RejectionCode
from robot.vr_gateway.neck import NeckControlConfig, NeckController
from robot.vr_gateway_ros.handlers import VrGatewayBridge


SESSION_START_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "session.start",
        "session_id": "ros-head-001",
        "sequence": 1,
        "timestamp_ms": 0,
        "payload": {"requested_mode": "head"},
    }
)
HEAD_RECENTER_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "head.recenter",
        "session_id": "ros-head-001",
        "sequence": 2,
        "timestamp_ms": 1,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }
)
HEAD_POSE_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "head.pose",
        "session_id": "ros-head-001",
        "sequence": 3,
        "timestamp_ms": 2,
        "payload": {
            "frame": "quest_local",
            "orientation": {"x": 0.0, "y": 0.1, "z": 0.0, "w": 1.0},
        },
    }
)
SESSION_STOP_JSON = json.dumps(
    {
        "schema_version": "0.1",
        "command": "session.stop",
        "session_id": "ros-head-001",
        "sequence": 4,
        "timestamp_ms": 3,
        "payload": {},
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


class FakeClock:
    def __init__(self) -> None:
        self.now_ns = 0

    def __call__(self) -> int:
        return self.now_ns

    def advance_ms(self, value: int) -> None:
        self.now_ns += value * 1_000_000


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[str] = []

    def __call__(self, message: str) -> None:
        self.published.append(message)


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


def _bridge() -> tuple[VrGatewayBridge, VrGateway, FakeClock, FakePublisher]:
    clock = FakeClock()
    gateway = VrGateway(_neck(), clock=clock)
    publisher = FakePublisher()
    return VrGatewayBridge(gateway, publisher), gateway, clock, publisher


def test_bridge_publishes_each_event_as_a_separate_message_in_order():
    bridge, gateway, _, publisher = _bridge()
    bridge.handle_command(SESSION_START_JSON)
    bridge.handle_command(HEAD_RECENTER_JSON)

    publisher.published.clear()
    bridge.handle_command(SESSION_STOP_JSON)

    documents = [json.loads(message) for message in publisher.published]
    assert [d["event_type"] for d in documents] == [
        EventName.GATEWAY_STATE.value,
        EventName.SAFETY_STOP.value,
    ]
    assert len(publisher.published) == 2


def test_bridge_publishes_nothing_when_command_leaves_state_unchanged():
    bridge, gateway, _, publisher = _bridge()
    bridge.handle_command(SESSION_START_JSON)
    publisher.published.clear()

    # mode.set("head") in a freshly-started head session emits no event.
    bridge.handle_command(
        json.dumps(
            {
                "schema_version": "0.1",
                "command": "mode.set",
                "session_id": "ros-head-001",
                "sequence": 2,
                "timestamp_ms": 1,
                "payload": {"mode": "head"},
            }
        )
    )

    assert publisher.published == []


def test_bridge_malformed_command_routes_through_gateway_fail_closed():
    bridge, gateway, _, publisher = _bridge()

    bridge.handle_command("{not json")

    assert len(publisher.published) == 1
    document = json.loads(publisher.published[0])
    assert document["event_type"] == EventName.COMMAND_REJECTED.value
    assert document["code"] == RejectionCode.INVALID_PAYLOAD.value


def test_bridge_handshake_timeout_via_poll_publishes_only_state_event():
    bridge, gateway, clock, publisher = _bridge()
    bridge.handle_command(SESSION_START_JSON)
    clock.advance_ms(10_000)

    publisher.published.clear()
    bridge.poll()

    documents = [json.loads(message) for message in publisher.published]
    assert [d["event_type"] for d in documents] == [EventName.GATEWAY_STATE.value]
    assert documents[0]["state"] == "IDLE"
    assert not any(d["event_type"] == EventName.SAFETY_STOP.value for d in documents)


def test_bridge_watchdog_stop_via_poll_publishes_state_then_safety_stop():
    bridge, gateway, clock, publisher = _bridge()
    bridge.handle_command(SESSION_START_JSON)
    bridge.handle_command(HEAD_RECENTER_JSON)
    bridge.handle_command(HEAD_POSE_JSON)
    clock.advance_ms(250)

    publisher.published.clear()
    bridge.poll()

    documents = [json.loads(message) for message in publisher.published]
    assert [d["event_type"] for d in documents] == [
        EventName.GATEWAY_STATE.value,
        EventName.SAFETY_STOP.value,
    ]
    assert documents[0]["state"] == "SAFE_STOPPED"
    assert documents[1]["reason"] == "WATCHDOG"


def test_bridge_poll_publishes_nothing_when_event_list_empty():
    bridge, gateway, _, publisher = _bridge()
    bridge.handle_command(SESSION_START_JSON)
    publisher.published.clear()

    bridge.poll()

    assert publisher.published == []


def test_bridge_estop_publishes_each_event_separately_from_idle():
    bridge, gateway, _, publisher = _bridge()

    bridge.handle_command(EMERGENCY_STOP_JSON)

    documents = [json.loads(message) for message in publisher.published]
    assert [d["event_type"] for d in documents] == [
        EventName.GATEWAY_STATE.value,
        EventName.SAFETY_STOP.value,
    ]
    assert documents[0]["state"] == "ESTOP_LATCHED"
    assert documents[1]["reason"] == "EMERGENCY_STOP"


def test_handlers_module_imports_no_ros():
    import ast

    handlers = Path(__file__).resolve().parents[1] / "robot" / "vr_gateway_ros" / "handlers.py"
    tree = ast.parse(handlers.read_text(encoding="utf-8"))
    forbidden = {"rclpy", "rcl_interfaces", "std_msgs", "geometry_msgs", "roslibpy"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in forbidden
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".", 1)[0] not in forbidden


def test_node_module_is_isolated_from_importable_core():
    # The node module deliberately imports rclpy at module top. It must not be
    # collected by the ordinary pytest suite, and the handlers/ros-free bridge
    # must remain importable without rclpy installed. This test only asserts
    # that handlers.py imports cleanly here; it does not import node.py.
    from robot.vr_gateway_ros import handlers  # noqa: F401

    assert VrGatewayBridge is handlers.VrGatewayBridge


def test_node_source_contract_uses_explicit_steady_clock_and_monotonic_ns():
    """Static AST check: the node uses an explicit steady clock for create_timer
    and passes time.monotonic_ns to the gateway, even though we cannot import
    the rclpy-dependent module in this environment."""
    import ast

    node = Path(__file__).resolve().parents[1] / "robot" / "vr_gateway_ros" / "node.py"
    source = node.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "ClockType.STEADY_TIME" in source
    assert "clock=self._steady_clock" in source
    assert "time.monotonic_ns" in source

    # Ensure the rclpy clock import is present (not the local type alias).
    imports = set()
    for imp in ast.walk(tree):
        if isinstance(imp, ast.ImportFrom):
            assert imp.module is not None
            imports.add((imp.module, frozenset(alias.name for alias in imp.names)))
    assert ("rclpy.clock", frozenset({"Clock", "ClockType"})) in imports


def test_node_source_validates_ros_parameters_before_use():
    import ast
    import re

    node = Path(__file__).resolve().parents[1] / "robot" / "vr_gateway_ros" / "node.py"
    source = node.read_text(encoding="utf-8")

    assert "_validate_topic(" in source
    assert "_validate_poll_period_ms(" in source

    # The publisher/subscription/timer must be created after validation calls.
    publisher_idx = source.index("self.create_publisher")
    subscription_idx = source.index("self.create_subscription")
    timer_idx = source.index("self.create_timer")
    validate_topic_idx = source.index("_validate_topic(")
    validate_poll_idx = source.index("_validate_poll_period_ms(")
    assert validate_topic_idx < publisher_idx
    assert validate_topic_idx < subscription_idx
    assert validate_topic_idx < timer_idx
    assert validate_poll_idx < timer_idx


def test_gateway_build_helper_passes_monotonic_clock_to_node():
    import ast

    node = Path(__file__).resolve().parents[1] / "robot" / "vr_gateway_ros" / "node.py"
    source = node.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Look for the call build_simulated_vr_gateway(time.monotonic_ns).
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_simulated_vr_gateway"
    ]
    assert len(calls) == 1
    args = calls[0].args
    assert len(args) == 1
    assert isinstance(args[0], ast.Attribute)
    assert args[0].attr == "monotonic_ns"
    assert isinstance(args[0].value, ast.Name)
    assert args[0].value.id == "time"