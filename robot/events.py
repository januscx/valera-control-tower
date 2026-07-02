from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from robot.models import ExecutionMode, FailureCode, ValidationError, require_enum


SCHEMA_VERSION = "1.0"


class EventType(str, Enum):
    TASK_CREATED = "task.created"
    TASK_ACCEPTED = "task.accepted"
    PLAN_CREATED = "plan.created"
    ROUTE_STARTED = "route.started"
    ROUTE_ARRIVED = "route.arrived"
    OBJECT_SEARCH_STARTED = "object.search_started"
    OBJECT_FOUND = "object.found"
    OBJECT_NOT_FOUND = "object.not_found"
    GRASP_STARTED = "grasp.started"
    OBJECT_GRASPED = "object.grasped"
    GRASP_FAILED = "grasp.failed"
    DELIVERY_STARTED = "delivery.started"
    OBJECT_RELEASED = "object.released"
    DELIVERY_COMPLETED = "delivery.completed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


@dataclass
class EventError:
    code: FailureCode
    message: str

    def __post_init__(self) -> None:
        self.code = require_enum(FailureCode, self.code, "error.code")
        if not self.message:
            raise ValidationError("error.message is required")


@dataclass
class EventEnvelope:
    event_id: str
    task_id: str
    correlation_id: str
    sequence: int
    event_type: EventType
    occurred_at: datetime
    source: str
    mode: ExecutionMode
    payload: dict[str, Any]
    schema_version: str = SCHEMA_VERSION
    evidence_refs: list[str] = field(default_factory=list)
    error: EventError | None = None

    def __post_init__(self) -> None:
        required_strings = {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "source": self.source,
            "schema_version": self.schema_version,
        }
        for field_name, value in required_strings.items():
            if not value:
                raise ValidationError(f"{field_name} is required")

        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ValidationError("sequence must be a positive integer")

        self.event_type = require_enum(EventType, self.event_type, "event_type")
        self.mode = require_enum(ExecutionMode, self.mode, "mode")

        if self.mode == ExecutionMode.HARDWARE:
            raise ValidationError(
                "hardware mode is not enabled for the MVP",
                FailureCode.HARDWARE_MODE_NOT_ENABLED,
            )

        if not isinstance(self.occurred_at, datetime):
            raise ValidationError("occurred_at must be a datetime")
        if self.occurred_at.tzinfo is None:
            self.occurred_at = self.occurred_at.replace(tzinfo=timezone.utc)

        if not isinstance(self.payload, dict):
            raise ValidationError("payload must be a dict")
        if not isinstance(self.evidence_refs, list):
            raise ValidationError("evidence_refs must be a list")

        if self.error is not None and not isinstance(self.error, EventError):
            self.error = EventError(**self.error)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at.isoformat(),
            "source": self.source,
            "mode": self.mode.value,
            "schema_version": self.schema_version,
            "payload": self.payload,
            "evidence_refs": self.evidence_refs,
        }
        if self.error is not None:
            data["error"] = {
                "code": self.error.code.value,
                "message": self.error.message,
            }
        return data
