"""Pure-Python bridge between ROS topic callbacks and the VR gateway.

This module must not import ROS. It exposes :class:`VrGatewayBridge`, which owns
no safety logic: it delegates JSON decoding to
:class:`robot.vr_gateway.adapter.VrGatewayAdapter` and publishes each encoded
event as a separate message through an injected ``publish`` callable. A
ROS-aware caller wires the callable to a ``std_msgs/msg/String`` publisher.

Keeping this module ROS-free lets the ordinary pytest suite exercise the
adapter/timer/publish ordering without a ROS installation.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Callable

from robot.vr_gateway.adapter import VrGatewayAdapter
from robot.vr_gateway.gateway import VrGateway

Publish = Callable[[str], None]
CmdVelPublish = Callable[[SimpleNamespace], None]
ArmCommandPublish = Callable[[str], None]

DEFAULT_MAX_LINEAR_SPEED = 0.5
DEFAULT_MAX_ANGULAR_SPEED = 0.8

_BASE_TARGET = "base.target"
_ARM_TARGET = "arm.target"


class VrGatewayBridge:
    """Wire raw JSON command strings to ROS topics through the gateway.

    Routes ``base.target`` events to ``cmd_vel_publish`` and ``arm.target``
    events to ``arm_command_publish``. All other events go through ``publish``.
    """

    def __init__(
        self,
        gateway: VrGateway,
        publish: Publish,
        cmd_vel_publish: CmdVelPublish,
        arm_command_publish: ArmCommandPublish,
        max_linear_speed: float = DEFAULT_MAX_LINEAR_SPEED,
        max_angular_speed: float = DEFAULT_MAX_ANGULAR_SPEED,
    ) -> None:
        self._adapter = VrGatewayAdapter(gateway)
        self._publish = publish
        self._cmd_vel_publish = cmd_vel_publish
        self._arm_command_publish = arm_command_publish
        self._max_linear = max_linear_speed
        self._max_angular = max_angular_speed

    def handle_command(self, raw: str) -> None:
        """Decode and route ``raw`` through the gateway, publishing each event."""
        for event_json in self._adapter.handle_command(raw):
            self._dispatch(event_json)

    def poll(self) -> None:
        """Publish each event produced by the gateway timer in order."""
        for event_json in self._adapter.poll():
            self._dispatch(event_json)

    def _dispatch(self, event_json: str) -> None:
        event = json.loads(event_json)
        event_type = event.get("event_type")
        if event_type == _BASE_TARGET:
            self._publish_cmd_vel(event)
        elif event_type == _ARM_TARGET:
            self._arm_command_publish(event_json)
        else:
            self._publish(event_json)

    def _publish_cmd_vel(self, event: dict[str, object]) -> None:
        if event["command_zeroed"]:
            lx = 0.0
            az = 0.0
        else:
            lx = float(event["throttle"]) * self._max_linear  # type: ignore[operator]
            az = float(event["steering"]) * self._max_angular  # type: ignore[operator]
        self._cmd_vel_publish(
            SimpleNamespace(
                linear=SimpleNamespace(x=lx, y=0.0, z=0.0),
                angular=SimpleNamespace(x=0.0, y=0.0, z=az),
            )
        )
