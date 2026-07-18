# Quest 3 rosbridge head client v0.1 Design

## Goal

Add a minimal Unity/OpenXR Meta Quest 3 client that sends real HMD orientation
through the existing VR Gateway JSON contract over rosbridge WebSocket and
displays returned simulated neck targets. No physical hardware is controlled.

## Scope and boundaries

- The client uses the existing `WireCodec`, DTOs, `SessionSequence`, and
  `QuestLocalPoseConverter` from `unity/Valera.VrGateway`.
- The client sends orientation only; pose position is omitted.
- The gateway contract, safety policy, watchdog, mechanical limits, neck
  controller, and ROS topics are unchanged.
- Pi5 rosbridge keeps `address:=127.0.0.1` as the default; LAN binding requires
  an explicit launch argument and remains limited to the two VR Gateway topics.
- Unity source is committed only under `Assets/`, `Packages/`, and
  `ProjectSettings/`; generated directories and APK/AAB files are excluded.

## Protocol

After WebSocket connection the client advertises the command topic, subscribes
to the event topic, creates a unique session id, and sends `session.start` with
sequence 1 and `requested_mode=head`. It waits for the gateway state event
`AWAITING_RECENTER`. Recenter is enabled only in that state and sends the
current HMD orientation as `head.recenter`; local `HeadActive` is entered only
after the gateway sends `HEAD_ACTIVE`. `head.pose` is forbidden before that
event and is sampled at 20 Hz using a monotonic scheduler that sends at most one
current pose per tick, never accumulated catch-up packets.

Commands use `msg.data` for the inner VR JSON string. Events are decoded from
the same `std_msgs/msg/String` field. `timestamp_ms` is derived from a
monotonic `Stopwatch` origin and is clamped non-decreasing within a session.

Disconnect, pause, application focus loss, and object destruction stop the
pose loop first, then best-effort send `session.stop` only when the socket is
open and the session has started, using a new sequence and timestamp. Receive
cancellation and transport disposal always follow, even if stop delivery
fails. `SAFE_STOPPED`, `IDLE`, socket errors, and session-invalidating
`command.rejected` events stop pose transmission immediately.

## Components

- `RosbridgeEnvelopeCodec`: serializes/deserializes rosbridge outer envelopes
  without changing the inner VR contract.
- `QuestHeadSession`: pure C# session state machine, command sequencing,
  monotonic timestamps, cadence, and cleanup decisions.
- `QuestHeadPoseSource`: Unity/OpenXR HMD orientation with editor fallback.
- `QuestHeadClientBehaviour`: Unity main-thread lifecycle, transport receive
  dispatch, and Inspector configuration.
- `QuestHeadDebugPanel`: minimal world-space runtime status and controls.

The WebSocket transport uses `ClientWebSocket` if the selected Unity runtime
supports it on Android IL2CPP. If the available Unity toolchain proves that it
does not, the PR will document the compatibility blocker and keep the
transport behind a narrow interface rather than adding an unverified library.

## Validation

EditMode/PlayMode tests cover envelopes, inner `msg.data`, state transitions,
pose gating, monotonic sequence/timestamps, 20 Hz no-catch-up cadence,
best-effort cleanup, malformed events, rejection handling, main-thread
dispatch, and forbidden hardware/ROS endpoints. Repository pytest and static
checks run locally. Unity tests, Android APK build, and Quest ADB/runtime smoke
are reported as `PENDING: tooling unavailable` when the required tools or
device are absent.
