from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from robot.adapters.base import AdapterFailure, AdapterHealth, AdapterIdentity


@dataclass(frozen=True)
class ArmJointState:
    name: str
    position_deg: float | None = None
    velocity_deg_s: float | None = None
    load: float | None = None
    temperature_c: float | None = None


@dataclass(frozen=True)
class ArmCapabilities:
    can_read_state: bool
    can_enable_torque: bool
    can_move: bool
    joint_count: int
    supported_commands: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArmState:
    joints: tuple[ArmJointState, ...] = ()
    gripper_open: bool | None = None
    torque_enabled: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ArmProbeResult:
    ok: bool
    identity: AdapterIdentity
    health: AdapterHealth
    capabilities: ArmCapabilities
    state: ArmState | None = None
    runtime: str = ""
    failure: AdapterFailure | None = None


@dataclass(frozen=True)
class ArmCommandResult:
    ok: bool
    identity: AdapterIdentity
    health: AdapterHealth
    command_name: str
    executed: bool
    state: ArmState | None = None
    failure: AdapterFailure | None = None


@dataclass(frozen=True)
class ArmIdentityStateReadiness:
    phase: str
    mode: str
    execution_available: bool
    protocol_candidate: str
    library_candidate: str
    query_requires_bytes: bool
    torque_required: bool
    movement_required: bool
    homing_required: bool
    safe_to_execute_now: bool
    blockers: tuple[str, ...] = ()
    operator_preconditions: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...] = ()
    safety_flags: dict[str, bool] = field(default_factory=dict)


@runtime_checkable
class ArmAdapter(Protocol):
    identity: AdapterIdentity

    def capabilities(self) -> ArmCapabilities:
        ...

    def health(self) -> AdapterHealth:
        ...

    def probe(self) -> ArmProbeResult:
        ...
