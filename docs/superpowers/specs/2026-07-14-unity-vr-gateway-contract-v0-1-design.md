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

Runtime code references only Unity's core `UnityEngine` value types in the
OpenXR converter. All JSON encoding and decoding is performed by a dependency-free
structural formatter. It has no package dependencies. Tests use Unity Test
Framework NUnit through the test assembly definition only. No Unity project is
committed.

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

`session.start.requested_mode` is exactly `"head"`. In contrast,
`mode.set.mode` is an open wire string: it must be non-empty, non-whitespace,
and at most 64 characters, but an unfamiliar value is preserved for the Python
gateway to reject with `UNKNOWN_MODE`. Optional Unity helpers may recognize
`head`, `drive`, and `arm`; they must never rewrite or reject another valid raw
mode string. Output rejection codes remain a closed, strict wire vocabulary.

`sequence`, `timestamp_ms`, and `gateway_monotonic_ns` are `long`. Validation
accepts only integer JSON literals in the range `0..Int64.MaxValue`. Fractional
and exponent forms such as `1.0` and `1e3` are rejected even where their numeric
value is integral. Overflow is detected by the structural parser before DTO
construction. Command `sequence` must be at least one. Session sequence
generation fails explicitly at `Int64.MaxValue`; it never wraps.

### Output event correlation

Every output event carries a `Correlation` value. `Correlation` is an explicit
value type with `IsAvailable`, `SessionId`, and `Sequence` fields. `neck.target`
requires `IsAvailable == true`; the other event types allow
`Correlation.Unavailable`.

On the wire, `session_id` and `sequence` are always present. When correlation is
unavailable, both are serialized as JSON `null`, matching the Python
`dataclasses.asdict` output. When available, `session_id` is a non-empty,
non-whitespace string and `sequence` is an integer literal at least one.
Partial correlation (one field null and the other non-null) is rejected.

| Event | Required non-null fields | Correlation |
| --- | --- | --- |
| `gateway.state` | `schema_version`, `event_type`, `gateway_monotonic_ns`, `state` | optional; `null`/`null` when unavailable |
| `neck.target` | `schema_version`, `event_type`, `gateway_monotonic_ns`, `session_id`, `sequence`, `pan_degrees`, `tilt_degrees`, `hold` | required; never unavailable |
| `safety.stop` | `schema_version`, `event_type`, `gateway_monotonic_ns`, `reason`, `neck_action`, `base_action`, `arm_action` | optional; `null`/`null` when unavailable |
| `command.rejected` | `schema_version`, `event_type`, `gateway_monotonic_ns`, `code`, `message` | optional; `null`/`null` when unavailable |

## Strict JSON boundary

`JsonUtility` is not used. Each decode first passes through a dependency-free
structural validator which accepts JSON only when it has:

- exactly the required and allowed root fields for its discriminator;
- exactly the required and allowed payload fields for that command;
- permitted JSON token types for every field;
- no duplicate property names at any object level;
- no trailing JSON data;
- finite JSON numeric literals only; and
- the exact schema version plus an approved command or event discriminator.

The validator has fixed resource limits: input received as UTF-8 bytes may not
exceed 65,536 bytes, and string input may not exceed 65,536 UTF-16 code units.
No parsed object or array may exceed 16 nesting levels. Property names are
decoded before duplicate detection, so `"x"` and `"\\u0078"` are duplicates.
The parser rejects invalid Unicode escapes, malformed surrogate pairs, comments,
trailing commas, and multiple root values. It accepts only standard JSON number
grammar; JSON extensions are never accepted.

Decode proceeds in two passes:

1. The structural parser validates the complete JSON shape, schema, and
   discriminator.
2. The discriminator chooses one exact DTO. The JSON is deserialized into that
   DTO manually, then semantic validation checks IDs, bounds, enum mappings,
   quaternion length, and pose frame.

Serialization validates the DTO semantically before emitting JSON. The encoder
omits optional null fields (such as an absent `head.pose` position) and emits
explicit `null` for unavailable correlation identifiers. Deserialization failure
never creates a partially accepted command or event.

## OpenXR conversion

The conversion module is a pure quaternion operation and does not read the XR
runtime or use Euler angles. For a normalized Unity quaternion
`q_unity = (x, y, z, w)`, it emits exactly
`q_openxr = (-x, -y, z, w)`. This is the basis reflection `S = diag(1, 1, -1)`
with `R_openxr = S * R_unity * S`. It converts Unity's left-handed pose
convention (`+Z` forward) into the canonical `quest_local` OpenXR convention
(`+X` right, `+Y` up, `-Z` forward), normalizes the result, and rejects
zero-length or non-finite values. Quaternion/basis-vector fixtures are
authoritative.

Tests cover identity; positive and negative yaw/pitch/roll; combined rotations;
normalization; the equivalence of `q` and `-q`; zero relative orientation after
recenter; signed recenter-relative yaw and pitch; transformed right, up, and
forward basis vectors; and forward basis conversion. The expected yaw/pitch signs
match the Python gateway: positive relative yaw maps to positive pan and positive
relative pitch maps to positive tilt. `q` and `-q` are equivalent rotations:
tests compare transformed basis vectors or relative orientation, never raw
quaternion components. The wire contract does not canonicalize quaternion signs.

## Session helpers

Session helpers create non-empty, non-whitespace IDs and monotonically
increasing `long` sequence values for one client session. They do not validate
gateway safety, run timers, make network requests, or clear an emergency-stop
latch.

## Tests and validation

NUnit fixtures include exhaustive JSON round trips for every command and event,
plus strict negatives for missing, extra, and duplicate fields at every object
level; wrong token types; `NaN`/infinity attempts; zero-length and non-finite
quaternions; unsupported schema; unknown command, event, mode, and rejection
code; null, empty, whitespace-only, and over-limit identifiers and modes; invalid
integer grammar; and trailing data, comments, and malformed escapes.
Deterministic quaternion fixtures are copied from the Python gateway cases as
literal data so the Unity package remains self-contained.

The package is validated in an ephemeral, untracked Unity test host project.
That host is created outside the repository, imports this package by local path,
and runs only runtime NUnit fixtures. It is never committed.

## Explicit exclusions

This slice adds no scenes, XR Interaction Toolkit UI, controller bindings,
networking, rosbridge, ROS, WebRTC, Astra media, serial access, base control,
arm control, neck servo control, or other hardware access. A later thin Pi5
ROS 2/rosbridge adapter receives only already-validated messages and cannot
replace the Python gateway's safety decisions.
