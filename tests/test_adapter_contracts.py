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
