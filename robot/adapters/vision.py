from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from robot.adapters.base import AdapterFailure, AdapterHealth, AdapterIdentity


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class VisionDetection:
    object_id: str
    label: str
    confidence: float
    bounding_box: BoundingBox | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class VisionResult:
    ok: bool
    identity: AdapterIdentity
    health: AdapterHealth
    source_artifact_uri: str
    detections: tuple[VisionDetection, ...] = ()
    failure: AdapterFailure | None = None


@runtime_checkable
class VisionAdapter(Protocol):
    identity: AdapterIdentity

    def health(self) -> AdapterHealth:
        ...

    def detect(self, source_artifact_uri: str) -> VisionResult:
        ...
