import ast
import json
from pathlib import Path

from robot.vr_gateway.messages import (
    CommandEnvelope,
    CommandName,
    ControlMode,
    ModeSetPayload,
    ModeTransition,
    PosePayload,
    Quaternion,
    SessionStartPayload,
)
from robot.vr_gateway.simulation import (
    SIMULATION_NECK_CONFIG,
    build_simulated_vr_gateway,
    run_simulated_arm_sequence,
    run_simulated_drive_sequence,
    run_simulated_head_sequence,
)
from robot.vr_gateway.simulation import _SimulationClock


def test_simulated_head_sequence_reaches_watchdog_safe_stop():
    events = run_simulated_head_sequence()

    assert [event["event_type"] for event in events] == [
        "gateway.state",
        "gateway.state",
        "neck.target",
        "gateway.state",
        "safety.stop",
    ]
    assert [event.get("state") for event in events if "state" in event] == [
        "AWAITING_RECENTER",
        "ACTIVE",
        "SAFE_STOPPED",
    ]
    assert all(event["schema_version"] == "0.1" for event in events)

    target = events[2]
    assert SIMULATION_NECK_CONFIG.min_pan_degrees <= target["pan_degrees"] <= SIMULATION_NECK_CONFIG.max_pan_degrees
    assert SIMULATION_NECK_CONFIG.min_tilt_degrees <= target["tilt_degrees"] <= SIMULATION_NECK_CONFIG.max_tilt_degrees
    assert events[-1]["reason"] == "WATCHDOG"
    assert events[-1]["neck_action"] == "HOLD_LAST_POSITION"
    assert not any(
        event["event_type"] in {"base.target", "arm.target"} for event in events
    )
    json.dumps(events)


def test_simulated_head_sequence_is_repeatable():
    assert run_simulated_head_sequence() == run_simulated_head_sequence()


def test_simulated_drive_sequence():
    events = run_simulated_drive_sequence()

    assert [event["event_type"] for event in events] == [
        "gateway.state",
        "gateway.state",
        "base.target",
    ]
    assert all(event["schema_version"] == "0.1" for event in events)

    target = events[2]
    assert target["throttle"] > 0.0
    assert target["steering"] == 0.0
    assert target["deadman"] is True
    assert target["command_zeroed"] is False
    assert not any(
        event["event_type"] in {"neck.target", "arm.target"} for event in events
    )
    json.dumps(events)


def test_simulated_arm_sequence():
    events = run_simulated_arm_sequence()

    assert [event["event_type"] for event in events] == [
        "gateway.state",
        "gateway.state",
        "arm.target",
    ]
    assert all(event["schema_version"] == "0.1" for event in events)

    target = events[2]
    assert target["kind"] == "JOINT_JOG"
    assert target["deadman"] is True
    assert target["command_zeroed"] is False
    assert target["joint_velocity"] == {"shoulder_pan": 0.5}
    assert not any(
        event["event_type"] in {"neck.target", "base.target"} for event in events
    )
    json.dumps(events)


def test_simulated_drive_to_arm_transition():
    clock = _SimulationClock()
    gateway = build_simulated_vr_gateway(clock)
    gateway.handle(
        CommandEnvelope(
            "0.1", CommandName.SESSION_START, "sim-drive",
            1, 1000, SessionStartPayload("drive"),
        )
    )
    gateway.handle(
        CommandEnvelope(
            "0.1", CommandName.HEAD_RECENTER, "sim-drive",
            2, 1001, PosePayload("quest_local", Quaternion(0, 0, 0, 1)),
        )
    )
    assert gateway.current_mode is ControlMode.DRIVE

    events = gateway.handle(
        CommandEnvelope(
            "0.1", CommandName.MODE_SET, "sim-drive",
            3, 1002, ModeSetPayload("arm"),
        )
    )
    assert gateway.transition is ModeTransition.STOPPING_BASE

    gateway.handle_base_stop_ack(True, False)
    clock.advance_ms(600)
    events = gateway.poll()

    assert gateway.current_mode is ControlMode.ARM
    assert gateway.transition is ModeTransition.NONE


def test_vr_gateway_import_roots_are_explicitly_allowed():
    # The wire codec is part of the package and must reach the standard JSON
    # parser, so ``json`` is allowed. ROS, network, serial, LeRobot, and
    # hardware roots remain forbidden and are not in this set.
    allowed_import_roots = {
        "__future__",
        "dataclasses",
        "enum",
        "json",
        "math",
        "robot",
        "time",
        "typing",
    }
    package_dir = Path(__file__).parents[1] / "robot" / "vr_gateway"

    found = set()
    for source_path in package_dir.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    found.add("<relative-import>")
                else:
                    found.add(node.module.split(".", 1)[0])

    assert found <= allowed_import_roots, (
        f"undeclared import roots: {found - allowed_import_roots}"
    )
