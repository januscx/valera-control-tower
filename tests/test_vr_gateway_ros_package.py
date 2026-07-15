"""Static contract tests for the installable ROS 2 package."""

import ast
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "ros2" / "valera_vr_gateway"


def test_ament_python_metadata_declares_safe_runtime_dependencies():
    package = ET.parse(PACKAGE / "package.xml").getroot()

    assert package.findtext("name") == "valera_vr_gateway"
    assert package.findtext("export/build_type") == "ament_python"
    dependencies = {
        node.text for node in package if node.tag in {"depend", "exec_depend"}
    }
    assert {"rclpy", "std_msgs"}.issubset(dependencies)
    assert not dependencies & {
        "geometry_msgs",
        "sensor_msgs",
        "nav_msgs",
        "ros2_control",
        "dynamixel_sdk",
    }


def test_setup_discovers_existing_robot_modules_without_copying_them():
    setup_source = (PACKAGE / "setup.py").read_text(encoding="utf-8")
    assert "find_packages" in setup_source
    assert "robot" in setup_source
    assert "copy" not in setup_source.lower()
    assert "robot.vr_gateway" not in (PACKAGE / "robot").as_posix()


def test_console_entry_point_is_the_existing_node_main():
    setup_source = (PACKAGE / "setup.py").read_text(encoding="utf-8")
    tree = ast.parse(setup_source)
    source = ast.unparse(tree)
    assert "valera_vr_gateway_node = robot.vr_gateway_ros.node:main" in source


def test_package_installs_resource_marker_and_launch_files():
    assert (PACKAGE / "resource" / "valera_vr_gateway").is_file()
    assert (PACKAGE / "launch" / "valera_vr_gateway.launch.py").is_file()
    assert (PACKAGE / "launch" / "valera_vr_gateway_with_rosbridge.launch.py").is_file()
    setup_source = (PACKAGE / "setup.py").read_text(encoding="utf-8")
    assert '"resource/valera_vr_gateway"' in setup_source
    assert '"share/valera_vr_gateway/launch"' in setup_source
    assert '.glob("*.launch.py")' in setup_source


def test_launch_boundaries_only_use_gateway_topics_and_no_hardware_modules():
    gateway = (PACKAGE / "launch" / "valera_vr_gateway.launch.py").read_text(
        encoding="utf-8"
    )
    rosbridge = (
        PACKAGE / "launch" / "valera_vr_gateway_with_rosbridge.launch.py"
    ).read_text(encoding="utf-8")
    combined = gateway + rosbridge
    assert "/valera/vr_gateway/command" in combined
    assert "/valera/vr_gateway/event" in combined
    for forbidden in ("/cmd_vel", "base", "arm", "camera", "serial", "GPIO"):
        assert forbidden not in combined
    assert "127.0.0.1" in rosbridge
    assert "topics_glob" in rosbridge
    assert "services_glob" in rosbridge
    assert "params_glob" in rosbridge


def test_smoke_harness_is_test_only_and_has_cleanup_boundary():
    source = (ROOT / "scripts" / "smoke_vr_gateway_ros2.py").read_text(
        encoding="utf-8"
    )
    assert "atexit" in source or "try:" in source
    assert "SIGTERM" in source
    assert "valera_vr_gateway_node" in source
    assert "websocket" in source.lower()
    assert "robot.vr_gateway_ros.node" not in source
