from __future__ import annotations

import hashlib

from robot.adapters.base import (
    AdapterHealth,
    AdapterIdentity,
    AdapterMode,
    AdapterStatus,
    AdapterType,
)
from robot.adapters.camera import (
    CameraCapabilities,
    CameraProbeResult,
    CameraRole,
    FrameArtifact,
    FrameCaptureResult,
)


class SimCameraAdapter:
    """Role-based synthetic camera adapter with no device access."""

    def __init__(
        self,
        role: CameraRole,
        adapter_id: str | None = None,
        resolution: tuple[int, int] = (640, 480),
        supports_depth: bool = False,
    ) -> None:
        self.role = role
        self.resolution = resolution
        self.supports_depth = supports_depth
        self._frame_number = 0
        self.identity = AdapterIdentity(
            adapter_id=adapter_id or f"sim-camera-{role.value}",
            adapter_type=AdapterType.CAMERA,
            mode=AdapterMode.SIMULATION,
            display_name=f"Simulated {role.value} camera",
            metadata={"role": role.value},
        )

    def capabilities(self) -> CameraCapabilities:
        return CameraCapabilities(
            roles=(self.role,),
            supports_frame_capture=True,
            supports_depth=self.supports_depth,
            resolutions=(self.resolution,),
            notes=("Synthetic artifact references only; no camera device is opened.",),
        )

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            status=AdapterStatus.OK,
            message="simulation camera ready",
            details={"camera_role": self.role.value},
        )

    def probe(self) -> CameraProbeResult:
        return CameraProbeResult(
            ok=True,
            identity=self.identity,
            health=self.health(),
            capabilities=self.capabilities(),
            device_label=f"simulated:{self.role.value}",
        )

    def capture_frame(self) -> FrameCaptureResult:
        self._frame_number += 1
        width, height = self.resolution
        artifact_uri = f"sim://camera/{self.role.value}/frame-{self._frame_number:06d}"
        frame_hash = "sha256:" + hashlib.sha256(artifact_uri.encode("utf-8")).hexdigest()
        artifact = FrameArtifact(
            artifact_uri=artifact_uri,
            frame_hash=frame_hash,
            media_type="application/x.valera.sim-frame",
            width=width,
            height=height,
            metadata={
                "camera_role": self.role.value,
                "frame_number": self._frame_number,
                "synthetic": True,
            },
        )
        return FrameCaptureResult(
            ok=True,
            identity=self.identity,
            health=self.health(),
            camera_role=self.role,
            artifact=artifact,
        )
