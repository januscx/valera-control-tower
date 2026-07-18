# Quest 3 rosbridge head client v0.1

This slice adds a minimal Unity/OpenXR client for Meta Quest 3. It sends only
the HMD orientation through rosbridge to the existing simulation-only VR
Gateway node and displays the simulated `neck.target` response. The gateway
wire contract, watchdog, limits, and safety policy are unchanged.

## Layout

`unity/ValeraQuestHeadClient/` is a source-only Unity project. It contains
only `Assets/`, `Packages/`, and `ProjectSettings/`. The existing local
`com.januscx.valera-vr-gateway` package is referenced from `Packages/manifest.json`,
so the DTOs, `WireCodec`, `SessionSequence`, and
`QuestLocalPoseConverter` are reused rather than copied.

The client uses Unity's `System.Net.WebSockets.ClientWebSocket` API. No ROS#,
Meta XR SDK, or XR Interaction Toolkit dependency is added. The HMD transform
is assigned in the Inspector and the scene includes a `MainCamera` pose path.
On Android the source reads the tracked `InputDevice` at `XRNode.Head` via
`CommonUsages.deviceRotation`; the serialized fallback is compiled only for
the Editor and cannot be used by an Android build.

## Protocol and safety

The client advertises and subscribes before publishing commands. Command JSON
is nested in the rosbridge `std_msgs/msg/String` envelope:

```json
{"op":"publish","topic":"/valera/vr_gateway/command","msg":{"data":"<VR JSON>"}}
```

It waits for `AWAITING_RECENTER`, sends recenter only from that state, and
starts the 20 Hz pose scheduler only after `HEAD_ACTIVE`. The scheduler uses
monotonic deadlines and sends one current pose after a delay; it never flushes
stale catch-up poses. `timestamp_ms` is derived from `Stopwatch` and is forced
nondecreasing within the session.

Pause, loss of focus, disconnect, and destruction stop the pose loop first.
They then attempt `session.stop` only when the socket is open and the gateway
has confirmed the session. The receive task is cancelled and the transport is
disposed regardless of whether that best-effort send succeeds. There is no
automatic reconnect. A completed cleanup releases a single-use cleanup gate,
so a later manual Connect creates a fresh session, transport, and cancellation
source. A remote WebSocket close is treated as a terminal transport error;
the receive loop does not call `ReceiveAsync` again after its close frame.

## Pi5 launch

From an isolated workspace with the PR31 install sourced:

```bash
source /opt/ros/jazzy/setup.bash
source /tmp/valera_vr_gateway_smoke_ws/install/setup.bash

# Safe default: loopback only.
ros2 launch valera_vr_gateway valera_vr_gateway_with_rosbridge.launch.py

# Explicit trusted-LAN smoke only; replace with the Pi5 LAN address.
ros2 launch valera_vr_gateway valera_vr_gateway_with_rosbridge.launch.py \
  rosbridge_address:=<PI5_LAN_IP> rosbridge_port:=9091
```

The launch file passes rosbridge an allowlist containing exactly
`/valera/vr_gateway/command` and `/valera/vr_gateway/event`; services and
parameters remain disabled. No port forwarding, TLS, or Internet exposure is
part of this slice.

## Validation

The repository static checks and the Unity EditMode/PlayMode tests are
separate. Run the available checks with:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
git diff --check origin/main...HEAD
```

If Unity Editor, Android SDK, or ADB is unavailable, Unity tests, APK build,
and Quest runtime smoke are `PENDING: tooling unavailable`; no result is
invented. Generated Unity directories (`Library/`, `Temp/`, `Logs/`, `obj/`,
`Builds/`) and APK/AAB outputs must not be committed.

No base, arm, camera, serial, GPIO, USB, `/cmd_vel`, or physical neck-servo
endpoint is accessed. The neck remains simulated.
