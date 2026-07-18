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
        "ACTIVE",
        "head.pose",
        "neck.target",
        "SAFE_STOPPED",
        "safety.stop",
        "INVALID_PAYLOAD",
        "emergency_stop",
        "ESTOP_LATCHED",
    ):
        assert text in source


def test_smoke_uses_isolated_domain_and_configurable_rosbridge_port():
    source = (ROOT / "scripts" / "smoke_vr_gateway_ros2.py").read_text(
        encoding="utf-8"
    )
    assert "ROS_DOMAIN_ID" in source
    assert "--ros-domain-id" in source
    assert "--smoke-port" in source
    assert "rosbridge_port:=" in source
    assert "DEFAULT_SMOKE_PORT" in source


def test_websocket_smoke_uses_std_msgs_string_wire_shape():
    source = (ROOT / "scripts" / "smoke_vr_gateway_ros2.py").read_text(
        encoding="utf-8"
    )
    assert '"msg": {"data": session_start()}' in source
    assert 'json.loads(document["msg"]["data"])' in source
    assert "client.close()" in source
    assert '"id": "subscribe-1"' in source
    assert "time.sleep(0.2)" in source


def test_smoke_asserts_first_session_transition_and_correlation():
    source = (ROOT / "scripts" / "smoke_vr_gateway_ros2.py").read_text(
        encoding="utf-8"
    )
    assert 'first["event_type"] == "gateway.state"' in source
    assert 'first["state"] == "AWAITING_RECENTER"' in source
    assert 'first["sequence"] == 1' in source


def test_smoke_has_no_unused_safety_stop_command_helper():
    source = (ROOT / "scripts" / "smoke_vr_gateway_ros2.py").read_text(
        encoding="utf-8"
    )
    assert "def safety_stop" not in source
