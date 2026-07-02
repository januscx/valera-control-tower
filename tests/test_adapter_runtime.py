import pytest

from robot.adapter_runtime import AdapterRuntimeConfig, build_adapter_runtime
from robot.adapters import (
    AdapterMode,
    CameraRole,
    SimArmAdapter,
    SimCameraAdapter,
    SimVisionAdapter,
)
from robot.adapters.vision import BoundingBox, VisionDetection
from robot.models import FailureCode, ValidationError


def make_detection() -> VisionDetection:
    return VisionDetection(
        object_id="VALERA-CUBE-001",
        label="sim_cube",
        confidence=0.95,
        bounding_box=BoundingBox(x=1, y=2, width=3, height=4),
        metadata={"marker_id": 7},
    )


def test_adapter_runtime_config_builds_simulation_adapters_from_roles():
    config = AdapterRuntimeConfig(
        mode=AdapterMode.SIMULATION,
        camera_role=CameraRole.WRIST,
        camera_resolution=(320, 240),
        vision_detections=(make_detection(),),
        arm_adapter_id="sim-arm-runtime",
    )

    runtime = build_adapter_runtime(config)

    assert isinstance(runtime.camera, SimCameraAdapter)
    assert isinstance(runtime.vision, SimVisionAdapter)
    assert isinstance(runtime.arm, SimArmAdapter)
    assert runtime.camera.identity.mode == AdapterMode.SIMULATION
    assert runtime.camera.identity.metadata["role"] == CameraRole.WRIST.value
    assert runtime.camera.capabilities().resolutions == ((320, 240),)
    assert runtime.arm.identity.adapter_id == "sim-arm-runtime"
    assert runtime.vision.detect("sim://frame").detections == (make_detection(),)
    assert not hasattr(config, "camera_index")


def test_adapter_runtime_defaults_to_simulation_only_components():
    runtime = build_adapter_runtime(AdapterRuntimeConfig())

    assert runtime.camera.identity.mode == AdapterMode.SIMULATION
    assert runtime.camera.identity.metadata["role"] == CameraRole.WRIST.value
    assert runtime.arm.capabilities().can_enable_torque is False


def test_adapter_runtime_fails_closed_for_hardware_mode_until_safety_gates_exist():
    config = AdapterRuntimeConfig(mode=AdapterMode.HARDWARE)

    with pytest.raises(ValidationError) as exc:
        build_adapter_runtime(config)

    assert exc.value.code == FailureCode.HARDWARE_MODE_NOT_ENABLED
