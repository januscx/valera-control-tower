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
