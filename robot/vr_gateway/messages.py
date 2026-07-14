from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
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
        for name in ("x", "y", "z", "w"):
            value = _finite_json_number(getattr(self, name), "quaternion")
            object.__setattr__(self, name, value)
        _validate_quaternion(self)

    @property
    def norm(self) -> float:
        return hypot(self.x, self.y, self.z, self.w)

    def normalized(self) -> "Quaternion":
        norm = self.norm
        return Quaternion(self.x / norm, self.y / norm, self.z / norm, self.w / norm)


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        for name in ("x", "y", "z"):
            value = _finite_json_number(getattr(self, name), "position")
            object.__setattr__(self, name, value)
        _validate_position(self)


@dataclass(frozen=True)
class SessionStartPayload:
    requested_mode: str

    def __post_init__(self) -> None:
        _require_nonempty_string(self.requested_mode, "requested_mode")


@dataclass(frozen=True)
class ModeSetPayload:
    mode: str

    def __post_init__(self) -> None:
        _require_nonempty_string(self.mode, "mode")


@dataclass(frozen=True)
class PosePayload:
    frame: str
    orientation: Quaternion
    position: Position | None = None

    def __post_init__(self) -> None:
        if type(self.frame) is not str or self.frame != QUEST_LOCAL_FRAME:
            raise MessageValidationError("frame must be quest_local")
        if type(self.orientation) is not Quaternion:
            raise MessageValidationError("orientation must be a Quaternion")
        _validate_quaternion(self.orientation)
        if self.position is not None:
            if type(self.position) is not Position:
                raise MessageValidationError("position must be a Position")
            _validate_position(self.position)


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
        if type(self.schema_version) is not str or self.schema_version != SCHEMA_VERSION:
            raise MessageValidationError("schema_version must be 0.1")
        if type(self.command) is not CommandName:
            raise MessageValidationError("command must be a CommandName")
        _require_nonempty_string(self.session_id, "session_id")
        if type(self.sequence) is not int:
            raise MessageValidationError("sequence must be an integer")
        if self.sequence < 1:
            raise MessageValidationError("sequence must be at least 1")
        if type(self.timestamp_ms) is not int:
            raise MessageValidationError("timestamp_ms must be an integer")
        if self.timestamp_ms < 0:
            raise MessageValidationError("timestamp_ms must be non-negative")
        _validate_payload(self.payload)


def validate_command_envelope(value: object) -> CommandEnvelope:
    """Validate an envelope again at the gateway's runtime trust boundary."""
    if type(value) is not CommandEnvelope:
        raise MessageValidationError("command must be a CommandEnvelope")
    value.__post_init__()
    return value


def _validate_payload(payload: object) -> None:
    if type(payload) is SessionStartPayload:
        payload.__post_init__()
    elif type(payload) is ModeSetPayload:
        payload.__post_init__()
    elif type(payload) is PosePayload:
        payload.__post_init__()
    elif type(payload) is not EmptyPayload:
        raise MessageValidationError("payload must be an approved payload model")


def _validate_quaternion(value: Quaternion) -> None:
    components = (value.x, value.y, value.z, value.w)
    if any(
        type(component) not in (int, float) or not isfinite(component)
        for component in components
    ):
        raise MessageValidationError("quaternion values must be finite JSON numbers")
    norm = hypot(*components)
    if not isfinite(norm):
        raise MessageValidationError("quaternion norm must be finite")
    if norm <= 1e-12:
        raise MessageValidationError("quaternion must not be zero length")


def _validate_position(value: Position) -> None:
    components = (value.x, value.y, value.z)
    if any(
        type(component) not in (int, float) or not isfinite(component)
        for component in components
    ):
        raise MessageValidationError("position values must be finite JSON numbers")


def _finite_json_number(value: object, owner: str) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise MessageValidationError(f"{owner} values must be finite JSON numbers")
    return float(value)


def _require_nonempty_string(value: object, field_name: str) -> None:
    if type(value) is not str or not value:
        raise MessageValidationError(f"{field_name} must be a non-empty string")


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
