import json
from pathlib import Path

from scripts.run_adapter_sim_demo import run_adapter_sim_demo


def test_adapter_sim_demo_writes_replay_and_dashboard(tmp_path: Path):
    result = run_adapter_sim_demo(tmp_path)

    assert result.task_id == "adapter-sim-demo-001"
    assert result.final_status == "completed"
    assert result.event_count == 18
    assert result.replay_path == tmp_path / "data" / "runs" / result.task_id / "replay.json"
    assert result.dashboard_path == tmp_path / "data" / "runs" / result.task_id / "dashboard.html"
    assert result.replay_path.is_file()
    assert result.dashboard_path.is_file()


def test_adapter_sim_demo_replay_proves_synthetic_camera_and_simulated_arm(tmp_path: Path):
    result = run_adapter_sim_demo(tmp_path)
    replay = json.loads(result.replay_path.read_text(encoding="utf-8"))

    camera_frame = next(event for event in replay if event["event_type"] == "camera.frame.captured")
    vision_detected = next(
        event for event in replay if event["event_type"] == "vision.object.detected"
    )
    arm_probe = next(event for event in replay if event["event_type"] == "hardware.probe.completed")
    object_grasped = next(event for event in replay if event["event_type"] == "object.grasped")

    assert camera_frame["payload"]["camera_role"] == "wrist"
    assert camera_frame["payload"]["artifact_uri"] == "sim://camera/wrist/frame-000001"
    assert "camera_index" not in camera_frame["payload"]
    assert vision_detected["payload"]["source_artifact_uri"] == camera_frame["payload"]["artifact_uri"]
    assert vision_detected["payload"]["detections"][0]["metadata"]["marker_id"] == 7
    assert arm_probe["payload"]["adapter_mode"] == "simulation"
    assert arm_probe["payload"]["can_enable_torque"] is False
    assert object_grasped["payload"]["torque_enabled"] is False
