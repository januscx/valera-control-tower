from __future__ import annotations

from robot.adapters.base import (
    AdapterHealth,
    AdapterIdentity,
    AdapterMode,
    AdapterStatus,
    AdapterType,
)
from robot.adapters.vision import VisionDetection, VisionResult


class SimVisionAdapter:
    """Deterministic vision adapter backed by configured detections."""

    def __init__(
        self,
        detections: tuple[VisionDetection, ...] = (),
        adapter_id: str = "sim-vision",
    ) -> None:
        self._detections = detections
        self.identity = AdapterIdentity(
            adapter_id=adapter_id,
            adapter_type=AdapterType.VISION,
            mode=AdapterMode.SIMULATION,
            display_name="Simulated vision",
            metadata={"detection_source": "configured"},
        )

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            status=AdapterStatus.OK,
            message="simulation vision ready",
            details={"configured_detections": len(self._detections)},
        )

    def detect(self, source_artifact_uri: str) -> VisionResult:
        return VisionResult(
            ok=True,
            identity=self.identity,
            health=self.health(),
            source_artifact_uri=source_artifact_uri,
            detections=self._detections,
        )
