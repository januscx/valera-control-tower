from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.render import render_dashboard_from_replay
from robot.adapter_runtime import AdapterRuntimeConfig, build_adapter_runtime
from robot.adapter_sim_mission import run_adapter_simulated_mission
from robot.adapters import AdapterMode, CameraRole
from robot.adapters.vision import BoundingBox, VisionDetection
from robot.models import ExecutionMode, Task, Zone


TASK_ID = "adapter-sim-demo-001"
OBJECT_ID = "VALERA-CUBE-001"


@dataclass(frozen=True)
class AdapterSimDemoResult:
    task_id: str
    final_status: str
    event_count: int
    replay_path: Path
    dashboard_path: Path


def run_adapter_sim_demo(output_root: Path = PROJECT_ROOT) -> AdapterSimDemoResult:
    output_root = Path(output_root)
    replay_path = output_root / "data" / "runs" / TASK_ID / "replay.json"
    dashboard_path = output_root / "data" / "runs" / TASK_ID / "dashboard.html"

    runtime = build_adapter_runtime(
        AdapterRuntimeConfig(
            mode=AdapterMode.SIMULATION,
            camera_role=CameraRole.WRIST,
            camera_resolution=(320, 240),
            vision_detections=(_demo_detection(),),
            arm_adapter_id="sim-arm-demo",
        )
    )
    task = Task(
        task_id=TASK_ID,
        object_id=OBJECT_ID,
        pickup_zone=Zone.PICKUP_ZONE,
        delivery_zone=Zone.DELIVERY_ZONE,
        mode=ExecutionMode.SIMULATION,
        description="Adapter-backed simulation demo for camera, vision, and arm boundaries",
    )
    event_log = run_adapter_simulated_mission(
        task=task,
        camera=runtime.camera,
        vision=runtime.vision,
        arm=runtime.arm,
    )

    replay_path.parent.mkdir(parents=True, exist_ok=True)
    replay_path.write_text(
        json.dumps([event.to_dict() for event in event_log.events], indent=2) + "\n",
        encoding="utf-8",
    )
    summary = render_dashboard_from_replay(replay_path, dashboard_path)

    return AdapterSimDemoResult(
        task_id=summary.task_id,
        final_status=summary.final_status,
        event_count=summary.event_count,
        replay_path=replay_path,
        dashboard_path=dashboard_path,
    )


def _demo_detection() -> VisionDetection:
    return VisionDetection(
        object_id=OBJECT_ID,
        label="sim_cube",
        confidence=0.97,
        bounding_box=BoundingBox(x=10, y=20, width=30, height=40),
        metadata={"marker_id": 7, "source": "adapter_sim_demo"},
    )


def main() -> None:
    result = run_adapter_sim_demo(PROJECT_ROOT)

    print("PASS: Adapter simulation demo")
    print(f"Task id: {result.task_id}")
    print(f"Final status: {result.final_status}")
    print(f"Event count: {result.event_count}")
    print(f"Replay path: {result.replay_path}")
    print(f"Dashboard path: {result.dashboard_path}")


if __name__ == "__main__":
    main()
