from __future__ import annotations

from robot.adapters.arm import (
    ArmCapabilities,
    ArmCommandResult,
    ArmJointState,
    ArmProbeResult,
    ArmState,
)
from robot.adapters.base import (
    AdapterHealth,
    AdapterIdentity,
    AdapterMode,
    AdapterStatus,
    AdapterType,
)


class SimArmAdapter:
    """Simulation-only arm adapter for orchestration tests and demos."""

    def __init__(
        self,
        adapter_id: str = "sim-arm",
        joint_names: tuple[str, ...] = (
            "base",
            "shoulder",
            "elbow",
            "wrist_pitch",
            "wrist_roll",
            "gripper",
        ),
        gripper_open: bool = True,
    ) -> None:
        self.identity = AdapterIdentity(
            adapter_id=adapter_id,
            adapter_type=AdapterType.ARM,
            mode=AdapterMode.SIMULATION,
            display_name="Simulated arm",
        )
        self._joint_names = joint_names
        self._state = ArmState(
            joints=tuple(ArmJointState(name=name, position_deg=0.0) for name in joint_names),
            gripper_open=gripper_open,
            torque_enabled=False,
            metadata={"source": "simulation"},
        )

    def capabilities(self) -> ArmCapabilities:
        return ArmCapabilities(
            can_read_state=True,
            can_enable_torque=False,
            can_move=True,
            joint_count=len(self._joint_names),
            supported_commands=("probe", "read_state", "simulate_grasp"),
            notes=("Simulation only; never enables torque or touches hardware.",),
        )

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            status=AdapterStatus.OK,
            message="simulation arm ready",
            details={"mode": AdapterMode.SIMULATION.value},
        )

    def probe(self) -> ArmProbeResult:
        return ArmProbeResult(
            ok=True,
            identity=self.identity,
            health=self.health(),
            capabilities=self.capabilities(),
            state=self._state,
            runtime="simulation",
        )

    def simulate_grasp(self, gripper_open: bool = False) -> ArmCommandResult:
        self._state = ArmState(
            joints=self._state.joints,
            gripper_open=gripper_open,
            torque_enabled=False,
            metadata={"source": "simulation", "last_command": "simulate_grasp"},
        )
        return ArmCommandResult(
            ok=True,
            identity=self.identity,
            health=self.health(),
            command_name="simulate_grasp",
            executed=True,
            state=self._state,
        )
