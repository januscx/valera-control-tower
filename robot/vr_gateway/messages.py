from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import TypeAlias

SCHEMA_VERSION = "0.1"
QUEST_LOCAL_FRAME = "quest_local"


class MessageValidationError(ValueError):
    pass


class ControlMode(str, Enum):
    HEAD_ONLY = "HEAD_ONLY"
    DRIVE = "DRIVE"
    ARM = "ARM"


class ModeTransition(str, Enum):
    NONE = "NONE"
    STOPPING_BASE = "STOPPING_BASE"
    STOPPING_ARM = "STOPPING_ARM"


class CommandName(str, Enum):
    SESSION_START = "session.start"
    SESSION_STOP = "session.stop"
    MODE_SET = "mode.set"
    HEAD_POSE = "head.pose"
    HEAD_RECENTER = "head.recenter"
    EMERGENCY_STOP = "emergency_stop"
    EMERGENCY_STOP_RESET = "emergency_stop.reset"
    BASE_DRIVE = "base.drive"
    ARM_JOG = "arm.jog"


class GatewayState(str, Enum):
    IDLE = "IDLE"
    AWAITING_RECENTER = "AWAITING_RECENTER"
    ACTIVE = "ACTIVE"
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
    BASE_TARGET = "base.target"
    ARM_TARGET = "arm.target"
    BASE_STOP_ACK = "base.stop_ack"


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


@dataclass(frozen=True)
class BaseDrivePayload:
    throttle: float
    steering: float
    deadman: bool

    def __post_init__(self) -> None:
        _finite_json_number(self.throttle, "throttle")
        _finite_json_number(self.steering, "steering")
        if not -1.0 <= self.throttle <= 1.0:
            raise MessageValidationError("throttle must be in [-1.0, 1.0]")
        if not -1.0 <= self.steering <= 1.0:
            raise MessageValidationError("steering must be in [-1.0, 1.0]")
        if type(self.deadman) is not bool:
            raise MessageValidationError("deadman must be a boolean")


@dataclass(frozen=True)
class ArmJogPayload:
    kind: str
    deadman: bool
    joint_velocity: dict[str, float]

    def __post_init__(self) -> None:
        if self.kind != "JOINT_JOG":
            raise MessageValidationError("kind must be JOINT_JOG")
        if type(self.deadman) is not bool:
            raise MessageValidationError("deadman must be a boolean")
        if type(self.joint_velocity) is not dict or not self.joint_velocity:
            raise MessageValidationError("joint_velocity must be a non-empty dict")
        for name, value in self.joint_velocity.items():
            _require_nonempty_string(name, "joint name")
            _finite_json_number(value, "joint velocity")
            if not -1.0 <= value <= 1.0:
                raise MessageValidationError(
                    f"joint {name} velocity must be in [-1.0, 1.0]"
                )


Payload: TypeAlias = SessionStartPayload | ModeSetPayload | PosePayload | EmptyPayload | BaseDrivePayload | ArmJogPayload


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
    elif type(payload) is BaseDrivePayload:
        payload.__post_init__()
    elif type(payload) is ArmJogPayload:
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


def _validate_int_field(value: object, field_name: str, minimum: int = 0) -> None:
    if type(value) is not int:
        raise MessageValidationError(f"{field_name} must be an integer")
    if value < minimum:
        raise MessageValidationError(f"{field_name} must be non-negative")


@dataclass(frozen=True)
class GatewayStateEvent:
    gateway_monotonic_ns: int
    state: GatewayState
    current_mode: ControlMode
    session_id: str | None
    sequence: int | None
    requested_mode: ControlMode | None = None
    transition: ModeTransition = ModeTransition.NONE
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


@dataclass(frozen=True)
class BaseTargetEvent:
    gateway_monotonic_ns: int
    throttle: float
    steering: float
    deadman: bool
    command_zeroed: bool
    schema_version: str = SCHEMA_VERSION
    event_type: EventName = EventName.BASE_TARGET

    def __post_init__(self) -> None:
        _validate_int_field(self.gateway_monotonic_ns, "gateway_monotonic_ns", minimum=0)
        for name in ("throttle", "steering"):
            value = getattr(self, name)
            if type(value) is bool or type(value) not in (int, float) or not isfinite(value):
                raise MessageValidationError(f"{name} must be a finite number")
            if not -1.0 <= value <= 1.0:
                raise MessageValidationError(f"{name} must be in [-1.0, 1.0]")
        if type(self.deadman) is not bool:
            raise MessageValidationError("deadman must be a boolean")
        if type(self.command_zeroed) is not bool:
            raise MessageValidationError("command_zeroed must be a boolean")


@dataclass(frozen=True)
class ArmTargetEvent:
    gateway_monotonic_ns: int
    kind: str
    deadman: bool
    command_zeroed: bool
    joint_velocity: dict[str, float]
    schema_version: str = SCHEMA_VERSION
    event_type: EventName = EventName.ARM_TARGET

    def __post_init__(self) -> None:
        _validate_int_field(self.gateway_monotonic_ns, "gateway_monotonic_ns", minimum=0)
        if self.kind != "JOINT_JOG":
            raise MessageValidationError("kind must be JOINT_JOG")
        if type(self.deadman) is not bool:
            raise MessageValidationError("deadman must be a boolean")
        if type(self.command_zeroed) is not bool:
            raise MessageValidationError("command_zeroed must be a boolean")
        if type(self.joint_velocity) is not dict or not self.joint_velocity:
            raise MessageValidationError("joint_velocity must be a non-empty dict")
        for name, value in self.joint_velocity.items():
            if not -1.0 <= value <= 1.0:
                raise MessageValidationError(
                    f"joint {name} velocity must be in [-1.0, 1.0]"
                )


@dataclass(frozen=True)
class BaseStopAckEvent:
    gateway_monotonic_ns: int
    command_zeroed: bool
    stationary_verified: bool
    schema_version: str = SCHEMA_VERSION
    event_type: EventName = EventName.BASE_STOP_ACK

    def __post_init__(self) -> None:
        if type(self.command_zeroed) is not bool:
            raise MessageValidationError("command_zeroed must be a boolean")
        if type(self.stationary_verified) is not bool:
            raise MessageValidationError("stationary_verified must be a boolean")


OutputEvent: TypeAlias = (
    GatewayStateEvent
    | NeckTargetEvent
    | SafetyStopEvent
    | CommandRejectedEvent
    | BaseTargetEvent
    | ArmTargetEvent
    | BaseStopAckEvent
)
