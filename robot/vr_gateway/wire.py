"""Transport-neutral wire codec for the Unity VR Gateway v0.1 contract.

This is the only module that translates between raw JSON strings and the
project-owned DTOs in :mod:`robot.vr_gateway.messages`. It owns no session
state, no watchdog, no mode policy, and no hardware knowledge.

Decoding is strict fail-closed and exactly matches the merged Unity contract
(``docs/superpowers/specs/2026-07-14-unity-vr-gateway-contract-v0-1-design.md``):

- ``head.pose`` payload is exactly ``frame``, ``orientation``, optional
  ``position`` (absent or null).
- ``head.recenter`` payload is exactly ``frame``, ``orientation``; any
  ``position`` field is rejected.
- Resource limits: 65,536 UTF-16/Python characters, 65,536 UTF-8 bytes, and a
  maximum JSON nesting depth of 16.
- Integer fields are literal integers in ``0..Int64.MaxValue``
  (``9_223_372_036_854_775_807``); command ``sequence`` is ``1..Int64.MaxValue``.
- ``mode.set.mode`` is non-empty, non-whitespace, at most 64 characters.
- ``session.start.requested_mode`` is exactly ``"head"``.
- session identifiers are non-empty and non-whitespace.
- ``head.recenter`` and ``emergency_stop`` have no ``position`` field.
- duplicate decoded keys (including ``"x"`` vs. ``"\\u0078"``), ``NaN``/
  ``Infinity`` literals, malformed JSON, trailing documents, missing/extra
  fields, wrong token types, and unknown discriminators are rejected.
- standard leading/trailing JSON whitespace is preserved (the stdlib decoder
  already accepts it).

The caller is expected to route :class:`WireError` failures through
:class:`robot.vr_gateway.gateway.VrGateway.handle` so the gateway's existing
fail-closed path produces the safety event.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from math import isfinite
from typing import Any

from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    CommandRejectedEvent,
    EmptyPayload,
    EventName,
    GatewayState,
    GatewayStateEvent,
    MessageValidationError,
    ModeSetPayload,
    NeckTargetEvent,
    OutputEvent,
    PosePayload,
    Position,
    Quaternion,
    RejectionCode,
    SafetyStopEvent,
    SessionStartPayload,
    StopReason,
)

__all__ = [
    "MAX_INPUT_CHARACTERS",
    "MAX_INPUT_UTF8_BYTES",
    "MAX_JSON_DEPTH",
    "MAX_INT64",
    "MAX_MODE_LENGTH",
    "WireError",
    "decode_command",
    "encode_event",
    "encode_events",
]


class WireError(ValueError):
    """Raised when a raw JSON string cannot be decoded/encoded against the v0.1 contract."""


# Resource and scalar limits copied from the Unity v0.1 contract.
MAX_INPUT_CHARACTERS = 65_536
MAX_INPUT_UTF8_BYTES = 65_536
MAX_JSON_DEPTH = 16
MAX_INT64 = 9_223_372_036_854_775_807
MAX_MODE_LENGTH = 64

_COMMAND_BY_NAME: dict[str, CommandName] = {name.value: name for name in CommandName}
_EVENT_BY_NAME: dict[str, type] = {
    EventName.GATEWAY_STATE.value: GatewayStateEvent,
    EventName.NECK_TARGET.value: NeckTargetEvent,
    EventName.SAFETY_STOP.value: SafetyStopEvent,
    EventName.COMMAND_REJECTED.value: CommandRejectedEvent,
}
_STATE_BY_VALUE = {state.value: state for state in GatewayState}
_STOP_REASON_BY_VALUE = {reason.value: reason for reason in StopReason}
_REJECTION_CODE_BY_VALUE = {code.value: code for code in RejectionCode}
_EVENT_TYPE_BY_VALUE = {event.value: event for event in EventName}

_ENVELOPE_KEYS = frozenset(
    {
        "schema_version",
        "command",
        "session_id",
        "sequence",
        "timestamp_ms",
        "payload",
    }
)
_HEAD_POSE_KEYS = frozenset({"frame", "orientation", "position"})
_HEAD_RECENTER_KEYS = frozenset({"frame", "orientation"})
_QUATERNION_KEYS = frozenset({"x", "y", "z", "w"})
_POSITION_KEYS = frozenset({"x", "y", "z"})
_SESSION_START_KEYS = frozenset({"requested_mode"})
_MODE_SET_KEYS = frozenset({"mode"})


def decode_command(raw: str) -> CommandEnvelope:
    """Decode a raw JSON command string into a validated :class:`CommandEnvelope`.

    Raises :class:`WireError` for any deviation from the v0.1 contract.
    """
    if type(raw) is not str:
        raise WireError("command must be a JSON string")
    if len(raw) > MAX_INPUT_CHARACTERS:
        raise WireError("command exceeds maximum input characters")
    try:
        encoded_bytes = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WireError("command is not valid UTF-8") from exc
    if len(encoded_bytes) > MAX_INPUT_UTF8_BYTES:
        raise WireError("command exceeds maximum UTF-8 bytes")

    obj = _parse_json(raw)
    if type(obj) is not dict:
        raise WireError("command must be a JSON object")
    keys = set(obj.keys())
    if keys != _ENVELOPE_KEYS:
        raise WireError("envelope must have exactly the required fields")

    schema_version = obj["schema_version"]
    if type(schema_version) is not str or schema_version != "0.1":
        raise WireError("schema_version must be 0.1")

    command_name = obj["command"]
    if type(command_name) is not str or command_name not in _COMMAND_BY_NAME:
        raise WireError("unknown command discriminator")
    command = _COMMAND_BY_NAME[command_name]

    session_id = obj["session_id"]
    _validate_session_id(session_id)

    sequence = obj["sequence"]
    _validate_int_field(sequence, "sequence", minimum=1)

    timestamp_ms = obj["timestamp_ms"]
    _validate_int_field(timestamp_ms, "timestamp_ms", minimum=0)

    payload = _decode_payload(command, obj["payload"])
    try:
        return CommandEnvelope(
            "0.1",
            command,
            session_id,
            sequence,
            timestamp_ms,
            payload,
        )
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def encode_event(event: OutputEvent) -> str:
    """Encode a single gateway output event into a canonical JSON string.

    Validates the DTO semantically before serialization and raises
    :class:`WireError` (not arbitrary exceptions) for any invalid event.
    """
    document = _event_to_validated_dict(event)
    try:
        return json.dumps(document, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise WireError(f"event serialization failed: {exc}") from exc


def encode_events(events: "tuple[OutputEvent, ...]") -> list[str]:
    """Encode an ordered tuple of events, preserving input order exactly."""
    return [encode_event(event) for event in events]


def _decode_payload(command: CommandName, payload: object) -> Any:
    if type(payload) is not dict:
        raise WireError("payload must be a JSON object")
    if command is CommandName.SESSION_START:
        return _decode_session_start(payload)
    if command is CommandName.SESSION_STOP:
        return _decode_empty_payload(payload)
    if command is CommandName.MODE_SET:
        return _decode_mode_set(payload)
    if command is CommandName.EMERGENCY_STOP:
        return _decode_empty_payload(payload)
    if command is CommandName.HEAD_POSE:
        return _decode_head_pose(payload)
    if command is CommandName.HEAD_RECENTER:
        return _decode_head_recenter(payload)
    raise WireError("unknown command discriminator")


def _decode_session_start(payload: dict[str, object]) -> SessionStartPayload:
    if set(payload.keys()) != _SESSION_START_KEYS:
        raise WireError("session.start payload must have requested_mode only")
    requested_mode = payload["requested_mode"]
    if type(requested_mode) is not str or requested_mode != "head":
        raise WireError("session.start requested_mode must be exactly \"head\"")
    try:
        return SessionStartPayload(requested_mode)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _decode_mode_set(payload: dict[str, object]) -> ModeSetPayload:
    if set(payload.keys()) != _MODE_SET_KEYS:
        raise WireError("mode.set payload must have mode only")
    mode = payload["mode"]
    if type(mode) is not str:
        raise WireError("mode must be a string")
    if not mode or mode.isspace():
        raise WireError("mode must be non-empty and non-whitespace")
    if len(mode) > MAX_MODE_LENGTH:
        raise WireError("mode must be at most 64 characters")
    try:
        return ModeSetPayload(mode)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _decode_empty_payload(payload: dict[str, object]) -> EmptyPayload:
    if payload:
        raise WireError("payload must be an empty object")
    return EmptyPayload()


def _decode_head_pose(payload: dict[str, object]) -> PosePayload:
    keys = set(payload.keys())
    if not {"frame", "orientation"} <= keys:
        raise WireError("head.pose payload must contain frame and orientation")
    if not keys <= _HEAD_POSE_KEYS:
        raise WireError("head.pose payload has unknown fields")
    frame = payload["frame"]
    if type(frame) is not str or frame != "quest_local":
        raise WireError("frame must be quest_local")
    orientation = _decode_quaternion(payload["orientation"])
    if "position" in keys:
        position = _decode_position_optional(payload["position"])
    else:
        position = None
    try:
        return PosePayload(frame, orientation, position)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _decode_head_recenter(payload: dict[str, object]) -> PosePayload:
    keys = set(payload.keys())
    if keys != _HEAD_RECENTER_KEYS:
        raise WireError(
            "head.recenter payload must have exactly frame and orientation"
        )
    frame = payload["frame"]
    if type(frame) is not str or frame != "quest_local":
        raise WireError("frame must be quest_local")
    orientation = _decode_quaternion(payload["orientation"])
    try:
        return PosePayload(frame, orientation, None)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _decode_quaternion(value: object) -> Quaternion:
    if type(value) is not dict or set(value.keys()) != _QUATERNION_KEYS:
        raise WireError("orientation must be an object with x,y,z,w")
    components: list[float] = []
    for name in ("x", "y", "z", "w"):
        component = value[name]
        if type(component) is bool or type(component) not in (int, float):
            raise WireError("quaternion values must be finite JSON numbers")
        if not isfinite(component):
            raise WireError("quaternion values must be finite JSON numbers")
        components.append(component)
    try:
        return Quaternion(*components)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _decode_position_optional(value: object) -> Position | None:
    if value is None:
        return None
    if type(value) is not dict or set(value.keys()) != _POSITION_KEYS:
        raise WireError("position must be an object with x,y,z or null")
    components: list[float] = []
    for name in ("x", "y", "z"):
        component = value[name]
        if type(component) is bool or type(component) not in (int, float):
            raise WireError("position values must be finite JSON numbers")
        if not isfinite(component):
            raise WireError("position values must be finite JSON numbers")
        components.append(component)
    try:
        return Position(*components)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _validate_session_id(value: object) -> None:
    if type(value) is not str or not value:
        raise WireError("session_id must be a non-empty string")
    if value.isspace() or value.strip() == "":
        raise WireError("session_id must be non-empty and non-whitespace")


def _validate_int_field(value: object, name: str, *, minimum: int) -> None:
    if type(value) is bool or type(value) is not int:
        raise WireError(f"{name} must be an integer")
    if value < minimum:
        raise WireError(f"{name} must be at least {minimum}")
    if value > MAX_INT64:
        raise WireError(f"{name} must not exceed Int64.MaxValue")


def _parse_json(raw: str) -> object:
    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )
    # Skip standard leading whitespace, matching json.loads / JSONDecoder.decode.
    start = 0
    length = len(raw)
    while start < length and raw[start] in " \t\n\r":
        start += 1
    try:
        obj, end = decoder.raw_decode(raw, start)
    except json.JSONDecodeError as exc:
        raise WireError(str(exc)) from exc
    if raw[end:].strip():
        raise WireError("trailing data after JSON document")
    _check_depth(obj, depth=1)
    return obj


def _check_depth(node: object, depth: int) -> None:
    if depth > MAX_JSON_DEPTH:
        raise WireError("JSON nesting depth exceeds 16")
    if type(node) is dict:
        for value in node.values():
            _check_depth(value, depth + 1)
    elif type(node) is list:
        for item in node:
            _check_depth(item, depth + 1)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    # Property names are decoded before duplicate detection so "x" and
    # "\u0078" collapse to the same key, matching the Unity contract.
    normalized: dict[str, object] = {}
    for key, value in pairs:
        if type(key) is not str:
            raise WireError("JSON property name must be a string")
        if key in normalized:
            raise WireError("duplicate keys in JSON object")
        normalized[key] = value
    return normalized


def _reject_constant(value: str) -> object:
    raise WireError(f"invalid JSON literal {value!r}")


# --- Event encoding (strict, fail-closed) ---


def _event_to_validated_dict(event: OutputEvent) -> dict[str, object]:
    if type(event) is GatewayStateEvent:
        return _encode_gateway_state_event(event)
    if type(event) is NeckTargetEvent:
        return _encode_neck_target_event(event)
    if type(event) is SafetyStopEvent:
        return _encode_safety_stop_event(event)
    if type(event) is CommandRejectedEvent:
        return _encode_command_rejected_event(event)
    raise WireError("event must be one of the approved event DTO types")


def _encode_gateway_state_event(event: GatewayStateEvent) -> dict[str, object]:
    _validate_int_field(event.gateway_monotonic_ns, "gateway_monotonic_ns", minimum=0)
    if type(event.schema_version) is not str or event.schema_version != "0.1":
        raise WireError("event schema_version must be 0.1")
    if event.event_type is not EventName.GATEWAY_STATE:
        raise WireError("event_type must be gateway.state")
    _validate_state_enum(event.state)
    _validate_correlation(event.session_id, event.sequence, required=False)
    return {
        "schema_version": "0.1",
        "event_type": EventName.GATEWAY_STATE.value,
        "gateway_monotonic_ns": event.gateway_monotonic_ns,
        "state": event.state.value,
        "session_id": event.session_id,
        "sequence": event.sequence,
    }


def _encode_neck_target_event(event: NeckTargetEvent) -> dict[str, object]:
    _validate_int_field(event.gateway_monotonic_ns, "gateway_monotonic_ns", minimum=0)
    if type(event.schema_version) is not str or event.schema_version != "0.1":
        raise WireError("event schema_version must be 0.1")
    if event.event_type is not EventName.NECK_TARGET:
        raise WireError("event_type must be neck.target")
    _validate_correlation(event.session_id, event.sequence, required=True)
    if type(event.pan_degrees) is bool or type(event.pan_degrees) not in (int, float):
        raise WireError("pan_degrees must be a finite number")
    if type(event.tilt_degrees) is bool or type(event.tilt_degrees) not in (int, float):
        raise WireError("tilt_degrees must be a finite number")
    if not isfinite(event.pan_degrees) or not isfinite(event.tilt_degrees):
        raise WireError("pan_degrees and tilt_degrees must be finite")
    if type(event.hold) is not bool:
        raise WireError("hold must be a boolean")
    return {
        "schema_version": "0.1",
        "event_type": EventName.NECK_TARGET.value,
        "gateway_monotonic_ns": event.gateway_monotonic_ns,
        "session_id": event.session_id,
        "sequence": event.sequence,
        "pan_degrees": event.pan_degrees,
        "tilt_degrees": event.tilt_degrees,
        "hold": event.hold,
    }


def _encode_safety_stop_event(event: SafetyStopEvent) -> dict[str, object]:
    _validate_int_field(event.gateway_monotonic_ns, "gateway_monotonic_ns", minimum=0)
    if type(event.schema_version) is not str or event.schema_version != "0.1":
        raise WireError("event schema_version must be 0.1")
    if event.event_type is not EventName.SAFETY_STOP:
        raise WireError("event_type must be safety.stop")
    if event.reason not in _STOP_REASON_BY_VALUE.values():
        raise WireError("unknown stop reason")
    _validate_correlation(event.session_id, event.sequence, required=False)
    _validate_action_string(event.neck_action, "neck_action")
    _validate_action_string(event.base_action, "base_action")
    _validate_action_string(event.arm_action, "arm_action")
    return {
        "schema_version": "0.1",
        "event_type": EventName.SAFETY_STOP.value,
        "gateway_monotonic_ns": event.gateway_monotonic_ns,
        "reason": event.reason.value,
        "session_id": event.session_id,
        "sequence": event.sequence,
        "neck_action": event.neck_action,
        "base_action": event.base_action,
        "arm_action": event.arm_action,
    }


def _encode_command_rejected_event(event: CommandRejectedEvent) -> dict[str, object]:
    _validate_int_field(event.gateway_monotonic_ns, "gateway_monotonic_ns", minimum=0)
    if type(event.schema_version) is not str or event.schema_version != "0.1":
        raise WireError("event schema_version must be 0.1")
    if event.event_type is not EventName.COMMAND_REJECTED:
        raise WireError("event_type must be command.rejected")
    if event.code not in _REJECTION_CODE_BY_VALUE.values():
        raise WireError("unknown rejection code")
    if type(event.message) is not str or not event.message:
        raise WireError("command.rejected message must be a non-empty string")
    _validate_correlation(event.session_id, event.sequence, required=False)
    return {
        "schema_version": "0.1",
        "event_type": EventName.COMMAND_REJECTED.value,
        "gateway_monotonic_ns": event.gateway_monotonic_ns,
        "code": event.code.value,
        "message": event.message,
        "session_id": event.session_id,
        "sequence": event.sequence,
    }


def _validate_state_enum(state: object) -> None:
    if state not in _STATE_BY_VALUE.values():
        raise WireError("unknown gateway state")


def _validate_action_string(value: object, name: str) -> None:
    if type(value) is not str or not value:
        raise WireError(f"{name} must be a non-empty string")


def _validate_correlation(
    session_id: object, sequence: object, *, required: bool
) -> None:
    session_present = session_id is not None
    sequence_present = sequence is not None
    if session_present != sequence_present:
        raise WireError("correlation must be both available or both unavailable")
    if not session_present:
        if required:
            raise WireError("neck.target correlation is required")
        return
    _validate_session_id(session_id)
    if type(sequence) is bool or type(sequence) is not int:
        raise WireError("correlation sequence must be an integer")
    if sequence < 1 or sequence > MAX_INT64:
        raise WireError("correlation sequence must be in 1..Int64.MaxValue")