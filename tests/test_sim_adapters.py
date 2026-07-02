from robot.adapters import (
    AdapterMode,
    AdapterStatus,
    AdapterType,
    ArmProbeResult,
    ArmState,
    CameraRole,
    FrameCaptureResult,
    VisionDetection,
    VisionResult,
)
from robot.adapters.sim_arm import SimArmAdapter
from robot.adapters.sim_camera import SimCameraAdapter
from robot.adapters.sim_vision import SimVisionAdapter
from robot.adapters.vision import BoundingBox


def test_sim_arm_adapter_returns_project_owned_probe_result():
    adapter = SimArmAdapter()

    assert adapter.identity.adapter_type == AdapterType.ARM
    assert adapter.identity.mode == AdapterMode.SIMULATION

    capabilities = adapter.capabilities()
    assert capabilities.can_read_state is True
    assert capabilities.can_enable_torque is False
    assert capabilities.can_move is True

    health = adapter.health()
    assert health.status == AdapterStatus.OK

    probe = adapter.probe()
    assert isinstance(probe, ArmProbeResult)
    assert isinstance(probe.state, ArmState)
    assert probe.identity.mode == AdapterMode.SIMULATION
    assert probe.capabilities.can_enable_torque is False
    assert probe.state.torque_enabled is False
    assert probe.runtime == "simulation"


def test_sim_camera_adapter_uses_camera_role_and_synthetic_artifact_uri():
    adapter = SimCameraAdapter(role=CameraRole.WRIST, resolution=(320, 240))

    assert adapter.identity.adapter_type == AdapterType.CAMERA
    assert adapter.identity.mode == AdapterMode.SIMULATION
    assert adapter.identity.metadata["role"] == CameraRole.WRIST.value
    assert not hasattr(adapter, "camera_index")

    probe = adapter.probe()
    assert probe.capabilities.roles == (CameraRole.WRIST,)
    assert probe.device_label == "simulated:wrist"

    capture = adapter.capture_frame()
    assert isinstance(capture, FrameCaptureResult)
    assert capture.identity.mode == AdapterMode.SIMULATION
    assert capture.camera_role == CameraRole.WRIST
    assert capture.artifact is not None
    assert capture.artifact.artifact_uri == "sim://camera/wrist/frame-000001"
    assert capture.artifact.media_type == "application/x.valera.sim-frame"
    assert capture.artifact.width == 320
    assert capture.artifact.height == 240
    assert capture.artifact.metadata["camera_role"] == CameraRole.WRIST.value


def test_sim_vision_adapter_returns_configured_deterministic_detections():
    detection = VisionDetection(
        object_id="VALERA-CUBE-001",
        label="sim_cube",
        confidence=0.93,
        bounding_box=BoundingBox(x=12, y=24, width=36, height=48),
        metadata={"fixture": "tabletop"},
    )
    adapter = SimVisionAdapter(detections=(detection,))

    first = adapter.detect("sim://camera/wrist/frame-000001")
    second = adapter.detect("sim://camera/wrist/frame-000001")

    assert isinstance(first, VisionResult)
    assert first == second
    assert first.identity.adapter_type == AdapterType.VISION
    assert first.identity.mode == AdapterMode.SIMULATION
    assert first.source_artifact_uri == "sim://camera/wrist/frame-000001"
    assert first.detections == (detection,)
    assert first.detections[0].metadata["fixture"] == "tabletop"
