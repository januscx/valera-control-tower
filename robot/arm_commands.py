from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from robot.adapters.arm import ArmAdapter, ArmCapabilities


PHASE_4_SAFETY_FLAGS = {
    "serial_opened": False,
    "serial_commands_sent": False,
    "torque_enabled": False,
    "movement_commanded": False,
    "actuator_calls": False,
}

PHASE_4_LIMITATIONS = (
    "Phase 4 is dry-run only.",
    "No serial port is opened.",
    "No bytes are sent.",
    "No torque is enabled.",
    "No movement is commanded.",
    "No actuator APIs are called.",
)

LOW_LEVEL_TARGET_KEYS = {
    "actuator",
    "actuator_id",
    "actuator_ids",
    "current",
    "current_ma",
    "enable_torque",
    "joint_angle",
    "joint_angles",
    "motor_id",
    "motor_ids",
    "raw_actuator",
    "raw_payload",
    "raw_serial",
    "raw_serial_bytes",
    "servo_id",
    "servo_ids",
    "serial_bytes",
    "torque",
    "torque_current",
    "torque_enabled",
}


class ArmCommandType(str, Enum):
    HOME = "home"
    MOVE_TO_POSE = "move_to_pose"
    OPEN_GRIPPER = "open_gripper"
    CLOSE_GRIPPER = "close_gripper"
    HOLD_POSITION = "hold_position"
    NOOP = "noop"


class ArmCommandStatus(str, Enum):
    ACCEPTED_DRY_RUN = "accepted_dry_run"
    REJECTED_SCHEMA = "rejected_schema"
    REJECTED_SAFETY = "rejected_safety"
    BLOCKED_CAPABILITY_UNAVAILABLE = "blocked_capability_unavailable"


@dataclass(frozen=True)
class ArmCommandSafetyPrecondition:
    name: str
    satisfied: bool
    description: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "satisfied": self.satisfied,
            "description": self.description,
        }


@dataclass(frozen=True)
class ArmCommand:
    command_type: ArmCommandType | str
    target: dict[str, object] = field(default_factory=dict)

    @property
    def command_type_value(self) -> str:
        if isinstance(self.command_type, ArmCommandType):
            return self.command_type.value
        return str(self.command_type)


@dataclass(frozen=True)
class ArmCommandEnvelope:
    command_id: str
    command_type: ArmCommandType | str
    target: dict[str, object]
    reason: str
    requested_by: str
    dry_run: bool = True

    @classmethod
    def from_command(
        cls,
        *,
        command_id: str,
        command: ArmCommand,
        reason: str,
        requested_by: str,
        dry_run: bool = True,
    ) -> "ArmCommandEnvelope":
        return cls(
            command_id=command_id,
            command_type=command.command_type,
            target=command.target,
            reason=reason,
            requested_by=requested_by,
            dry_run=dry_run,
        )

    @classmethod
    def from_command_name(
        cls,
        *,
        command_id: str,
        command_name: str,
        target: dict[str, object],
        reason: str,
        requested_by: str,
        dry_run: bool = True,
    ) -> "ArmCommandEnvelope":
        normalized = command_name.strip().lower().replace("-", "_")
        try:
            command_type: ArmCommandType | str = ArmCommandType(normalized)
        except ValueError:
            command_type = normalized
        return cls(
            command_id=command_id,
            command_type=command_type,
            target=target,
            reason=reason,
            requested_by=requested_by,
            dry_run=dry_run,
        )

    @property
    def command_type_value(self) -> str:
        if isinstance(self.command_type, ArmCommandType):
            return self.command_type.value
        return str(self.command_type)


@dataclass(frozen=True)
class ArmCommandValidation:
    schema_valid: bool
    safety_valid: bool
    execution_available: bool
    dry_run_acceptable: bool
    status: ArmCommandStatus
    messages: list[str]


@dataclass(frozen=True)
class ArmCommandDryRunResult:
    command_id: str
    command_type: str
    adapter_id: str
    accepted: bool
    executable_now: bool
    status: ArmCommandStatus
    schema_valid: bool
    safety_valid: bool
    required_capabilities: list[str]
    unavailable_capabilities: list[str]
    safety_preconditions: list[ArmCommandSafetyPrecondition]
    evidence: dict[str, object]
    messages: list[str]
    next_actions: list[str]
    safety_flags: dict[str, bool] = field(default_factory=lambda: dict(PHASE_4_SAFETY_FLAGS))

    def to_dict(self) -> dict[str, object]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type,
            "adapter_id": self.adapter_id,
            "accepted": self.accepted,
            "executable_now": self.executable_now,
            "status": self.status.value,
            "schema_valid": self.schema_valid,
            "safety_valid": self.safety_valid,
            "required_capabilities": list(self.required_capabilities),
            "unavailable_capabilities": list(self.unavailable_capabilities),
            "safety_preconditions": [
                precondition.to_dict() for precondition in self.safety_preconditions
            ],
            "evidence": dict(self.evidence),
            "messages": list(self.messages),
            "next_actions": list(self.next_actions),
            "safety_flags": dict(self.safety_flags),
        }


def dry_run_arm_command(
    envelope: ArmCommandEnvelope,
    adapter: ArmAdapter,
    *,
    now: datetime | None = None,
) -> ArmCommandDryRunResult:
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    capabilities = adapter.capabilities()
    required_capabilities = _required_capabilities(envelope.command_type)
    unavailable_capabilities = _unavailable_capabilities(required_capabilities, capabilities)
    schema_messages = _schema_messages(envelope)
    safety_messages = _safety_messages(envelope.target)

    schema_valid = not schema_messages
    safety_valid = not safety_messages
    accepted = schema_valid and safety_valid and envelope.dry_run
    executable_now = False

    if not schema_valid:
        status = ArmCommandStatus.REJECTED_SCHEMA
    elif not safety_valid:
        status = ArmCommandStatus.REJECTED_SAFETY
    else:
        status = ArmCommandStatus.ACCEPTED_DRY_RUN

    messages = [*schema_messages, *safety_messages]
    if accepted:
        messages.append("Phase 4 is dry-run only")
        if unavailable_capabilities:
            messages.append(
                "Adapter does not currently expose required execution capability: "
                + ", ".join(unavailable_capabilities)
            )
        messages.append("Execution is not available in Phase 4")

    safety_preconditions = _safety_preconditions(envelope.command_type)
    evidence = {
        "command_id": envelope.command_id,
        "command_type": envelope.command_type_value,
        "adapter_id": adapter.identity.adapter_id,
        "adapter_mode": adapter.identity.mode.value,
        "dry_run_status": status.value,
        "blocked_reason": "execution_not_available_in_phase_4",
        "required_capabilities": list(required_capabilities),
        "unavailable_capabilities": list(unavailable_capabilities),
        "safety_preconditions": [item.to_dict() for item in safety_preconditions],
        "timestamp": timestamp,
        "limitations": list(PHASE_4_LIMITATIONS),
        "safety_flags": dict(PHASE_4_SAFETY_FLAGS),
    }

    return ArmCommandDryRunResult(
        command_id=envelope.command_id,
        command_type=envelope.command_type_value,
        adapter_id=adapter.identity.adapter_id,
        accepted=accepted,
        executable_now=executable_now,
        status=status,
        schema_valid=schema_valid,
        safety_valid=safety_valid,
        required_capabilities=list(required_capabilities),
        unavailable_capabilities=list(unavailable_capabilities),
        safety_preconditions=safety_preconditions,
        evidence=evidence,
        messages=messages,
        next_actions=_next_actions(status),
        safety_flags=dict(PHASE_4_SAFETY_FLAGS),
    )


def _schema_messages(envelope: ArmCommandEnvelope) -> list[str]:
    messages: list[str] = []
    if not envelope.command_id.strip():
        messages.append("command id is required")
    if not isinstance(envelope.command_type, ArmCommandType):
        messages.append(f"unknown command type: {envelope.command_type_value}")
    if not isinstance(envelope.target, dict):
        messages.append("target must be an object")
    if not envelope.reason.strip():
        messages.append("reason is required")
    if not envelope.requested_by.strip():
        messages.append("requested_by is required")
    if envelope.dry_run is not True:
        messages.append("dry_run must be true")
    if isinstance(envelope.command_type, ArmCommandType) and isinstance(envelope.target, dict):
        messages.extend(_target_shape_messages(envelope.command_type, envelope.target))
    return messages


def _target_shape_messages(
    command_type: ArmCommandType,
    target: dict[str, object],
) -> list[str]:
    messages: list[str] = []
    allowed_keys = _allowed_target_keys(command_type)
    unknown_keys = sorted(set(target) - allowed_keys)
    if unknown_keys:
        messages.append("target contains unsupported keys: " + ", ".join(unknown_keys))

    if command_type == ArmCommandType.MOVE_TO_POSE and not isinstance(target.get("pose_id"), str):
        messages.append("move_to_pose requires a named pose_id")
    if command_type == ArmCommandType.HOME and "profile" in target and not isinstance(
        target["profile"],
        str,
    ):
        messages.append("home profile must be a name")
    if command_type == ArmCommandType.OPEN_GRIPPER and "width_intent" in target and not isinstance(
        target["width_intent"],
        str,
    ):
        messages.append("open_gripper width_intent must be a name")
    if command_type == ArmCommandType.CLOSE_GRIPPER and "force_profile" in target and not isinstance(
        target["force_profile"],
        str,
    ):
        messages.append("close_gripper force_profile must be a name")
    if command_type == ArmCommandType.HOLD_POSITION and "duration_hint_s" in target:
        duration = target["duration_hint_s"]
        if not isinstance(duration, int | float) or duration < 0:
            messages.append("hold_position duration_hint_s must be a non-negative hint")
    if command_type == ArmCommandType.NOOP and target:
        messages.append("noop target must be empty")
    return messages


def _allowed_target_keys(command_type: ArmCommandType) -> set[str]:
    return {
        ArmCommandType.HOME: {"profile"},
        ArmCommandType.MOVE_TO_POSE: {"pose_id"},
        ArmCommandType.OPEN_GRIPPER: {"width_intent"},
        ArmCommandType.CLOSE_GRIPPER: {"force_profile"},
        ArmCommandType.HOLD_POSITION: {"duration_hint_s"},
        ArmCommandType.NOOP: set(),
    }[command_type]


def _safety_messages(target: dict[str, object]) -> list[str]:
    unsafe_keys = sorted(_find_low_level_keys(target))
    if not unsafe_keys:
        return []
    return ["target contains low-level actuator or serial fields: " + ", ".join(unsafe_keys)]


def _find_low_level_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if normalized in LOW_LEVEL_TARGET_KEYS:
                found.add(normalized)
            found.update(_find_low_level_keys(nested))
    elif isinstance(value, list | tuple):
        for item in value:
            found.update(_find_low_level_keys(item))
    return found


def _required_capabilities(command_type: ArmCommandType | str) -> tuple[str, ...]:
    if command_type in {
        ArmCommandType.HOME,
        ArmCommandType.MOVE_TO_POSE,
        ArmCommandType.OPEN_GRIPPER,
        ArmCommandType.CLOSE_GRIPPER,
        ArmCommandType.HOLD_POSITION,
    }:
        return ("can_move",)
    return ()


def _unavailable_capabilities(
    required_capabilities: tuple[str, ...],
    capabilities: ArmCapabilities,
) -> tuple[str, ...]:
    return tuple(
        capability
        for capability in required_capabilities
        if not bool(getattr(capabilities, capability))
    )


def _safety_preconditions(
    command_type: ArmCommandType | str,
) -> list[ArmCommandSafetyPrecondition]:
    common = [
        ArmCommandSafetyPrecondition(
            name="operator_review",
            satisfied=False,
            description="A future execution phase requires explicit operator review.",
        ),
        ArmCommandSafetyPrecondition(
            name="phase_allows_execution",
            satisfied=False,
            description="Phase 4 does not allow command execution.",
        ),
    ]
    if command_type == ArmCommandType.NOOP:
        return common
    return [
        *common,
        ArmCommandSafetyPrecondition(
            name="motion_safety_plan",
            satisfied=False,
            description="Motion intents require a later supervised safety plan.",
        ),
    ]


def _next_actions(status: ArmCommandStatus) -> list[str]:
    if status == ArmCommandStatus.ACCEPTED_DRY_RUN:
        return [
            "Record dry-run evidence only if the orchestrator chooses to append an event.",
            "Keep Phase 5 limited to read-only serial identity/state gates.",
        ]
    return [
        "Fix the command envelope before recording dry-run evidence.",
        "Do not attempt hardware execution.",
    ]
