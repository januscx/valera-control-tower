from dataclasses import dataclass
from enum import Enum


class Zone(str, Enum):
    BASE = "base"
    PICKUP_ZONE = "pickup_zone"
    DELIVERY_ZONE = "delivery_zone"
    SAFE_STOP = "safe_stop"


class ExecutionMode(str, Enum):
    SIMULATION = "simulation"
    REAL_VISION = "real_vision"
    HARDWARE = "hardware"


class FailureCode(str, Enum):
    OBJECT_NOT_FOUND = "object_not_found"
    MARKER_CONFIDENCE_LOW = "marker_confidence_low"
    PICKUP_UNREACHABLE = "pickup_unreachable"
    ALIGNMENT_FAILED = "alignment_failed"
    GRASP_FAILED = "grasp_failed"
    RELEASE_UNCERTAIN = "release_uncertain"
    MANUAL_CANCELLED = "manual_cancelled"
    EMERGENCY_STOP = "emergency_stop"
    HARDWARE_MODE_NOT_ENABLED = "hardware_mode_not_enabled"
    INVALID_TASK = "invalid_task"


class ValidationError(ValueError):
    def __init__(self, message: str, code: FailureCode = FailureCode.INVALID_TASK):
        super().__init__(message)
        self.code = code


def require_enum(enum_type: type[Enum], value: object, field_name: str) -> Enum:
    if isinstance(value, enum_type):
        return value

    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValidationError(f"unknown {field_name}: {value!r}") from exc


@dataclass
class Task:
    task_id: str
    object_id: str
    pickup_zone: Zone
    delivery_zone: Zone
    mode: ExecutionMode = ExecutionMode.SIMULATION
    description: str = ""

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValidationError("task_id is required")
        if not self.object_id:
            raise ValidationError("object_id is required")

        self.pickup_zone = require_enum(Zone, self.pickup_zone, "pickup_zone")
        self.delivery_zone = require_enum(Zone, self.delivery_zone, "delivery_zone")
        self.mode = require_enum(ExecutionMode, self.mode, "mode")

        if self.mode == ExecutionMode.HARDWARE:
            raise ValidationError(
                "hardware mode is not enabled for the MVP",
                FailureCode.HARDWARE_MODE_NOT_ENABLED,
            )
