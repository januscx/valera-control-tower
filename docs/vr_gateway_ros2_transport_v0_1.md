# VR Gateway ROS 2 Transport Slice v0.1

Date: 2026-07-14

## Purpose

Add a minimal ROS 2 / rosbridge-compatible transport slice for the Unity VR
Gateway v0.1. It is a thin adapter that moves raw JSON strings between ROS
topics and the transport-neutral gateway core
(`robot/vr_gateway`). It owns no safety decisions.

## Architecture boundary

```text
Unity Quest client
  -> JSON command string
  -> /valera/vr_gateway/command  (std_msgs/String, ROS 2 only)
  -> VrGatewayWire.decode_command  -> project-owned DTO
  -> VrGatewayAdapter.handle_command
       -> VrGateway.handle(command)
       -> output events (DTO)
  -> wire.encode_event -> JSON string
  -> /valera/vr_gateway/event  (std_msgs/String, published per event)
```

The ROS layer is only an adapter. It must never host:

- session state
- sequence/timestamp decisions
- watchdog decisions
- mode policy
- E-stop logic
- neck safety limits
- base/arm control

`rosbridge` is reached through ordinary ROS topics. There is **no WebSocket
client** in this slice.

## Files

- `robot/vr_gateway/wire.py` - transport-neutral JSON codec. Strict fail-closed
  decoding of all 6 commands and encoding of all 4 events.
- `robot/vr_gateway/adapter.py` - thin adapter. Routes decode failures through
  `VrGateway.handle` (the existing fail-closed path), returns encoded events in
  the original gateway order.
- `robot/vr_gateway_ros/handlers.py` - pure-Python `VrGatewayBridge`. ROS-free.
- `robot/vr_gateway_ros/node.py` - ROS 2 node (`rclpy`). ROS imports are
  isolated here so the rest of the package and the pytest suite import without
  an installed ROS.

## ROS 2 topics

| direction | topic | type | notes |
|-----------|-------|------|-------|
| subscribe | `/valera/vr_gateway/command` | `std_msgs/msg/String` | `data` is a raw JSON command string (v0.1 contract) |
| publish | `/valera/vr_gateway/event` | `std_msgs/msg/String` | one message per gateway event, emitted in gateway order |

The node is named `valera_vr_gateway`. The poll timer defaults to 20 ms and is
configurable via the `poll_period_ms` ROS parameter; `command_topic` and
`event_topic` parameters override the topic names. The node uses only the
simulation neck configuration; it never opens neck servos, the tracked base, or
the SO-101 arm.

## JSON contract v0.1 (recap)

### Command envelope

```json
{
  "schema_version": "0.1",
  "command": "head.pose",
  "session_id": "unity-head-001",
  "sequence": 3,
  "timestamp_ms": 2,
  "payload": {
    "frame": "quest_local",
    "orientation": {"x": 0.0, "y": 0.1, "z": 0.0, "w": 1.0},
    "position": {"x": 0.0, "y": 1.5, "z": -2.0}
  }
}
```

Approved commands and payloads:

| command | payload |
|--------|---------|
| `session.start` | `{"requested_mode": "head"}` |
| `session.stop` | `{}` |
| `mode.set` | `{"mode": "head"}` (`drive` / `arm` return `MODE_BLOCKED`, unknown values return `UNKNOWN_MODE`) |
| `head.pose` | `{"frame":"quest_local","orientation":{"x","y","z","w"},"position":{"x","y","z"}}` (`position` optional or null) |
| `head.recenter` | `{"frame":"quest_local","orientation":{"x","y","z","w"}}` (`position` optional or null) |
| `emergency_stop` | `{}` |

Strict decode rules: duplicate keys, `NaN`/`Infinity` literals, trailing data,
missing/extra fields, wrong types, and unknown command discriminators are all
rejected. Decode failures are routed through `VrGateway.handle`, so the gateway
emits the `INVALID_PAYLOAD` rejection (plus any elapsed-deadline events) through
its existing fail-closed path. The adapter never synthesizes a safety event.

### Output events

Each event is published as its own `String` message. Field order is the
dataclass declaration order; parsers must treat JSON objects as unordered.

`gateway.state`:

```json
{
  "gateway_monotonic_ns": 11,
  "state": "HEAD_ACTIVE",
  "session_id": "unity-head-001",
  "sequence": 2,
  "schema_version": "0.1",
  "event_type": "gateway.state"
}
```

`neck.target`:

```json
{
  "gateway_monotonic_ns": 22,
  "session_id": "unity-head-001",
  "sequence": 3,
  "pan_degrees": 1.25,
  "tilt_degrees": -2.5,
  "hold": false,
  "schema_version": "0.1",
  "event_type": "neck.target"
}
```

`safety.stop`:

```json
{
  "gateway_monotonic_ns": 33,
  "reason": "WATCHDOG",
  "session_id": "unity-head-001",
  "sequence": 4,
  "neck_action": "HOLD_LAST_POSITION",
  "base_action": "STOP",
  "arm_action": "HOLD",
  "schema_version": "0.1",
  "event_type": "safety.stop"
}
```

`command.rejected`:

```json
{
  "gateway_monotonic_ns": 44,
  "code": "INVALID_PAYLOAD",
  "message": "Command payload is invalid.",
  "session_id": null,
  "sequence": null,
  "schema_version": "0.1",
  "event_type": "command.rejected"
}
```

`session_id` and `sequence` are `null` in `gateway.state`, `safety.stop`, and
`command.rejected` when the correlated command is unavailable (for example after
a watchdog expiry or a malformed envelope).

## End-to-end example (CLI, no ROS required)

```bash
python3 scripts/run_vr_gateway_simulation.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_wire.py tests/test_vr_gateway_ros_node.py -v
```

These run the transport-neutral core and the ROS-free bridge logic. They open
no ROS, network, base, arm, gripper, or real neck device.

## Monotonic watchdog clock

The gateway watchdog and handshake timeout use `time.monotonic_ns`, not ROS
Time. ROS Time may pause or jump when `use_sim_time` is enabled or during
rosbag playback; a steady monotonic clock ensures that simulated time, rosbag
playback, or `/clock` pauses cannot stop watchdog evaluation. The poll timer
is scheduled using `rclpy`'s steady timer (the default backing clock is
steady), and the configured poll period is validated as finite and positive
before the timer is created.

## ROS 2 smoke (requires an installed ROS 2 Jazzy)

This repository has no ROS 2 package metadata or `ros2 run` entry point --
that would require an `ament_python` package layout, `setup.py`,
`package.xml`, and a colcon workspace. The node is invoked directly as a
Python module under a sourced ROS 2 environment:

```bash
# Source ROS 2 Jazzy first, then from the repository root:
python3 -m robot.vr_gateway_ros.node

# In another shell (ROS 2 sourced):
ros2 topic pub /valera/vr_gateway/command std_msgs/msg/String \
  '{data: "{\"schema_version\":\"0.1\",\"command\":\"emergency_stop\",\"session_id\":\"operator\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{}}"}' once
ros2 topic echo /valera/vr_gateway/event
```

The node logs `valera_vr_gateway ready: ...` and then only subscribes/publishes
strings; it never moves equipment. A guarded hardware slice must be added
separately with explicit safety notes. Adding `ament_python` package metadata
is deferred until the repository structure warrants it.

## Limitations

- This slice does **not** wire real neck servos, the tracked base, or the
  SO-101 arm. It uses the simulation neck configuration only.
- rosbridge/WebSocket integration is intentionally absent; only ROS topics are
  used.
- The ROS 2 node depends on an installed ROS 2 Jazzy; the pure-Python test
  suite does not exercise `robot/vr_gateway_ros/node.py`.
- No `safety.reset` command exists; recovery from `ESTOP_LATCHED` still requires
  restarting the gateway process.
- The repository has no ROS 2 package metadata (`package.xml`, `setup.py`,
  colcon entry point); the node is invoked via `python3 -m robot.vr_gateway_ros.node`.