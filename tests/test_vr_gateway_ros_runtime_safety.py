"""Static checks that runtime packaging stays inside the simulation boundary."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ros_package_does_not_add_hardware_or_base_arm_imports():
    files = list((ROOT / "ros2").rglob("*.py")) + [
        ROOT / "scripts" / "smoke_vr_gateway_ros2.py"
    ]
    forbidden = {
        "robot.adapters.base",
        "robot.adapters.arm",
        "robot.adapters.camera",
        "serial",
        "gpiozero",
        "RPi",
        "dynamixel_sdk",
    }
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            assert not forbidden.intersection(modules), (path, modules)


def test_smoke_scenarios_name_required_ordered_events_and_safety_states():
    source = (ROOT / "scripts" / "smoke_vr_gateway_ros2.py").read_text(
        encoding="utf-8"
    )
    for text in (
        "session.start",
        "AWAITING_RECENTER",
        "head.recenter",
        "HEAD_ACTIVE",
        "head.pose",
        "neck.target",
        "SAFE_STOPPED",
        "safety.stop",
        "INVALID_PAYLOAD",
        "emergency_stop",
        "ESTOP_LATCHED",
    ):
        assert text in source

