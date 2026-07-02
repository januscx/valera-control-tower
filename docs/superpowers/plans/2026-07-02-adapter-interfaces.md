# Adapter Interfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project-owned adapter interface and result models for hardware integration without enabling real hardware control.

**Architecture:** The adapter layer exposes small, explicit contracts for identity, health, arm probing, camera roles, frame capture metadata, and vision detections. LeRobot, OpenCV, and real device details remain outside these domain models. Adapters return structured results; orchestration code will later translate results into immutable events.

**Tech Stack:** Python dataclasses, enums, runtime-checkable protocols, pytest. No new runtime dependencies.

## Global Constraints

- Do not control real robot hardware in this plan.
- Do not open cameras, serial ports, USB devices, or `/dev/*` paths in tests.
- Do not expose LeRobot types in adapter interfaces.
- Keep simulation, dry-run, probe, and hardware modes explicit.
- Keep event-log facts separate from adapter commands and results.
- CI and replay paths must not require physical devices.
- Use plain Python and existing pytest conventions.

---

## File Structure

- Create `robot/adapters/__init__.py`: package exports for adapter enums, dataclasses, and protocols.
- Create `robot/adapters/base.py`: common adapter identity, mode, health, and failure result models.
- Create `robot/adapters/arm.py`: arm-specific capabilities, state, probe result, command result, and protocol.
- Create `robot/adapters/camera.py`: camera roles, camera capabilities, frame artifact metadata, capture result, and protocol.
- Create `robot/adapters/vision.py`: vision detection models, vision result, and protocol.
- Create `tests/test_adapter_contracts.py`: focused tests proving the contracts are project-owned, structured, and safe by default.

---

### Task 1: Common Adapter Models

**Files:**
- Create: `robot/adapters/__init__.py`
- Create: `robot/adapters/base.py`
- Test: `tests/test_adapter_contracts.py`

**Interfaces:**
- Produces: `AdapterMode`, `AdapterType`, `AdapterStatus`, `AdapterIdentity`, `AdapterHealth`, `AdapterFailure`, `AdapterResult`
- Consumes: Python `dataclasses`, `enum.Enum`, `typing.Any`

- [ ] **Step 1: Write the failing test**

Add this test to `tests/test_adapter_contracts.py`:

```python
from robot.adapters.base import (
    AdapterFailure,
    AdapterHealth,
    AdapterIdentity,
    AdapterMode,
    AdapterResult,
    AdapterStatus,
    AdapterType,
)


def test_common_adapter_models_are_explicit_and_structured():
    identity = AdapterIdentity(
        adapter_id="sim-arm-001",
        adapter_type=AdapterType.ARM,
        mode=AdapterMode.SIMULATION,
        display_name="Simulated arm",
    )
    health = AdapterHealth(status=AdapterStatus.OK, message="ready")
    failure = AdapterFailure(code="adapter.timeout", message="probe timed out")
    result = AdapterResult(ok=False, identity=identity, health=health, failure=failure)

    assert identity.adapter_type == AdapterType.ARM
    assert identity.mode == AdapterMode.SIMULATION
    assert health.status == AdapterStatus.OK
    assert result.ok is False
    assert result.failure.code == "adapter.timeout"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_adapter_contracts.py::test_common_adapter_models_are_explicit_and_structured -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'robot.adapters'`.

- [ ] **Step 3: Write minimal implementation**

Create `robot/adapters/base.py`:

```python
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
```

Create `robot/adapters/__init__.py`:

```python
from robot.adapters.base import (
    AdapterFailure,
    AdapterHealth,
    AdapterIdentity,
    AdapterMode,
    AdapterResult,
    AdapterStatus,
    AdapterType,
)

__all__ = [
    "AdapterFailure",
    "AdapterHealth",
    "AdapterIdentity",
    "AdapterMode",
    "AdapterResult",
    "AdapterStatus",
    "AdapterType",
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_adapter_contracts.py::test_common_adapter_models_are_explicit_and_structured -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add robot/adapters/__init__.py robot/adapters/base.py tests/test_adapter_contracts.py
git commit -m "feat: add common adapter models"
```

---

### Task 2: Arm Adapter Contract

**Files:**
- Modify: `robot/adapters/__init__.py`
- Create: `robot/adapters/arm.py`
- Modify: `tests/test_adapter_contracts.py`

**Interfaces:**
- Consumes: `AdapterFailure`, `AdapterHealth`, `AdapterIdentity`
- Produces: `ArmJointState`, `ArmCapabilities`, `ArmState`, `ArmProbeResult`, `ArmCommandResult`, `ArmAdapter`

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/test_adapter_contracts.py`:

```python
from robot.adapters.arm import (
    ArmCapabilities,
    ArmCommandResult,
    ArmJointState,
    ArmProbeResult,
    ArmState,
)


def test_arm_probe_result_is_read_only_and_project_owned():
    identity = AdapterIdentity(
        adapter_id="so101-probe",
        adapter_type=AdapterType.ARM,
        mode=AdapterMode.PROBE,
    )
    health = AdapterHealth(status=AdapterStatus.OK, message="controller detected")
    capabilities = ArmCapabilities(
        can_read_state=True,
        can_enable_torque=False,
        can_move=False,
        joint_count=6,
        supported_commands=("probe", "read_state"),
    )
    state = ArmState(
        joints=(
            ArmJointState(name="base", position_deg=0.0),
            ArmJointState(name="shoulder", position_deg=15.0),
        ),
        gripper_open=None,
        torque_enabled=False,
    )
    result = ArmProbeResult(
        ok=True,
        identity=identity,
        health=health,
        capabilities=capabilities,
        state=state,
        runtime="lerobot",
    )

    assert result.capabilities.can_move is False
    assert result.state.torque_enabled is False
    assert result.runtime == "lerobot"


def test_arm_command_result_can_block_motion_without_success():
    identity = AdapterIdentity(
        adapter_id="so101-probe",
        adapter_type=AdapterType.ARM,
        mode=AdapterMode.PROBE,
    )
    health = AdapterHealth(status=AdapterStatus.BLOCKED, message="motion disabled")
    result = ArmCommandResult(
        ok=False,
        identity=identity,
        health=health,
        command_name="move_joints",
        executed=False,
        failure=AdapterFailure(
            code="hardware.motion.blocked",
            message="missing --allow-motion",
        ),
    )

    assert result.ok is False
    assert result.executed is False
    assert result.failure.code == "hardware.motion.blocked"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_adapter_contracts.py::test_arm_probe_result_is_read_only_and_project_owned tests/test_adapter_contracts.py::test_arm_command_result_can_block_motion_without_success -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'robot.adapters.arm'`.

- [ ] **Step 3: Write minimal implementation**

Create `robot/adapters/arm.py`:

```python
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
```

Add arm exports to `robot/adapters/__init__.py`:

```python
from robot.adapters.arm import (
    ArmAdapter,
    ArmCapabilities,
    ArmCommandResult,
    ArmJointState,
    ArmProbeResult,
    ArmState,
)
```

and add these names to `__all__`.

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_adapter_contracts.py::test_arm_probe_result_is_read_only_and_project_owned tests/test_adapter_contracts.py::test_arm_command_result_can_block_motion_without_success -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add robot/adapters/__init__.py robot/adapters/arm.py tests/test_adapter_contracts.py
git commit -m "feat: add arm adapter contract"
```

---

### Task 3: Camera And Vision Adapter Contracts

**Files:**
- Modify: `robot/adapters/__init__.py`
- Create: `robot/adapters/camera.py`
- Create: `robot/adapters/vision.py`
- Modify: `tests/test_adapter_contracts.py`

**Interfaces:**
- Consumes: `AdapterFailure`, `AdapterHealth`, `AdapterIdentity`
- Produces: `CameraRole`, `FrameArtifact`, `CameraCapabilities`, `CameraProbeResult`, `FrameCaptureResult`, `CameraAdapter`, `BoundingBox`, `VisionDetection`, `VisionResult`, `VisionAdapter`

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/test_adapter_contracts.py`:

```python
from robot.adapters.camera import (
    CameraCapabilities,
    CameraProbeResult,
    CameraRole,
    FrameArtifact,
    FrameCaptureResult,
)
from robot.adapters.vision import BoundingBox, VisionDetection, VisionResult


def test_camera_contract_uses_roles_and_artifact_references():
    identity = AdapterIdentity(
        adapter_id="wrist-camera-001",
        adapter_type=AdapterType.CAMERA,
        mode=AdapterMode.PROBE,
    )
    health = AdapterHealth(status=AdapterStatus.OK, message="camera detected")
    capabilities = CameraCapabilities(
        roles=(CameraRole.WRIST,),
        supports_frame_capture=True,
        supports_depth=False,
        resolutions=((640, 480), (1920, 1080)),
    )
    probe = CameraProbeResult(
        ok=True,
        identity=identity,
        health=health,
        capabilities=capabilities,
        device_label="USB2.0 UVC Camera",
    )
    artifact = FrameArtifact(
        artifact_uri="data/evidence/task-001/frame.png",
        frame_hash="sha256:abc",
        media_type="image/png",
        width=640,
        height=480,
    )
    capture = FrameCaptureResult(
        ok=True,
        identity=identity,
        health=health,
        camera_role=CameraRole.WRIST,
        artifact=artifact,
    )

    assert probe.capabilities.roles == (CameraRole.WRIST,)
    assert capture.artifact.artifact_uri.endswith("frame.png")
    assert capture.camera_role == CameraRole.WRIST


def test_vision_result_references_camera_artifact_and_detection_metadata():
    identity = AdapterIdentity(
        adapter_id="aruco-detector",
        adapter_type=AdapterType.VISION,
        mode=AdapterMode.SIMULATION,
    )
    health = AdapterHealth(status=AdapterStatus.OK, message="detected")
    detection = VisionDetection(
        object_id="VALERA-CUBE-001",
        label="aruco_marker",
        confidence=1.0,
        bounding_box=BoundingBox(x=10, y=20, width=30, height=40),
        metadata={"marker_id": 7},
    )
    result = VisionResult(
        ok=True,
        identity=identity,
        health=health,
        source_artifact_uri="data/evidence/task-001/frame.png",
        detections=(detection,),
    )

    assert result.detections[0].object_id == "VALERA-CUBE-001"
    assert result.detections[0].bounding_box.width == 30
    assert result.source_artifact_uri.endswith("frame.png")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_adapter_contracts.py::test_camera_contract_uses_roles_and_artifact_references tests/test_adapter_contracts.py::test_vision_result_references_camera_artifact_and_detection_metadata -v
```

Expected: FAIL with `ModuleNotFoundError` for `robot.adapters.camera` or `robot.adapters.vision`.

- [ ] **Step 3: Write minimal implementation**

Create `robot/adapters/camera.py`:

```python
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
```

Create `robot/adapters/vision.py`:

```python
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
```

Add camera and vision exports to `robot/adapters/__init__.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_adapter_contracts.py::test_camera_contract_uses_roles_and_artifact_references tests/test_adapter_contracts.py::test_vision_result_references_camera_artifact_and_detection_metadata -v
```

Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add robot/adapters/__init__.py robot/adapters/camera.py robot/adapters/vision.py tests/test_adapter_contracts.py
git commit -m "feat: add camera and vision adapter contracts"
```
