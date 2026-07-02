from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from robot.adapters.base import AdapterFailure, AdapterHealth, AdapterIdentity


class CameraRole(str, Enum):
    FRONT_NAV = "front_nav"
    WRIST = "wrist"
    OVERHEAD = "overhead"
    OPERATOR_VIEW = "operator_view"


@dataclass(frozen=True)
class CameraCapabilities:
    roles: tuple[CameraRole, ...]
    supports_frame_capture: bool
    supports_depth: bool
    resolutions: tuple[tuple[int, int], ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class FrameArtifact:
    artifact_uri: str
    frame_hash: str
    media_type: str
    width: int
    height: int
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CameraProbeResult:
    ok: bool
    identity: AdapterIdentity
    health: AdapterHealth
    capabilities: CameraCapabilities
    device_label: str = ""
    failure: AdapterFailure | None = None


@dataclass(frozen=True)
class FrameCaptureResult:
    ok: bool
    identity: AdapterIdentity
    health: AdapterHealth
    camera_role: CameraRole
    artifact: FrameArtifact | None = None
    failure: AdapterFailure | None = None


@runtime_checkable
class CameraAdapter(Protocol):
    identity: AdapterIdentity

    def capabilities(self) -> CameraCapabilities:
        ...

    def health(self) -> AdapterHealth:
        ...

    def probe(self) -> CameraProbeResult:
        ...
