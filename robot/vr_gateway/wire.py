"""Transport-neutral wire codec for the Unity VR Gateway v0.1 contract.

This module is the only place that translates between raw JSON strings and the
project-owned DTOs in :mod:`robot.vr_gateway.messages`. It owns no session
state, no watchdog, no mode policy, and no hardware knowledge. Decoding is
strict fail-closed: malformed JSON, duplicate keys, NaN/Infinity literals,
trailing data, missing/extra fields, wrong types, and unknown command
discriminators all raise :class:`WireError`. The caller is expected to route
that failure through :class:`robot.vr_gateway.gateway.VrGateway.handle` so the
gateway's existing fail-closed path produces the safety event.
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
    EmptyPayload,
    GatewayStateEvent,
    MessageValidationError,
    ModeSetPayload,
    NeckTargetEvent,
    OutputEvent,
    PosePayload,
    Position,
    Quaternion,
    SafetyStopEvent,
    SessionStartPayload,
)

__all__ = [
    "WireError",
    "decode_command",
    "encode_event",
    "encode_events",
]


class WireError(ValueError):
    """Raised when a raw JSON string cannot be decoded into a command DTO."""


_COMMAND_BY_NAME: dict[str, CommandName] = {name.value: name for name in CommandName}

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
_POSE_KEYS = frozenset({"frame", "orientation", "position"})
_QUATERNION_KEYS = frozenset({"x", "y", "z", "w"})
_POSITION_KEYS = frozenset({"x", "y", "z"})
_SESSION_START_KEYS = frozenset({"requested_mode"})
_MODE_SET_KEYS = frozenset({"mode"})


def decode_command(raw: str) -> CommandEnvelope:
    """Decode a raw JSON command string into a validated :class:`CommandEnvelope`.

    Raises :class:`WireError` for any deviation from the v0.1 contract.
    """
    obj = _parse_json(raw)
    if type(obj) is not dict:
        raise WireError("command must be a JSON object")
    if set(obj.keys()) != _ENVELOPE_KEYS:
        raise WireError("envelope must have exactly the required fields")

    schema_version = obj["schema_version"]
    if type(schema_version) is not str or schema_version != "0.1":
        raise WireError("schema_version must be 0.1")

    command_name = obj["command"]
    if type(command_name) is not str or command_name not in _COMMAND_BY_NAME:
        raise WireError("unknown command discriminator")
    command = _COMMAND_BY_NAME[command_name]

    session_id = obj["session_id"]
    if type(session_id) is not str or not session_id:
        raise WireError("session_id must be a non-empty string")

    sequence = obj["sequence"]
    if type(sequence) is not int:
        raise WireError("sequence must be an integer")
    if sequence < 1:
        raise WireError("sequence must be at least 1")

    timestamp_ms = obj["timestamp_ms"]
    if type(timestamp_ms) is not int:
        raise WireError("timestamp_ms must be an integer")
    if timestamp_ms < 0:
        raise WireError("timestamp_ms must be non-negative")

    payload = _decode_payload(command, obj["payload"])
    try:
        return CommandEnvelope(
            schema_version,
            command,
            session_id,
            sequence,
            timestamp_ms,
            payload,
        )
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def encode_event(event: OutputEvent) -> str:
    """Encode a single gateway output event into a canonical JSON string."""
    return json.dumps(_event_to_dict(event), separators=(",", ":"))


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
    return _decode_pose(payload)


def _decode_session_start(payload: dict[str, object]) -> SessionStartPayload:
    if set(payload.keys()) != _SESSION_START_KEYS:
        raise WireError("session.start payload must have requested_mode only")
    requested_mode = payload["requested_mode"]
    if type(requested_mode) is not str or not requested_mode:
        raise WireError("requested_mode must be a non-empty string")
    try:
        return SessionStartPayload(requested_mode)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _decode_mode_set(payload: dict[str, object]) -> ModeSetPayload:
    if set(payload.keys()) != _MODE_SET_KEYS:
        raise WireError("mode.set payload must have mode only")
    mode = payload["mode"]
    if type(mode) is not str or not mode:
        raise WireError("mode must be a non-empty string")
    try:
        return ModeSetPayload(mode)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _decode_empty_payload(payload: dict[str, object]) -> EmptyPayload:
    if payload:
        raise WireError("payload must be an empty object")
    return EmptyPayload()


def _decode_pose(payload: dict[str, object]) -> PosePayload:
    keys = set(payload.keys())
    if not {"frame", "orientation"} <= keys:
        raise WireError("pose payload must contain frame and orientation")
    if not keys <= _POSE_KEYS:
        raise WireError("pose payload has unknown fields")
    frame = payload["frame"]
    if type(frame) is not str or frame != "quest_local":
        raise WireError("frame must be quest_local")
    orientation = _decode_quaternion(payload["orientation"])
    position = _decode_position_optional(payload.get("position"))
    try:
        return PosePayload(frame, orientation, position)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _decode_quaternion(value: object) -> Quaternion:
    if type(value) is not dict or set(value.keys()) != _QUATERNION_KEYS:
        raise WireError("orientation must be an object with x,y,z,w")
    components: list[float] = []
    for name in ("x", "y", "z", "w"):
        component = value[name]
        if type(component) not in (int, float) or not isfinite(component):
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
        if type(component) not in (int, float) or not isfinite(component):
            raise WireError("position values must be finite JSON numbers")
        components.append(component)
    try:
        return Position(*components)
    except MessageValidationError as exc:
        raise WireError(str(exc)) from exc


def _parse_json(raw: str) -> object:
    if type(raw) is not str:
        raise WireError("command must be a JSON string")
    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )
    try:
        obj, end = decoder.raw_decode(raw)
    except json.JSONDecodeError as exc:
        raise WireError(str(exc)) from exc
    if raw[end:].strip():
        raise WireError("trailing data after JSON document")
    return obj


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise WireError("duplicate keys in JSON object")
    return dict(pairs)


def _reject_constant(value: str) -> object:
    raise WireError(f"invalid JSON literal {value!r}")


def _event_to_dict(event: OutputEvent) -> dict[str, object]:
    return {key: _enum_to_value(value) for key, value in asdict(event).items()}


def _enum_to_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value