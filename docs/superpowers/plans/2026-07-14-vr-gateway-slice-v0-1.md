# VR Gateway Slice v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a transport-neutral, simulation-only VR gateway core that safely accepts HEAD commands, emits bounded neck targets, and fails closed on invalid sessions, watchdog expiry, or emergency stop.

**Architecture:** Add a focused `robot.vr_gateway` package with validated project-owned messages, a deterministic quaternion/neck controller, a stateful safety gateway, and an in-memory simulation sink. ROS, Unity, networking, real servos, base control, arm control, and gripper control remain outside this slice.

**Tech Stack:** Python 3.12 standard library (`dataclasses`, `enum`, `math`, `time`, `typing`), pytest 7–8, existing Valera Control Tower local CI.

## Global Constraints

- Schema version is exactly `0.1`.
- `quest_local` is right-handed OpenXR: `+X` right, `+Y` up, forward `-Z`; quaternions use `x,y,z,w`.
- Only HEAD is executable; DRIVE and ARM always return `MODE_BLOCKED`.
- Client sequence strictly increases; client `timestamp_ms` is non-decreasing.
- Handshake timeout is 10 seconds in `AWAITING_RECENTER` and emits no actuator stop.
- Motion watchdog is 250 milliseconds and runs only in `HEAD_ACTIVE` using gateway-local `time.monotonic_ns()`.
- Emergency stop is accepted despite session or ordering errors, repeats `safety.stop` on every call, and can be cleared only by restarting the gateway process.
- No real mechanical values are inferred. All neck centers, gains, limits, rates, filter constants, and simulation initial targets are explicit configuration.
- No ROS, WebSocket, serial, LeRobot, Unity, servo, base, arm, or gripper dependency enters `robot/vr_gateway`.
- Existing unrelated worktree changes are preserved and excluded from VR gateway commits.

---

## File Structure

- `robot/vr_gateway/messages.py` — schema constants, enums, immutable payloads/envelopes/events, shape validation.
- `robot/vr_gateway/neck.py` — quaternion math, relative yaw/pitch, filtering, gain, rate limit, clamp.
- `robot/vr_gateway/gateway.py` — state machine, session/order gates, semantic mode routing, handshake timer, watchdog, E-stop.
- `robot/vr_gateway/simulation.py` — explicit simulation profile and output collector.
- `robot/vr_gateway/__init__.py` — public package exports only.
- `tests/test_vr_gateway_messages.py` — contract and payload tests.
- `tests/test_vr_gateway_neck.py` — deterministic neck-control tests.
- `tests/test_vr_gateway_gateway.py` — lifecycle and safety tests.
- `tests/test_vr_gateway_simulation.py` — complete simulation flow and dependency boundary.
- `scripts/run_vr_gateway_simulation.py` — repeatable JSON-output validation run.
- `README.md` — scope and invocation for the simulation slice.

---

### Task 1: Versioned Transport-Neutral Message Contract

**Files:**

- Create: `robot/vr_gateway/messages.py`
- Create: `robot/vr_gateway/__init__.py`
- Test: `tests/test_vr_gateway_messages.py`

**Interfaces:**

- Produces: `CommandEnvelope`, `SessionStartPayload`, `ModeSetPayload`, `PosePayload`, `EmptyPayload`, `Quaternion`, `Position`.
- Produces: `CommandName`, `EventName`, `GatewayState`, `RejectionCode`, `StopReason`, `GatewayStateEvent`, `NeckTargetEvent`, `SafetyStopEvent`, `CommandRejectedEvent`, `OutputEvent`.
- Produces: `MessageValidationError` for message-shape errors before gateway routing.

- [ ] **Step 1: Write failing message validation tests**

Create `tests/test_vr_gateway_messages.py` with focused tests:

```python
import math

import pytest

from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    MessageValidationError,
    ModeSetPayload,
    PosePayload,
    Quaternion,
)


def test_envelope_requires_schema_0_1_and_positive_sequence():
    with pytest.raises(MessageValidationError, match="schema_version"):
        CommandEnvelope("0.2", CommandName.MODE_SET, "session-a", 1, 10, ModeSetPayload("head"))
    with pytest.raises(MessageValidationError, match="sequence"):
        CommandEnvelope("0.1", CommandName.MODE_SET, "session-a", 0, 10, ModeSetPayload("head"))


def test_mode_payload_accepts_unknown_nonempty_string_for_gateway_semantics():
    assert ModeSetPayload("banana").mode == "banana"
    with pytest.raises(MessageValidationError, match="mode"):
        ModeSetPayload("")


def test_pose_requires_quest_local_and_finite_nonzero_quaternion():
    with pytest.raises(MessageValidationError, match="frame"):
        PosePayload("unity_world", Quaternion(0.0, 0.0, 0.0, 1.0))
    with pytest.raises(MessageValidationError, match="finite"):
        Quaternion(math.nan, 0.0, 0.0, 1.0)
    with pytest.raises(MessageValidationError, match="zero"):
        Quaternion(0.0, 0.0, 0.0, 0.0)


def test_quaternion_normalized_returns_unit_value():
    value = Quaternion(0.0, 0.0, 0.0, 2.0).normalized()
    assert value == Quaternion(0.0, 0.0, 0.0, 1.0)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_messages.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'robot.vr_gateway'`.

- [ ] **Step 3: Implement immutable message and event models**

Create `robot/vr_gateway/messages.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from typing import TypeAlias

SCHEMA_VERSION = "0.1"
QUEST_LOCAL_FRAME = "quest_local"


class MessageValidationError(ValueError):
    pass


class CommandName(str, Enum):
    SESSION_START = "session.start"
    SESSION_STOP = "session.stop"
    MODE_SET = "mode.set"
    HEAD_POSE = "head.pose"
    HEAD_RECENTER = "head.recenter"
    EMERGENCY_STOP = "emergency_stop"


class GatewayState(str, Enum):
    IDLE = "IDLE"
    AWAITING_RECENTER = "AWAITING_RECENTER"
    HEAD_ACTIVE = "HEAD_ACTIVE"
    SAFE_STOPPED = "SAFE_STOPPED"
    ESTOP_LATCHED = "ESTOP_LATCHED"


class RejectionCode(str, Enum):
    STALE_SEQUENCE = "STALE_SEQUENCE"
    STALE_TIMESTAMP = "STALE_TIMESTAMP"
    SESSION_MISMATCH = "SESSION_MISMATCH"
    NO_ACTIVE_SESSION = "NO_ACTIVE_SESSION"
    MODE_BLOCKED = "MODE_BLOCKED"
    UNKNOWN_MODE = "UNKNOWN_MODE"
    WATCHDOG_ACTIVE = "WATCHDOG_ACTIVE"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    ESTOP_LATCHED = "ESTOP_LATCHED"


class StopReason(str, Enum):
    WATCHDOG = "WATCHDOG"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SESSION_STOPPED = "SESSION_STOPPED"


class EventName(str, Enum):
    GATEWAY_STATE = "gateway.state"
    NECK_TARGET = "neck.target"
    SAFETY_STOP = "safety.stop"
    COMMAND_REJECTED = "command.rejected"


@dataclass(frozen=True)
class Quaternion:
    x: float
    y: float
    z: float
    w: float

    def __post_init__(self) -> None:
        if not all(isfinite(value) for value in (self.x, self.y, self.z, self.w)):
            raise MessageValidationError("quaternion values must be finite")
        if self.norm <= 1e-12:
            raise MessageValidationError("quaternion must not be zero length")

    @property
    def norm(self) -> float:
        return sqrt(self.x * self.x + self.y * self.y + self.z * self.z + self.w * self.w)

    def normalized(self) -> "Quaternion":
        norm = self.norm
        return Quaternion(self.x / norm, self.y / norm, self.z / norm, self.w / norm)


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        if not all(isfinite(value) for value in (self.x, self.y, self.z)):
            raise MessageValidationError("position values must be finite")


@dataclass(frozen=True)
class SessionStartPayload:
    requested_mode: str

    def __post_init__(self) -> None:
        if not self.requested_mode:
            raise MessageValidationError("requested_mode is required")


@dataclass(frozen=True)
class ModeSetPayload:
    mode: str

    def __post_init__(self) -> None:
        if not self.mode:
            raise MessageValidationError("mode is required")


@dataclass(frozen=True)
class PosePayload:
    frame: str
    orientation: Quaternion
    position: Position | None = None

    def __post_init__(self) -> None:
        if self.frame != QUEST_LOCAL_FRAME:
            raise MessageValidationError("frame must be quest_local")


@dataclass(frozen=True)
class EmptyPayload:
    pass


Payload: TypeAlias = SessionStartPayload | ModeSetPayload | PosePayload | EmptyPayload


@dataclass(frozen=True)
class CommandEnvelope:
    schema_version: str
    command: CommandName
    session_id: str
    sequence: int
    timestamp_ms: int
    payload: Payload

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise MessageValidationError("schema_version must be 0.1")
        if not self.session_id:
            raise MessageValidationError("session_id is required")
        if self.sequence < 1:
            raise MessageValidationError("sequence must be at least 1")
        if self.timestamp_ms < 0:
            raise MessageValidationError("timestamp_ms must be non-negative")


@dataclass(frozen=True)
class GatewayStateEvent:
    gateway_monotonic_ns: int
    state: GatewayState
    session_id: str | None
    sequence: int | None
    schema_version: str = SCHEMA_VERSION
    event_type: EventName = EventName.GATEWAY_STATE


@dataclass(frozen=True)
class NeckTargetEvent:
    gateway_monotonic_ns: int
    session_id: str
    sequence: int
    pan_degrees: float
    tilt_degrees: float
    hold: bool = False
    schema_version: str = SCHEMA_VERSION
    event_type: EventName = EventName.NECK_TARGET


@dataclass(frozen=True)
class SafetyStopEvent:
    gateway_monotonic_ns: int
    reason: StopReason
    session_id: str | None
    sequence: int | None
    neck_action: str = "HOLD_LAST_POSITION"
    base_action: str = "STOP"
    arm_action: str = "HOLD"
    schema_version: str = SCHEMA_VERSION
    event_type: EventName = EventName.SAFETY_STOP


@dataclass(frozen=True)
class CommandRejectedEvent:
    gateway_monotonic_ns: int
    code: RejectionCode
    message: str
    session_id: str | None
    sequence: int | None
    schema_version: str = SCHEMA_VERSION
    event_type: EventName = EventName.COMMAND_REJECTED


OutputEvent: TypeAlias = GatewayStateEvent | NeckTargetEvent | SafetyStopEvent | CommandRejectedEvent
```

Create `robot/vr_gateway/__init__.py` with no wildcard imports:

```python
"""Transport-neutral VR gateway core."""
```

- [ ] **Step 4: Run the message tests and full suite**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_messages.py -v
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

Expected: message tests pass; existing suite remains green.

- [ ] **Step 5: Commit the contract**

```bash
git add robot/vr_gateway/__init__.py robot/vr_gateway/messages.py tests/test_vr_gateway_messages.py
git commit -m "feat: add VR gateway message contract"
```

---

### Task 2: Deterministic HEAD/NECK Controller

**Files:**

- Create: `robot/vr_gateway/neck.py`
- Test: `tests/test_vr_gateway_neck.py`

**Interfaces:**

- Consumes: normalized `Quaternion` from Task 1.
- Produces: `NeckControlConfig`, `NeckTarget`, and `NeckController.recenter()` / `NeckController.update()`.
- Invariant: recenter emits no target; `update()` applies filter → gain → rate limit → clamp.

- [ ] **Step 1: Write failing quaternion and safety-pipeline tests**

Create tests using a helper that builds axis-angle quaternions. Cover identity,
`+30°` yaw, `+20°` pitch, recenter-relative deltas, zero target after recenter,
low-pass response at a deterministic delta, independent pan/tilt gain, per-axis
rate limit, mechanical clamp, and active recenter retaining `last_target`.

The core assertions are:

```python
controller.recenter(axis_angle("y", 10.0), now_ns=0)
target = controller.update(axis_angle("y", 40.0), now_ns=1_000_000_000)
assert target.pan_degrees == pytest.approx(30.0)

controller.recenter(axis_angle("y", 40.0), now_ns=1_000_000_000, preserve_target=True)
assert controller.last_target == target
assert controller.update(axis_angle("y", 40.0), now_ns=2_000_000_000).pan_degrees == pytest.approx(target.pan_degrees)
```

Use a zero filter constant and high rate limits for pure quaternion mapping,
then separate fixtures with finite filter/rate values for each pipeline test.

- [ ] **Step 2: Run the neck tests and verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_neck.py -v
```

Expected: collection fails because `robot.vr_gateway.neck` does not exist.

- [ ] **Step 3: Implement quaternion-relative control**

Create `robot/vr_gateway/neck.py` with these exact public data shapes:

```python
@dataclass(frozen=True)
class NeckControlConfig:
    center_pan_degrees: float
    center_tilt_degrees: float
    initial_pan_degrees: float
    initial_tilt_degrees: float
    pan_gain: float
    tilt_gain: float
    filter_time_constant_seconds: float
    max_pan_rate_degrees_per_second: float
    max_tilt_rate_degrees_per_second: float
    min_pan_degrees: float
    max_pan_degrees: float
    min_tilt_degrees: float
    max_tilt_degrees: float


@dataclass(frozen=True)
class NeckTarget:
    pan_degrees: float
    tilt_degrees: float
```

Add `NeckController.__init__(config: NeckControlConfig)`, read-only
`last_target: NeckTarget`,
`recenter(orientation: Quaternion, now_ns: int, preserve_target: bool = False) -> None`,
and `update(orientation: Quaternion, now_ns: int) -> NeckTarget` with no other
public motion methods.

Implement quaternion inverse/multiply internally. Rotate canonical forward
`(0, 0, -1)` by the relative quaternion, then calculate:

```python
yaw = atan2(-forward_x, -forward_z)
pitch = atan2(forward_y, hypot(forward_x, forward_z))
```

Use `alpha = 1.0` when the filter time constant is zero; otherwise use
`1.0 - exp(-dt_seconds / tau_seconds)`. Rate-limit from `last_target` with
`max_delta = configured_rate * dt_seconds`, then clamp to each configured
mechanical interval. Validate finite config values, ordered min/max values,
non-negative filter constant, and positive rate limits.

- [ ] **Step 4: Run neck and full tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_neck.py -v
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

Expected: all neck cases and the existing suite pass.

- [ ] **Step 5: Commit the controller**

```bash
git add robot/vr_gateway/neck.py tests/test_vr_gateway_neck.py
git commit -m "feat: add bounded simulated neck controller"
```

---

### Task 3: Session Lifecycle, Mode Gates, And Recenter Handshake

**Files:**

- Create: `robot/vr_gateway/gateway.py`
- Test: `tests/test_vr_gateway_gateway.py`

**Interfaces:**

- Consumes: Task 1 command/event models and Task 2 `NeckController`.
- Produces: `GatewayConfig` and `VrGateway.handle(command) -> tuple[OutputEvent, ...]`.
- Produces: `VrGateway.poll() -> tuple[OutputEvent, ...]` for timer evaluation without incoming traffic.

- [ ] **Step 1: Write failing lifecycle tests with an injected fake clock**

Use:

```python
class FakeClock:
    def __init__(self):
        self.now_ns = 0
    def __call__(self) -> int:
        return self.now_ns
    def advance_ms(self, value: int) -> None:
        self.now_ns += value * 1_000_000
```

Cover these independent behaviors:

- `session.start` requires sequence 1, a new ID, `requested_mode="head"`, and emits one transition to `AWAITING_RECENTER`.
- an unknown `requested_mode` reaches gateway semantics and returns `UNKNOWN_MODE`.
- repeated session ID returns `INVALID_PAYLOAD`.
- a new session ID invalidates the previous session.
- missing and mismatched sessions return `NO_ACTIVE_SESSION` and `SESSION_MISMATCH`.
- same `timestamp_ms` with a higher sequence is accepted.
- lower timestamp returns `STALE_TIMESTAMP`; repeated/lower sequence returns `STALE_SEQUENCE`.
- a command with the wrong payload model returns `INVALID_PAYLOAD` with a bounded static message that does not contain payload data.
- `mode.set("drive")` and `mode.set("arm")` return `MODE_BLOCKED`.
- `mode.set("banana")` reaches gateway semantics and returns `UNKNOWN_MODE`.
- the first recenter transitions to `HEAD_ACTIVE` without a neck target.
- active recenter stays `HEAD_ACTIVE`, emits no state/target, and preserves the last target.
- `session.stop` transitions to `IDLE` and emits `SESSION_STOPPED` with hold/stop/hold actions.
- after 10,000 ms in `AWAITING_RECENTER`, `poll()` emits only an `IDLE` state event and no `SafetyStopEvent`.
- `gateway.state` is absent when a valid command leaves state unchanged.

- [ ] **Step 2: Run lifecycle tests and verify RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_gateway.py -v
```

Expected: collection fails because `robot.vr_gateway.gateway` does not exist.

- [ ] **Step 3: Implement the gateway lifecycle and semantic routing**

Create `GatewayConfig` with nanosecond defaults:

```python
@dataclass(frozen=True)
class GatewayConfig:
    handshake_timeout_ns: int = 10_000_000_000
    motion_watchdog_timeout_ns: int = 250_000_000
```

Create `VrGateway(neck_controller, clock=time.monotonic_ns, config=GatewayConfig())`.
Store `state`, `used_session_ids`, active session fields,
`session_started_monotonic_ns`, and `last_valid_packet_received_monotonic_ns`.

Route in this order:

1. validate E-stop payload shape and dispatch E-stop before session/order gates
2. dispatch `session.start`, rejecting E-stop latch and reused IDs
3. reject `SAFE_STOPPED` traffic with `WATCHDOG_ACTIVE`
4. reject absent/mismatched sessions
5. check strictly increasing sequence and non-decreasing timestamp
6. validate the command-specific payload class
7. apply HEAD-only semantic mode routing
8. update accepted ordering/timer state

Use a private `_transition()` helper that returns a `GatewayStateEvent` only
when the state changes. Use a bounded static rejection message per code; never
format the incoming payload into the message.

- [ ] **Step 4: Run lifecycle and full tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_gateway.py -v
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

Expected: session, ordering, modes, handshake, and active recenter tests pass.

- [ ] **Step 5: Commit lifecycle behavior**

```bash
git add robot/vr_gateway/gateway.py tests/test_vr_gateway_gateway.py
git commit -m "feat: add VR gateway session lifecycle"
```

---

### Task 4: Motion Watchdog And Latched Emergency Stop

**Files:**

- Modify: `robot/vr_gateway/gateway.py`
- Modify: `tests/test_vr_gateway_gateway.py`

**Interfaces:**

- Extends: `VrGateway.poll()` with one-shot HEAD motion timeout behavior.
- Extends: `VrGateway.handle()` with unconditional, repeatable E-stop handling.

- [ ] **Step 1: Add failing watchdog tests**

Test that after recenter and a valid pose:

```python
clock.advance_ms(249)
assert gateway.poll() == ()
clock.advance_ms(1)
events = gateway.poll()
assert [type(event) for event in events] == [GatewayStateEvent, SafetyStopEvent]
assert events[0].state is GatewayState.SAFE_STOPPED
assert events[1].reason is StopReason.WATCHDOG
assert events[1].neck_action == "HOLD_LAST_POSITION"
assert gateway.poll() == ()
```

Also prove that rejected stale, blocked-mode, and malformed commands do not
refresh the watchdog, and that expired-session traffic returns
`WATCHDOG_ACTIVE` without producing a target.

- [ ] **Step 2: Run the focused watchdog tests and verify RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_gateway.py -k watchdog -v
```

Expected: failures show missing timeout events or incorrect timer refresh.

- [ ] **Step 3: Implement the one-shot motion watchdog**

In `poll()`, evaluate handshake timeout only in `AWAITING_RECENTER` and motion
watchdog only in `HEAD_ACTIVE`. On motion expiry, invalidate the active session,
transition once to `SAFE_STOPPED`, and append exactly one `SafetyStopEvent` with
`StopReason.WATCHDOG`. Later polls return an empty tuple.

- [ ] **Step 4: Add failing E-stop tests**

Cover E-stop:

- without an active session
- with stale sequence and timestamp
- from a mismatched session
- while already latched
- after a watchdog
- followed by `session.start`, which must return `ESTOP_LATCHED`
- with a non-empty payload, which must return `INVALID_PAYLOAD` rather than latch

Assert every E-stop call yields `SafetyStopEvent`; only the first yields an
additional `GatewayStateEvent`; no call yields `NeckTargetEvent`.

- [ ] **Step 5: Run E-stop tests and verify RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_gateway.py -k estop -v
```

Expected: failures show missing latch or repeated stop behavior.

- [ ] **Step 6: Implement latched E-stop**

Handle E-stop before ordinary session/order checks. Invalidate the active
session, transition to `ESTOP_LATCHED` if needed, and append a fresh
`SafetyStopEvent(StopReason.EMERGENCY_STOP)` on every valid E-stop envelope.
Do not implement a reset method or command. A fresh `VrGateway` instance is the
only v0.1 reset path.

- [ ] **Step 7: Run gateway and full tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_gateway.py -v
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

Expected: all lifecycle, watchdog, and E-stop cases pass with no warnings.

- [ ] **Step 8: Commit safety timers and E-stop**

```bash
git add robot/vr_gateway/gateway.py tests/test_vr_gateway_gateway.py
git commit -m "feat: enforce VR watchdog and emergency stop"
```

---

### Task 5: Simulation Flow, Structured Output, And Dependency Boundary

**Files:**

- Create: `robot/vr_gateway/simulation.py`
- Create: `tests/test_vr_gateway_simulation.py`
- Create: `scripts/run_vr_gateway_simulation.py`
- Modify: `robot/vr_gateway/__init__.py`
- Modify: `README.md`

**Interfaces:**

- Produces: `build_simulated_vr_gateway(clock)` with explicitly labeled simulation values.
- Produces: `run_simulated_head_sequence()` returning JSON-serializable event dictionaries.
- Produces: a repeatable CLI that prints newline-delimited JSON and never opens network or hardware resources.

- [ ] **Step 1: Write the failing end-to-end simulation test**

The test runs:

```text
session.start -> head.recenter -> head.pose -> neck.target
-> advance 250 ms -> safety.stop(HOLD_LAST_POSITION)
```

Assert event ordering, schema `0.1`, bounded target values, `SAFE_STOPPED`, and
the absence of any base/arm target event. Add a source-boundary test that scans
all `robot/vr_gateway/*.py` imports and fails if it finds `rclpy`, `roslibpy`,
`websockets`, `serial`, `lerobot`, `socket`, or camera/servo SDK imports.

- [ ] **Step 2: Run the simulation test and verify RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_simulation.py -v
```

Expected: collection fails because `robot.vr_gateway.simulation` does not exist.

- [ ] **Step 3: Implement the explicit simulation profile and flow**

Use named simulation-only values:

```python
SIMULATION_NECK_CONFIG = NeckControlConfig(
    center_pan_degrees=0.0,
    center_tilt_degrees=0.0,
    initial_pan_degrees=0.0,
    initial_tilt_degrees=0.0,
    pan_gain=1.0,
    tilt_gain=1.0,
    filter_time_constant_seconds=0.08,
    max_pan_rate_degrees_per_second=30.0,
    max_tilt_rate_degrees_per_second=20.0,
    min_pan_degrees=-30.0,
    max_pan_degrees=30.0,
    min_tilt_degrees=-20.0,
    max_tilt_degrees=20.0,
)
```

Document in the module that these are deterministic fixtures, not measured
Valera servo limits. Serialize dataclass events with `dataclasses.asdict()` and
convert enums to their string values in one explicit helper.

- [ ] **Step 4: Add the repeatable runner and README instructions**

Create `scripts/run_vr_gateway_simulation.py` with a `main()` that executes the
deterministic flow and writes each event using
`json.dumps(event_dictionary, sort_keys=True)`.
Add a README section containing:

```bash
python3 scripts/run_vr_gateway_simulation.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_*.py -v
```

State plainly that no ROS, network, base, arm, gripper, or real neck device is
opened and that simulation angles are not hardware calibration.

- [ ] **Step 5: Run focused tests, runner, and full suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_*.py -v
python3 scripts/run_vr_gateway_simulation.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

Expected: all VR tests and existing tests pass; runner prints the deterministic
state/target/watchdog event chain as valid JSON lines.

- [ ] **Step 6: Verify the package has no forbidden dependencies**

```bash
rg -n "\b(rclpy|roslibpy|websockets|serial|lerobot|socket|cv2)\b" robot/vr_gateway
```

Expected: no matches and exit status 1.

- [ ] **Step 7: Commit simulation and documentation**

```bash
git add robot/vr_gateway/__init__.py robot/vr_gateway/simulation.py tests/test_vr_gateway_simulation.py scripts/run_vr_gateway_simulation.py README.md
git commit -m "feat: add VR gateway simulation flow"
```

---

## Final Verification

- [ ] Run whitespace and repository status checks:

```bash
git diff --check
git status --short
```

- [ ] Run all VR gateway tests independently:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_*.py -v
```

- [ ] Run the entire stable suite:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

- [ ] Run the simulation CLI twice and confirm byte-for-byte deterministic output:

```bash
python3 scripts/run_vr_gateway_simulation.py > /tmp/valera-vr-run-1.jsonl
python3 scripts/run_vr_gateway_simulation.py > /tmp/valera-vr-run-2.jsonl
cmp /tmp/valera-vr-run-1.jsonl /tmp/valera-vr-run-2.jsonl
```

Expected: `cmp` exits 0. The `/tmp` files are not added to git.

- [ ] Inspect the final diff against the approved design and confirm every v0.1 requirement has direct test evidence before claiming the slice complete.
