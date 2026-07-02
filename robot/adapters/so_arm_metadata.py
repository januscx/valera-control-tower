from __future__ import annotations

import os
import stat
from pathlib import Path

from robot.adapters.arm import ArmCapabilities, ArmProbeResult, ArmState
from robot.adapters.base import (
    AdapterFailure,
    AdapterHealth,
    AdapterIdentity,
    AdapterMode,
    AdapterStatus,
    AdapterType,
)


class MetadataOnlySOArmAdapter:
    """SO-ARM adapter skeleton that collects path metadata only."""

    def __init__(
        self,
        device_path: str = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0",
        adapter_id: str = "metadata-only-so-arm",
    ) -> None:
        self.device_path = device_path
        self.identity = AdapterIdentity(
            adapter_id=adapter_id,
            adapter_type=AdapterType.ARM,
            mode=AdapterMode.PROBE,
            display_name="Metadata-only SO-ARM adapter",
            metadata={
                "device_path": device_path,
                "control_boundary": "metadata_only",
            },
        )

    def capabilities(self) -> ArmCapabilities:
        return ArmCapabilities(
            can_read_state=False,
            can_enable_torque=False,
            can_move=False,
            joint_count=0,
            supported_commands=("probe_metadata",),
            notes=(
                "Metadata-only adapter skeleton; does not open serial.",
                "Does not read/write device bytes, enable torque, or command movement.",
            ),
        )

    def health(self) -> AdapterHealth:
        metadata = self._path_metadata()
        if metadata["path_exists"]:
            return AdapterHealth(
                status=AdapterStatus.OK,
                message="SO-ARM path metadata available",
                details=metadata,
            )
        return AdapterHealth(
            status=AdapterStatus.UNAVAILABLE,
            message="SO-ARM device path is missing",
            details=metadata,
        )

    def probe(self) -> ArmProbeResult:
        metadata = self._path_metadata()
        health = self.health()
        failure = None
        if not metadata["path_exists"]:
            failure = AdapterFailure(
                code="hardware.device_path_missing",
                message="SO-ARM device path is missing",
                details=metadata,
            )

        return ArmProbeResult(
            ok=metadata["path_exists"],
            identity=self.identity,
            health=health,
            capabilities=self.capabilities(),
            state=ArmState(
                joints=(),
                gripper_open=None,
                torque_enabled=False,
                metadata=metadata,
            ),
            runtime="metadata_only",
            failure=failure,
        )

    def _path_metadata(self) -> dict[str, object]:
        path = Path(self.device_path)
        try:
            info = path.lstat()
        except FileNotFoundError:
            return {
                "device_path": self.device_path,
                "resolved_path": None,
                "path_exists": False,
                "is_symlink": False,
                "mode": None,
                "readable": False,
                "writable": False,
                "serial_opened": False,
                "serial_commands_sent": False,
                "torque_enabled": False,
                "movement_commanded": False,
                "actuator_calls": False,
            }

        is_symlink = stat.S_ISLNK(info.st_mode)
        resolved_path = str(path.resolve()) if is_symlink else str(path)
        target_info = path.stat()
        return {
            "device_path": self.device_path,
            "resolved_path": resolved_path,
            "path_exists": True,
            "is_symlink": is_symlink,
            "mode": oct(stat.S_IMODE(target_info.st_mode)),
            "readable": os.access(self.device_path, os.R_OK),
            "writable": os.access(self.device_path, os.W_OK),
            "serial_opened": False,
            "serial_commands_sent": False,
            "torque_enabled": False,
            "movement_commanded": False,
            "actuator_calls": False,
        }
