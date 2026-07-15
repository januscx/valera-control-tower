import ast
import json
from pathlib import Path

from robot.vr_gateway.simulation import (
    SIMULATION_NECK_CONFIG,
    run_simulated_head_sequence,
)


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
