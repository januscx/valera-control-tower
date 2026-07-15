# VR Gateway ROS 2 runtime smoke v0.1

## Packaging decision

The ROS 2 package lives at `ros2/valera_vr_gateway/` as a small
`ament_python` wrapper. It does not copy the production modules. `setup.py`
discovers the existing `robot` package tree from the repository root and
installs `robot.vr_gateway` and `robot.vr_gateway_ros` directly. The only
production entry point is:

```text
valera_vr_gateway_node = robot.vr_gateway_ros.node:main
```

The gateway-only launch starts that entry point. The combined launch includes
Jazzy's installed `rosbridge_websocket_launch.xml`. Its interface was inspected
on Pi5; the launch passes the supported `port`, `address`, `topics_glob`,
`services_glob`, and `params_glob` arguments. Because Jazzy declares these as
scalar strings, the glob lists are quoted in the launch file.

## Isolated build

These commands do not use the live Pi5 workspace or services:

```bash
source /opt/ros/jazzy/setup.bash
rm -rf /tmp/valera_vr_gateway_smoke_ws
mkdir -p /tmp/valera_vr_gateway_smoke_ws/src
git clone --branch codex/vr-gateway-ros2-runtime-smoke-v0-1 \
  --single-branch https://github.com/januscx/valera-control-tower.git \
  /tmp/valera_vr_gateway_smoke_ws/src/valera-control-tower
cd /tmp/valera_vr_gateway_smoke_ws
colcon build --packages-select valera_vr_gateway
source install/setup.bash
```

Observed on Pi5:

```text
Starting >>> valera_vr_gateway
Finished <<< valera_vr_gateway [1.79s]
Summary: 1 package finished
valera_vr_gateway valera_vr_gateway_node
```

## Gateway runtime smoke

Run from the checked-out repository after sourcing the isolated install:

```bash
cd /tmp/valera_vr_gateway_smoke_ws/src/valera-control-tower
python3 -u scripts/smoke_vr_gateway_ros2.py --mode gateway
```

The harness starts a fresh `ros2 run` process for every stateful scenario,
waits for both expected DDS connections, applies strict timeouts, and kills
the complete child process group in `finally` cleanup. Observed on Pi5:

```text
scenario: session and pose
  ordered session/recenter/pose events: PASS
scenario: handshake timeout
  handshake timeout via poll(): PASS
scenario: watchdog
  watchdog -> SAFE_STOPPED -> safety.stop: PASS
scenario: rejections
  malformed JSON and emergency_stop: PASS
scenario: empty events
  empty event list publishes nothing: PASS
```

The scenarios validate `session.start` → `AWAITING_RECENTER`,
`head.recenter` → `HEAD_ACTIVE`, one ordered `neck.target` for `head.pose`,
correlation fields, handshake timeout, watchdog stop, malformed JSON rejection,
emergency-stop latching, and no publication for an empty event list.

## Launch smoke and topic boundary

Gateway-only launch:

```bash
ros2 launch valera_vr_gateway valera_vr_gateway.launch.py
```

Gateway plus loopback rosbridge:

```bash
ros2 launch valera_vr_gateway valera_vr_gateway_with_rosbridge.launch.py
```

Observed on Pi5 for the gateway-only launch:

```text
/parameter_events
/rosout
/valera/vr_gateway/command
/valera/vr_gateway/event
```

Observed for the combined launch:

```text
Rosbridge WebSocket server started on port 9090
```

The combined launch bound to `127.0.0.1:9090`. Its topic allowlist is exactly:

```text
/valera/vr_gateway/command
/valera/vr_gateway/event
```

`services_glob` and `params_glob` are empty filters. No `/cmd_vel`, base, arm,
camera, serial, GPIO, or RC topic appeared. The node log reported `sim neck`,
`monotonic watchdog clock`, and `steady poll timer`.

## WebSocket smoke

The smoke harness uses an optional test-only `websocket-client` import and does
not add WebSocket code to the production node:

```bash
python3 scripts/smoke_vr_gateway_ros2.py --mode rosbridge
```

Pi5 result: **pending**. `websocket`, `websockets`, and `roslibpy` were not
installed, so no WebSocket success is claimed and no dependency was installed
into the system or live workspace.

## Cleanup

For foreground launch smoke, stop with `Ctrl-C`. For an interrupted isolated
run, terminate only the temporary workspace processes:

```bash
pkill -TERM -f /tmp/valera_vr_gateway_smoke_ws
```

Then confirm cleanup:

```bash
ps -eo pid,args | grep -E \
  '/tmp/valera_vr_gateway_smoke_ws|rosbridge|rosapi|smoke_vr_gateway_ros2' \
  | grep -v grep || true
```

No live Pi5 workspace, tmux session, systemd service, or hardware endpoint was
modified. The node accesses only ROS `std_msgs/msg/String` topics and the
existing simulation neck configuration; it does not open servos, base, arm,
cameras, serial devices, GPIO, USB, or RC control.

## Local validation

The development host has ROS 2 Jazzy and `colcon`, but not `rosbridge_server`
or a WebSocket client. The local isolated `colcon` build and installed
gateway-only smoke passed; the Pi5 has the full rosbridge package and passed
the combined launch smoke. Ordinary pytest remains ROS-independent.
