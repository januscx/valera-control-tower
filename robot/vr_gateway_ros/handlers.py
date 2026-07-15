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

from typing import Callable

from robot.vr_gateway.adapter import VrGatewayAdapter
from robot.vr_gateway.gateway import VrGateway

Publish = Callable[[str], None]


class VrGatewayBridge:
    """Wire raw JSON command strings to a publish callable through the gateway."""

    def __init__(self, gateway: VrGateway, publish: Publish) -> None:
        self._adapter = VrGatewayAdapter(gateway)
        self._publish = publish

    def handle_command(self, raw: str) -> None:
        """Decode and route ``raw`` through the gateway, publishing each event."""
        for event_json in self._adapter.handle_command(raw):
            self._publish(event_json)

    def poll(self) -> None:
        """Publish each event produced by the gateway timer in order."""
        for event_json in self._adapter.poll():
            self._publish(event_json)