# VR Gateway Slice v0.1 Design

Date: 2026-07-14

## Purpose

Build the first safe, transport-neutral slice of `valera_vr_gateway` for a
native Meta Quest 3 application using Unity, OpenXR, and the Unity Input System.
This slice proves the command contract and HEAD/NECK control semantics entirely
in simulation. It does not access ROS, the network, servos, the tracked base, or
the SO-101 arm.

The gateway core lives in this repository. A later ROS 2 Jazzy adapter in the
Pi5 workspace will translate rosbridge messages to and from the core models. It
must not duplicate or override gateway safety decisions.

## Slice Scope

Included:

- versioned, transport-neutral input and output messages
- explicit session lifecycle and replay protection
- relative HEAD/NECK control from headset quaternion poses
- recentering without automatic movement
- configurable filtering, gain, rate limits, and mechanical limits
- local monotonic watchdog
- latched emergency stop
- structured rejection reasons
- deterministic simulation and tests

Explicitly excluded:

- ROS 2 nodes, topics, rosbridge, or WebSocket connections
- Unity project code
- Astra video and WebRTC
- tracked-base movement
- arm movement, inverse kinematics, and torque enablement
- gripper commands
- any real hardware adapter

DRIVE and ARM commands are part of the mode vocabulary so clients receive an
explicit `MODE_BLOCKED` rejection. They are never executed in v0.1.

## Architecture

The gateway is divided into focused modules:

- `robot/vr_gateway/messages.py` owns message enums, validated payload models,
  rejection codes, and output event models.
- `robot/vr_gateway/neck.py` owns quaternion-to-relative-angle conversion and
  the deterministic filter, gain, rate-limit, and mechanical-limit pipeline.
- `robot/vr_gateway/gateway.py` owns session state, mode gates, watchdog,
  emergency-stop latch, and fail-closed command routing.
- `robot/vr_gateway/simulation.py` provides in-memory HEAD/NECK output capture.
  Its base and arm endpoints remain explicitly blocked.

The core accepts already-decoded project-owned message objects. Transport
adapters may parse JSON or ROS messages, but they cannot decide whether a
command is safe, clear an emergency stop, calculate neck targets, or bypass a
rejection.

```text
Unity Quest client
  -> versioned command payload
  -> future rosbridge transport adapter
  -> VrGateway.handle(command)
       -> session and safety validation
       -> NeckController for allowed HEAD commands
       -> output events
  -> simulation sink now / guarded hardware adapter later
```

## Coordinate Contract

`head.pose` and `head.recenter` use the canonical OpenXR Cartesian frame:

- `frame` is exactly `quest_local`
- the frame is right-handed
- `+X` points right
- `+Y` points up
- forward points along `-Z`
- orientation is a normalized quaternion with fields `x`, `y`, `z`, `w`

Unity uses a different handedness. The Unity client is responsible for
converting its tracked pose into this canonical contract before serialization.
The future Unity implementation must have fixture tests for that conversion.

Positive relative yaw turns the view left. Positive relative pitch turns the
view up. The v0.1 mapping is:

```text
positive relative yaw   -> positive neck pan
positive relative pitch -> positive neck tilt
```

Position is optional and ignored by v0.1. It remains available for future ARM
and spatial-overlay work without changing the pose envelope.

## Input Envelope

Every input command has:

```text
schema_version: "0.1"
command: one of the approved command names
session_id: non-empty string
sequence: integer >= 1
timestamp_ms: integer >= 0
payload: command-specific object
```

The approved commands are:

```text
session.start
session.stop
mode.set
head.pose
head.recenter
emergency_stop
```

`timestamp_ms` is the client's monotonic sample time within a session. It is
not assumed to share an epoch or clock with the gateway. The gateway uses it to
reject time regression and for diagnostics only.

### Command payloads

`session.start`:

```text
requested_mode: "head"
```

Only `head` is accepted. The first command for a new session has `sequence = 1`.

`mode.set`:

```text
mode: "head" | "drive" | "arm"
```

`drive` and `arm` are always rejected with `MODE_BLOCKED` in v0.1. An unknown
mode is rejected with `UNKNOWN_MODE`.

`head.recenter`:

```text
frame: "quest_local"
orientation: {x, y, z, w}
```

The orientation is captured at the recenter action and sent atomically with the
command. Recenter does not depend on a previously received pose.

`head.pose`:

```text
frame: "quest_local"
orientation: {x, y, z, w}
position: optional {x, y, z}
```

`session.stop` has an empty payload and safely invalidates the active session.

`emergency_stop` has an empty payload. It is accepted regardless of session,
mode, sequence, timestamp, watchdog state, or an existing emergency-stop latch.

## Output Events

The gateway returns zero or more structured events:

```text
gateway.state
neck.target
safety.stop
command.rejected
```

Every event contains `schema_version`, gateway-local monotonic event time, and
the related `session_id` and `sequence` when available. The gateway clock field
is named `gateway_monotonic_ns` and is never compared with client time.

`neck.target` contains:

```text
pan_degrees
tilt_degrees
hold: false
```

`safety.stop` contains:

```text
reason: "WATCHDOG" | "EMERGENCY_STOP" | "SESSION_STOPPED"
neck_action: "HOLD_LAST_POSITION"
base_action: "STOP"
arm_action: "HOLD"
```

This event describes the required safe action. The gateway never generates an
automatic return-to-center target.

`command.rejected` contains a stable machine code, a bounded human-readable
message, and the related envelope identifiers. It does not echo arbitrary input
payloads.

Approved rejection codes:

```text
STALE_SEQUENCE
STALE_TIMESTAMP
SESSION_MISMATCH
NO_ACTIVE_SESSION
MODE_BLOCKED
UNKNOWN_MODE
WATCHDOG_ACTIVE
INVALID_PAYLOAD
ESTOP_LATCHED
```

Unsupported schema versions and malformed envelopes use `INVALID_PAYLOAD` in
v0.1 so the rejection vocabulary remains small.

## Session Lifecycle

Gateway states are:

```text
IDLE
AWAITING_RECENTER
HEAD_ACTIVE
SAFE_STOPPED
ESTOP_LATCHED
```

The lifecycle is:

```text
IDLE
  -> session.start(new ID, sequence 1)
AWAITING_RECENTER
  -> head.recenter(valid quaternion)
HEAD_ACTIVE
  -> valid head.pose updates neck target
```

Each `session_id` must be unique for the lifetime of a gateway process. A used
ID cannot be started again, including after stop, watchdog, or emergency stop.
A repeated `session.start` with the same ID is rejected rather than treated as
idempotent. ID reuse is reported as `INVALID_PAYLOAD`; ordering codes remain
reserved for commands within a valid active session.

Starting a new session invalidates any previous active session. Packets for an
old or different session are rejected with `SESSION_MISMATCH`. Within the active
session, sequence numbers and client timestamps must strictly increase after
`session.start`; gaps in sequence are allowed.

`head.pose` is accepted only in `HEAD_ACTIVE`. Recenter is required after every
new session. A new valid session may leave `ESTOP_LATCHED`, but it transitions
only to `AWAITING_RECENTER`; it cannot produce motion until another explicit
recenter and pose are accepted.

## Watchdog

The gateway records `last_valid_packet_received_monotonic_ns` using an injected
clock backed by `time.monotonic_ns()` in production. Client time is never used
to measure the watchdog interval.

The watchdog timeout is 250 milliseconds. It is refreshed only by a command
that passes envelope, session, ordering, mode, and payload validation. Invalid
or rejected traffic cannot keep the session alive.

When the timeout expires in `AWAITING_RECENTER` or `HEAD_ACTIVE`, the gateway:

1. enters `SAFE_STOPPED`
2. invalidates the active session
3. emits exactly one `safety.stop` with `HOLD_LAST_POSITION`
4. emits no neck target

Recovery requires a `session.start` with a new unique ID followed by
`head.recenter`. The gateway never resumes from later packets of the expired
session.

## Emergency Stop

`emergency_stop` is handled before normal envelope ordering and session gates.
It is accepted:

- without an active session
- for an old or mismatched session
- with a stale sequence or timestamp
- in any mode or gateway state
- repeatedly

It invalidates the active session, enters `ESTOP_LATCHED`, and emits an
idempotent `safety.stop` requiring neck hold, base stop, and arm hold. It never
causes movement.

No command in the stopped session can clear the latch. In v0.1, only a new unique
`session.start` can transition from `ESTOP_LATCHED` to `AWAITING_RECENTER`.
Future guarded hardware integration may strengthen this with a separate
operator-confirmed reset command without weakening the v0.1 behavior.

## Neck Control Pipeline

`NeckController` receives the recenter quaternion and later pose quaternions. It
computes relative orientation, extracts yaw and pitch in the defined OpenXR
frame, and applies this pipeline in order:

1. exponential first-order low-pass filter using monotonic delta time
2. configured pan and tilt gain
3. configured maximum pan and tilt rate
4. configured mechanical minimum and maximum angles

The controller center, gains, filter time constant, rate limits, and mechanical
limits are explicit configuration. There are no real-hardware defaults. Tests
and the simulation runner may use clearly named simulation-only fixture values.

Invalid, non-finite, or zero-length quaternions are rejected with
`INVALID_PAYLOAD`. Accepted quaternions are normalized before use.

On the first pose after recenter, rate limiting starts from the configured servo
center. Recenter itself emits no target, preventing an implicit movement.

## Failure Semantics

Validation is fail-closed:

- malformed payloads produce no target
- stale or mismatched traffic cannot refresh the watchdog
- blocked modes produce explicit rejections
- watchdog and emergency-stop paths produce explicit safe-action events
- no error path returns the neck to center automatically
- no v0.1 path calls base, arm, gripper, ROS, network, or hardware APIs

The gateway reports facts and required safe actions. A later hardware adapter
must confirm execution separately; emitting `safety.stop` is not proof that a
physical actuator held position.

## Testing Strategy

Stable CI uses only deterministic unit and integration tests with an injected
monotonic clock.

Message tests cover:

- required envelope fields and schema version
- command-specific payload validation
- normalized finite quaternions and the fixed frame name
- all structured rejection codes

Session and gateway tests cover:

- first sequence is 1
- unique session IDs and rejection of ID reuse
- invalidation of old sessions
- strictly increasing sequence and client timestamp
- acceptance of sequence gaps
- HEAD-only mode and explicit DRIVE/ARM blocking
- recenter requirement before any target
- watchdog refresh only from valid packets
- one-shot watchdog stop and mandatory new-session recovery
- emergency stop without a session and despite stale ordering
- repeated emergency stop behavior
- no automatic latch clearing or return-to-center movement

Neck tests cover:

- known OpenXR quaternions mapping to signed yaw and pitch
- zero relative target immediately after recenter
- low-pass filter behavior under deterministic delta time
- pan and tilt gains
- per-axis rate limiting
- per-axis mechanical clamping
- invalid quaternion rejection

An integration test runs a complete simulated sequence:

```text
session.start -> head.recenter -> head.pose -> neck.target -> watchdog
-> safety.stop(HOLD_LAST_POSITION)
```

The test suite also asserts that the v0.1 package has no ROS, WebSocket, serial,
LeRobot, or hardware dependencies.

## Follow-on Slices

After v0.1 is verified:

1. add the native Unity/OpenXR client contract implementation and fixtures
2. add the thin ROS 2 Jazzy/rosbridge adapter on Pi5
3. connect HEAD output to two neck servos behind explicit hardware safety gates
4. add Astra H.264/WebRTC video as a separate media path
5. design DRIVE with grip deadman, immediate STOP, and RC override
6. design ARM joint jog, then bounded Cartesian DLS IK
7. enable the gripper only after mechanical rebuild and final calibration

The current SO-101 dataset block remains in force throughout the HEAD and DRIVE
slices. Initial ARM work remains unloaded with the gripper software-blocked.

## References

- [Meta Quest Touch Plus Controller Profile](https://docs.unity3d.com/Packages/com.unity.xr.openxr%401.16/manual/features/metaquesttouchpluscontrollerprofile.html)
- [OpenXR 1.1 Specification](https://registry.khronos.org/OpenXR/specs/1.1/html/xrspec.html)
- [GStreamer WebRTC documentation](https://gstreamer.freedesktop.org/documentation/webrtc/)
- [rosbridge_suite documentation](https://docs.ros.org/en/jazzy/p/rosbridge_suite/)
