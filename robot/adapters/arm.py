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


@runtime_checkable
class ArmAdapter(Protocol):
    identity: AdapterIdentity

    def capabilities(self) -> ArmCapabilities:
        ...

    def health(self) -> AdapterHealth:
        ...

    def probe(self) -> ArmProbeResult:
        ...
