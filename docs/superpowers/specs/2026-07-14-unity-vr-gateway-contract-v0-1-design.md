# Unity VR Gateway Contract v0.1 Design

## Purpose

Deliver `unity/Valera.VrGateway` as a reusable Unity package that implements
the client-side, transport-neutral VR Gateway v0.1 wire contract. The package
does not connect to ROS, a network, XR runtime APIs, hardware, or a Unity scene.
It can be imported unchanged into a later Quest 3 application.

## Package layout

```text
unity/Valera.VrGateway/
  package.json
  README.md
  Runtime/
    Valera.VrGateway.Runtime.asmdef
    Contracts/
    Json/
    OpenXr/
    Session/
  Tests/Runtime/
    Valera.VrGateway.Runtime.Tests.asmdef
```

Runtime code references only Unity's core `UnityEngine` value types and
`JsonUtility`; it has no package dependencies. Tests use Unity Test Framework
NUnit through the test assembly definition only. No Unity project is committed.

## Wire models

Every wire DTO is `[Serializable]`, uses public fields, preserves exact
snake_case field names, and contains no behavior or safety decisions. The DTOs
mirror the Python v0.1 input commands and output events:

- commands: `session.start`, `session.stop`, `mode.set`, `head.pose`,
  `head.recenter`, `emergency_stop`
- events: `gateway.state`, `neck.target`, `safety.stop`, `command.rejected`
- exact schema version: `"0.1"`

Wire enumerations are strings. A dedicated mapping layer maps approved strings
to internal C# enums and rejects unknown values. C# enum serialization is never
used for wire data.

`sequence`, `timestamp_ms`, and `gateway_monotonic_ns` are `long`. Validation
requires non-negative values and the command sequence requires a value of at
least one.

## Strict JSON boundary

`JsonUtility` is not a trust boundary. Each decode first passes through a
dependency-free structural validator which accepts JSON only when it has:

- exactly the required and allowed root fields for its discriminator;
- exactly the required and allowed payload fields for that command;
- permitted JSON token types for every field;
- no duplicate property names at any object level;
- no trailing JSON data;
- finite JSON numeric literals only; and
- the exact schema version plus an approved command or event discriminator.

Decode proceeds in two passes:

1. The validator parses a minimal header and validates its schema/discriminator.
2. The discriminator chooses one exact DTO. The full JSON is deserialized into
   that DTO with `JsonUtility`, then semantic validation checks IDs, bounds,
   enum mappings, quaternion length, and pose frame.

Serialization validates the DTO semantically before emitting JSON. Deserialization
failure never creates a partially accepted command or event.

## OpenXR conversion

The conversion module is a pure quaternion operation and does not read the XR
runtime or use Euler angles. It converts Unity's left-handed pose convention
(`+Z` forward) into the canonical `quest_local` OpenXR convention (`+X` right,
`+Y` up, `-Z` forward), normalizes the result, and rejects zero-length or
non-finite values. Quaternion/basis-vector fixtures are authoritative.

Tests cover identity; positive and negative yaw/pitch; roll; normalization;
the equivalence of `q` and `-q`; recenter-relative orientation; and forward
basis conversion. The expected yaw/pitch signs match the Python gateway:
positive relative yaw maps to positive pan and positive relative pitch maps to
positive tilt.

## Session helpers

Session helpers create non-empty IDs and monotonically increasing `long`
sequence values for one client session. They do not validate gateway safety,
run timers, make network requests, or clear an emergency-stop latch.

## Tests and validation

NUnit fixtures include JSON round trips and negatives for missing, extra, and
duplicate fields; wrong token types; `NaN`/infinity attempts; zero-length
quaternions; unsupported schema; and unknown command, event, mode, and
rejection code. Deterministic quaternion fixtures are copied from the Python
gateway cases as literal data so the Unity package remains self-contained.

The package is validated in an ephemeral, untracked Unity test host project.
That host is created outside the repository, imports this package by local path,
and runs only runtime NUnit fixtures. It is never committed.

## Explicit exclusions

This slice adds no scenes, XR Interaction Toolkit UI, controller bindings,
networking, rosbridge, ROS, WebRTC, Astra media, serial access, base control,
arm control, neck servo control, or other hardware access. A later thin Pi5
ROS 2/rosbridge adapter receives only already-validated messages and cannot
replace the Python gateway's safety decisions.
