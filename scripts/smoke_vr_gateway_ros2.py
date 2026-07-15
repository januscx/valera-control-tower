#!/usr/bin/env python3
"""Simulation-only ROS 2 runtime smoke for the installed VR Gateway package.

Run after sourcing the ROS and colcon workspaces. This is intentionally a
test-only client: the production node remains a plain ROS topic adapter and
contains no WebSocket implementation.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


COMMAND_TOPIC = "/valera/vr_gateway/command"
EVENT_TOPIC = "/valera/vr_gateway/event"
NODE_COMMAND = ["ros2", "run", "valera_vr_gateway", "valera_vr_gateway_node"]
LAUNCH_COMMAND = [
    "ros2",
    "launch",
    "valera_vr_gateway",
    "valera_vr_gateway_with_rosbridge.launch.py",
]


def command(name: str, session_id: str, sequence: int, timestamp_ms: int, payload: dict[str, Any]) -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "command": name,
            "session_id": session_id,
            "sequence": sequence,
            "timestamp_ms": timestamp_ms,
            "payload": payload,
        }
    )


def session_start(session_id: str = "smoke-session") -> str:
    return command("session.start", session_id, 1, 0, {"requested_mode": "head"})


def recenter(session_id: str = "smoke-session") -> str:
    return command(
        "head.recenter",
        session_id,
        2,
        1,
        {
            "frame": "quest_local",
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    )


def pose(session_id: str = "smoke-session") -> str:
    return command(
        "head.pose",
        session_id,
        3,
        2,
        {
            "frame": "quest_local",
            "orientation": {"x": 0.0, "y": 0.1, "z": 0.0, "w": 1.0},
        },
    )


def safety_stop() -> str:
    return command("safety.stop", "smoke-stop", 1, 0, {})


@dataclass
class GatewayProcess:
    process: subprocess.Popen[str] | None = None

    def __enter__(self) -> "GatewayProcess":
        self.process = subprocess.Popen(
            NODE_COMMAND,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
            start_new_session=True,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            self.process.wait(timeout=3)


class RosProbe(Node):
    def __init__(self) -> None:
        super().__init__("valera_vr_gateway_smoke_probe")
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.publisher = self.create_publisher(String, COMMAND_TOPIC, 10)
        self.create_subscription(String, EVENT_TOPIC, self._on_event, 10)

    def _on_event(self, message: String) -> None:
        self.events.put(json.loads(message.data))

    def wait_for_topics(self, deadline: float) -> None:
        while time.monotonic() < deadline:
            names = {name for name, _ in self.get_topic_names_and_types()}
            if (
                {COMMAND_TOPIC, EVENT_TOPIC}.issubset(names)
                and self.publisher.get_subscription_count() > 0
                and self.count_publishers(EVENT_TOPIC) > 0
            ):
                return
            rclpy.spin_once(self, timeout_sec=0.1)
        raise RuntimeError("gateway did not advertise both expected topics")

    def publish(self, raw: str) -> None:
        message = String()
        message.data = raw
        self.publisher.publish(message)

    def collect(self, count: int, deadline: float) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        while len(result) < count and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            try:
                result.append(self.events.get_nowait())
            except queue.Empty:
                pass
        if len(result) < count:
            raise RuntimeError(f"expected {count} events, received {len(result)}")
        return result


def isolated(scenario: str, callback) -> None:
    print(f"scenario: {scenario}")
    with GatewayProcess():
        probe = RosProbe()
        try:
            probe.wait_for_topics(time.monotonic() + 5)
            callback(probe)
        finally:
            probe.destroy_node()


def scenario_session_and_pose(probe: RosProbe) -> None:
    probe.publish(session_start())
    probe.collect(1, time.monotonic() + 2)
    probe.publish(recenter())
    recenter_event = probe.collect(1, time.monotonic() + 2)[0]
    assert recenter_event["state"] == "HEAD_ACTIVE"
    probe.publish(pose())
    pose_event = probe.collect(1, time.monotonic() + 2)[0]
    assert pose_event["event_type"] == "neck.target"
    assert pose_event["session_id"] == "smoke-session"
    assert pose_event["sequence"] == 3
    print("  ordered session/recenter/pose events: PASS")


def scenario_handshake_timeout(probe: RosProbe) -> None:
    probe.publish(session_start("timeout-session"))
    probe.collect(1, time.monotonic() + 2)
    event = probe.collect(1, time.monotonic() + 11)[0]
    assert event["state"] == "IDLE"
    print("  handshake timeout via poll(): PASS")


def scenario_watchdog(probe: RosProbe) -> None:
    probe.publish(session_start("watchdog-session"))
    probe.collect(1, time.monotonic() + 2)
    probe.publish(recenter("watchdog-session"))
    probe.collect(1, time.monotonic() + 2)
    probe.publish(pose("watchdog-session"))
    probe.collect(1, time.monotonic() + 2)
    events = probe.collect(2, time.monotonic() + 2)
    assert [event["state"] if "state" in event else event["event_type"] for event in events] == [
        "SAFE_STOPPED",
        "safety.stop",
    ]
    assert events[1]["reason"] == "WATCHDOG"
    print("  watchdog -> SAFE_STOPPED -> safety.stop: PASS")


def scenario_rejections(probe: RosProbe) -> None:
    probe.publish("{not json")
    invalid = probe.collect(1, time.monotonic() + 2)[0]
    assert invalid["event_type"] == "command.rejected"
    assert invalid["code"] == "INVALID_PAYLOAD"
    probe.publish(
        command("emergency_stop", "operator-stop", 1, 0, {})
    )
    estop = probe.collect(2, time.monotonic() + 2)
    assert estop[0]["state"] == "ESTOP_LATCHED"
    assert estop[1]["event_type"] == "safety.stop"
    assert estop[1]["reason"] == "EMERGENCY_STOP"
    print("  malformed JSON and emergency_stop: PASS")


def scenario_empty_events(probe: RosProbe) -> None:
    probe.publish(session_start("empty-session"))
    probe.collect(1, time.monotonic() + 2)
    probe.publish(
        command("mode.set", "empty-session", 2, 1, {"mode": "head"})
    )
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        rclpy.spin_once(probe, timeout_sec=0.1)
    assert probe.events.empty()
    print("  empty event list publishes nothing: PASS")


def gateway_smoke() -> None:
    rclpy.init()
    try:
        isolated("session and pose", scenario_session_and_pose)
        isolated("handshake timeout", scenario_handshake_timeout)
        isolated("watchdog", scenario_watchdog)
        isolated("rejections", scenario_rejections)
        isolated("empty events", scenario_empty_events)
    finally:
        rclpy.shutdown()


def websocket_smoke(timeout: float) -> int:
    try:
        import websocket
    except ImportError:
        print("PENDING: no test-only WebSocket client is installed", file=sys.stderr)
        return 2

    process = subprocess.Popen(
        LAUNCH_COMMAND,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", 9090), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("rosbridge WebSocket did not open on loopback:9090")
        with websocket.create_connection("ws://127.0.0.1:9090", timeout=timeout) as client:
            client.send(json.dumps({"op": "subscribe", "topic": EVENT_TOPIC}))
            client.send(json.dumps({"op": "publish", "topic": COMMAND_TOPIC, "msg": json.loads(session_start())}))
            while time.monotonic() < deadline:
                document = json.loads(client.recv())
                if document.get("topic") == EVENT_TOPIC:
                    assert document["msg"]["state"] == "AWAITING_RECENTER"
                    print("rosbridge WebSocket loopback smoke: PASS")
                    return 0
        raise RuntimeError("rosbridge did not return the expected event")
    finally:
        if process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("gateway", "rosbridge"), default="gateway")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    if args.mode == "gateway":
        gateway_smoke()
        return 0
    return websocket_smoke(args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
