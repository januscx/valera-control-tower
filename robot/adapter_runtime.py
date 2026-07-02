from __future__ import annotations

from dataclasses import dataclass, field

from robot.adapters.base import AdapterMode
from robot.adapters.camera import CameraRole
from robot.adapters.sim_arm import SimArmAdapter
from robot.adapters.sim_camera import SimCameraAdapter
from robot.adapters.sim_vision import SimVisionAdapter
from robot.adapters.so_arm_metadata import MetadataOnlySOArmAdapter
from robot.adapters.vision import VisionDetection
from robot.models import FailureCode, ValidationError


ARM_ADAPTER_SIM = "sim"
ARM_ADAPTER_METADATA_ONLY_SO_ARM = "metadata_only_so_arm"


@dataclass(frozen=True)
class AdapterRuntimeConfig:
    mode: AdapterMode = AdapterMode.SIMULATION
    camera_role: CameraRole = CameraRole.WRIST
    camera_resolution: tuple[int, int] = (640, 480)
    vision_detections: tuple[VisionDetection, ...] = field(default_factory=tuple)
    arm_adapter_id: str = "sim-arm"
    arm_adapter_kind: str = ARM_ADAPTER_SIM
    so_arm_device_path: str = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", AdapterMode(self.mode))
        object.__setattr__(self, "camera_role", CameraRole(self.camera_role))

        if len(self.camera_resolution) != 2:
            raise ValidationError("camera_resolution must be a width/height pair")
        width, height = self.camera_resolution
        if width <= 0 or height <= 0:
            raise ValidationError("camera_resolution values must be positive")
        if self.arm_adapter_kind not in {
            ARM_ADAPTER_SIM,
            ARM_ADAPTER_METADATA_ONLY_SO_ARM,
        }:
            raise ValidationError(f"unknown arm_adapter_kind: {self.arm_adapter_kind!r}")


@dataclass(frozen=True)
class AdapterRuntime:
    camera: SimCameraAdapter
    vision: SimVisionAdapter
    arm: SimArmAdapter | MetadataOnlySOArmAdapter


def build_adapter_runtime(config: AdapterRuntimeConfig) -> AdapterRuntime:
    if config.mode == AdapterMode.HARDWARE:
        raise ValidationError(
            "hardware adapters require explicit safety gates and are not enabled yet",
            FailureCode.HARDWARE_MODE_NOT_ENABLED,
        )
    if config.mode != AdapterMode.SIMULATION:
        raise ValidationError(
            f"adapter runtime mode is not implemented: {config.mode.value}",
            FailureCode.INVALID_TASK,
        )

    if config.arm_adapter_kind == ARM_ADAPTER_METADATA_ONLY_SO_ARM:
        arm = MetadataOnlySOArmAdapter(
            adapter_id=config.arm_adapter_id,
            device_path=config.so_arm_device_path,
        )
    else:
        arm = SimArmAdapter(adapter_id=config.arm_adapter_id)

    return AdapterRuntime(
        camera=SimCameraAdapter(
            role=config.camera_role,
            resolution=config.camera_resolution,
        ),
        vision=SimVisionAdapter(detections=config.vision_detections),
        arm=arm,
    )
