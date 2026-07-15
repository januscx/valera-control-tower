"""ROS 2 node that bridges the VR gateway JSON contract to ROS topics.

subscribing topic:  /valera/vr_gateway/command  (std_msgs/msg/String)
publishing topic:   /valera/vr_gateway/event    (std_msgs/msg/String)

The node owns no safety decisions. The payload of every command message is a
raw JSON string conforming to the v0.1 contract; it is decoded by
:mod:`robot.vr_gateway.wire` and routed through
:class:`robot.vr_gateway.gateway.VrGateway`. Each gateway output event is
published as its own ``String`` message in the original gateway order. A
configurable poll timer (default 20 ms) drives ``VrGateway.poll`` so handshake
and motion-watchdog deadlines fire without incoming traffic.

The node uses the *simulation* neck configuration only. It never opens real
neck servos, the tracked base, or the SO-101 arm. A guarded hardware slice must
be added separately with explicit safety notes.

Monotonic clock: the gateway watchdog and handshake timeout use ``time.monotonic_ns``,
not ROS Time. ROS Time may pause or jump when ``use_sim_time`` is enabled or
during rosbag playback; a steady monotonic clock ensures that simulated time,
rosbag playback, or ``/clock`` pauses cannot stop watchdog evaluation. The poll
timer is scheduled on an explicit ``rclpy.clock.Clock(clock_type=ClockType.STEADY_TIME)``
instead of the node's default clock, which may be a ROSClock under sim time.

ROS 2 imports here are deliberate and isolated to this module; the rest of
``robot.vr_gateway_ros`` and the whole ``robot.vr_gateway`` core package remain
importable without an installed ROS.
"""
from __future__ import annotations

import time

import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from std_msgs.msg import String

from robot.vr_gateway.simulation import build_simulated_vr_gateway
from robot.vr_gateway_ros.handlers import VrGatewayBridge

DEFAULT_COMMAND_TOPIC = "/valera/vr_gateway/command"
DEFAULT_EVENT_TOPIC = "/valera/vr_gateway/event"
DEFAULT_POLL_PERIOD_MS = 20
MAX_POLL_PERIOD_MS = 60_000


def _validate_topic(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_poll_period_ms(value: object) -> int:
    if type(value) is not int:
        raise ValueError("poll_period_ms must be an integer")
    if value <= 0:
        raise ValueError("poll_period_ms must be positive")
    if value > MAX_POLL_PERIOD_MS:
        raise ValueError(f"poll_period_ms must not exceed {MAX_POLL_PERIOD_MS}")
    return value


class VrGatewayNode(Node):
    def __init__(self) -> None:
        super().__init__("valera_vr_gateway")

        self.declare_parameter("command_topic", DEFAULT_COMMAND_TOPIC)
        self.declare_parameter("event_topic", DEFAULT_EVENT_TOPIC)
        self.declare_parameter("poll_period_ms", DEFAULT_POLL_PERIOD_MS)

        command_topic = _validate_topic(
            self.get_parameter("command_topic").value, "command_topic"
        )
        event_topic = _validate_topic(
            self.get_parameter("event_topic").value, "event_topic"
        )
        poll_period_ms = _validate_poll_period_ms(
            self.get_parameter("poll_period_ms").value
        )

        self._gateway = build_simulated_vr_gateway(time.monotonic_ns)

        # Explicit steady clock for the poll timer. The default node clock may
        # be a ROSClock that pauses under use_sim_time or /clock; the watchdog
        # must keep running.
        self._steady_clock = Clock(clock_type=ClockType.STEADY_TIME)

        self._publisher = self.create_publisher(String, event_topic, 10)
        self._bridge = VrGatewayBridge(self._gateway, self._publish_event)

        self.create_subscription(String, command_topic, self._on_command, 10)
        self.create_timer(
            poll_period_ms / 1000.0,
            self._bridge.poll,
            clock=self._steady_clock,
        )

        message = (
            f"valera_vr_gateway ready: command={command_topic} "
            f"event={event_topic} poll={poll_period_ms}ms (sim neck, "
            "monotonic watchdog clock, steady poll timer)"
        )
        self.get_logger().info(message)

    def _publish_event(self, event_json: str) -> None:
        message = String()
        message.data = event_json
        self._publisher.publish(message)

    def _on_command(self, message: String) -> None:
        self._bridge.handle_command(message.data)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VrGatewayNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()