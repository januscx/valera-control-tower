from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AdapterMode(str, Enum):
    SIMULATION = "simulation"
    DRY_RUN = "dry_run"
    PROBE = "probe"
    HARDWARE = "hardware"


class AdapterType(str, Enum):
    ARM = "arm"
    CAMERA = "camera"
    VISION = "vision"
    BASE_MOTION = "base_motion"


class AdapterStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AdapterIdentity:
    adapter_id: str
    adapter_type: AdapterType
    mode: AdapterMode
    display_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterHealth:
    status: AdapterStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterFailure:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    identity: AdapterIdentity
    health: AdapterHealth
    failure: AdapterFailure | None = None
    details: dict[str, Any] = field(default_factory=dict)
