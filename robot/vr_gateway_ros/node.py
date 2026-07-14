"""ROS 2 node that bridges the VR gateway JSON contract to ROS topics.

 subscribing topic:  /valera/vr_gateway/command  (std_msgs/msg/String)
 publishing topic:    /valera/vr_gateway/event    (std_msgs/msg/String)

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

ROS 2 imports here are deliberate and isolated to this module; the rest of
``robot.vr_gateway_ros`` and the whole ``robot.vr_gateway`` core package remain
importable without an installed ROS.
"""
from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from robot.vr_gateway.simulation import build_simulated_vr_gateway
from robot.vr_gateway_ros.handlers import VrGatewayBridge

DEFAULT_COMMAND_TOPIC = "/valera/vr_gateway/command"
DEFAULT_EVENT_TOPIC = "/valera/vr_gateway/event"
DEFAULT_POLL_PERIOD_MS = 20


class VrGatewayNode(Node):
    def __init__(self) -> None:
        super().__init__("valera_vr_gateway")

        self.declare_parameter("command_topic", DEFAULT_COMMAND_TOPIC)
        self.declare_parameter("event_topic", DEFAULT_EVENT_TOPIC)
        self.declare_parameter("poll_period_ms", DEFAULT_POLL_PERIOD_MS)

        command_topic = self.get_parameter("command_topic").value
        event_topic = self.get_parameter("event_topic").value
        poll_period_ms = self.get_parameter("poll_period_ms").value

        ros_clock = self.get_clock()
        self._gateway = build_simulated_vr_gateway(
            lambda: ros_clock.now().nanoseconds
        )

        self._publisher = self.create_publisher(String, event_topic, 10)
        self._bridge = VrGatewayBridge(self._gateway, self._publish_event)

        self.create_subscription(String, command_topic, self._on_command, 10)
        self.create_timer(poll_period_ms / 1000.0, self._bridge.poll)

        self.get_logger().info(
            "valera_vr_gateway ready: command=%s event=%s poll=%dms (sim neck)",
            command_topic,
            event_topic,
            poll_period_ms,
        )

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