from robot.adapters import CameraRole, SimArmAdapter, SimCameraAdapter, SimVisionAdapter
from robot.adapters.vision import BoundingBox, VisionDetection
from robot.adapter_sim_mission import run_adapter_simulated_mission
from robot.events import EventType
from robot.models import ExecutionMode, Task, Zone


def make_task() -> Task:
    return Task(
        task_id="adapter-sim-task-001",
        object_id="VALERA-CUBE-001",
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.SIMULATION,
    )


def make_detection() -> VisionDetection:
    return VisionDetection(
        object_id="VALERA-CUBE-001",
        label="sim_cube",
        confidence=0.97,
        bounding_box=BoundingBox(x=10, y=20, width=30, height=40),
        metadata={"marker_id": 7},
    )


def test_adapter_simulated_mission_records_adapter_backed_success_flow():
    event_log = run_adapter_simulated_mission(
        task=make_task(),
        camera=SimCameraAdapter(role=CameraRole.WRIST, resolution=(320, 240)),
        vision=SimVisionAdapter(detections=(make_detection(),)),
        arm=SimArmAdapter(),
    )

    assert [event.event_type for event in event_log.events] == [
        EventType.TASK_CREATED,
        EventType.PLAN_CREATED,
        EventType.TASK_ACCEPTED,
        EventType.ROUTE_STARTED,
        EventType.ROUTE_ARRIVED,
        EventType.OBJECT_SEARCH_STARTED,
        EventType.CAMERA_PROBE_COMPLETED,
        EventType.CAMERA_FRAME_CAPTURED,
        EventType.VISION_OBJECT_DETECTED,
        EventType.OBJECT_FOUND,
        EventType.HARDWARE_PROBE_COMPLETED,
        EventType.GRASP_STARTED,
        EventType.OBJECT_GRASPED,
        EventType.DELIVERY_STARTED,
        EventType.ROUTE_ARRIVED,
        EventType.OBJECT_RELEASED,
        EventType.DELIVERY_COMPLETED,
        EventType.TASK_COMPLETED,
    ]
    assert event_log.terminal_event_type == EventType.TASK_COMPLETED
    event_log.validate()


def test_adapter_simulated_mission_payloads_use_adapter_results_not_hardware_objects():
    event_log = run_adapter_simulated_mission(
        task=make_task(),
        camera=SimCameraAdapter(role=CameraRole.WRIST, resolution=(320, 240)),
        vision=SimVisionAdapter(detections=(make_detection(),)),
        arm=SimArmAdapter(adapter_id="sim-arm-test"),
    )

    camera_event = next(
        event for event in event_log.events if event.event_type == EventType.CAMERA_FRAME_CAPTURED
    )
    camera_probe_event = next(
        event for event in event_log.events if event.event_type == EventType.CAMERA_PROBE_COMPLETED
    )
    vision_event = next(
        event for event in event_log.events if event.event_type == EventType.VISION_OBJECT_DETECTED
    )
    arm_probe_event = next(
        event for event in event_log.events if event.event_type == EventType.HARDWARE_PROBE_COMPLETED
    )
    grasped_event = next(
        event for event in event_log.events if event.event_type == EventType.OBJECT_GRASPED
    )

    assert camera_probe_event.payload["adapter_mode"] == "simulation"
    assert camera_probe_event.payload["camera_role"] == "wrist"
    assert camera_probe_event.payload["device_label"] == "simulated:wrist"

    assert camera_event.payload["adapter_mode"] == "simulation"
    assert camera_event.payload["camera_role"] == "wrist"
    assert camera_event.payload["artifact_uri"] == "sim://camera/wrist/frame-000001"
    assert "camera_index" not in camera_event.payload

    assert vision_event.payload["adapter_mode"] == "simulation"
    assert vision_event.payload["source_artifact_uri"] == "sim://camera/wrist/frame-000001"
    assert vision_event.payload["detections"][0]["object_id"] == "VALERA-CUBE-001"
    assert vision_event.payload["detections"][0]["metadata"] == {"marker_id": 7}

    assert arm_probe_event.payload["adapter_id"] == "sim-arm-test"
    assert arm_probe_event.payload["adapter_mode"] == "simulation"
    assert arm_probe_event.payload["can_enable_torque"] is False

    assert grasped_event.payload["adapter_id"] == "sim-arm-test"
    assert grasped_event.payload["command_name"] == "simulate_grasp"
    assert grasped_event.payload["torque_enabled"] is False


def test_adapter_simulated_mission_fails_closed_when_object_is_not_detected():
    event_log = run_adapter_simulated_mission(
        task=make_task(),
        camera=SimCameraAdapter(role=CameraRole.WRIST),
        vision=SimVisionAdapter(detections=()),
        arm=SimArmAdapter(),
    )

    assert event_log.events[-2].event_type == EventType.OBJECT_NOT_FOUND
    assert event_log.events[-1].event_type == EventType.TASK_FAILED
    assert event_log.events[-1].error is not None
    assert event_log.events[-1].error.code.value == "object_not_found"
    assert EventType.GRASP_STARTED not in [event.event_type for event in event_log.events]
    event_log.validate()
