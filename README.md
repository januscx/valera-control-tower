# Valera Control Tower

Valera Control Tower is a local-first hybrid robotics evidence demo for a
simulated robot mission with fixture-based real vision evidence.

The current MVP demonstrates a deterministic task execution flow, replayable
event logs, local evidence references, OpenCV marker detection against a fixture,
and a static HTML dashboard. Movement, grasp, and delivery are simulated;
`object.found` evidence is produced by real OpenCV marker detection from a
deterministic image fixture.

## Quick start

Create and activate a virtual environment if needed:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install development requirements:

```bash
python3 -m pip install -r requirements-dev.txt
```

Run the test suite:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

## CI boundary

GitHub Actions validates the stable local simulation, fixture vision, dashboard,
hybrid demo, and adapter simulation chain. CI intentionally does not open
cameras, run the live camera probe with `--enable-live-camera`, run the physical
demo, move the robot, control the arm, or call actuators. Live camera and
physical demo runs remain local operator actions only.

Run the hybrid evidence demo:

```bash
python3 scripts/run_hybrid_demo.py
```

Run the adapter-backed simulation demo:

```bash
python3 scripts/run_adapter_sim_demo.py
```

This exercises the camera, vision, and arm adapter boundaries without opening
real cameras, serial ports, USB devices, or arm runtimes.

## VR gateway simulation

Run the deterministic VR head-control simulation and its focused tests:

```bash
python3 scripts/run_vr_gateway_simulation.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_*.py -v
```

The runner prints newline-delimited JSON and opens no ROS, network, base, arm,
gripper, or real neck device. Its named simulation angles are deterministic
fixtures, not Valera hardware calibration.

### VR Gateway ROS 2 transport slice

A minimal ROS 2 / rosbridge transport adapter for the gateway core lives in
`robot/vr_gateway/wire.py` (transport-neutral JSON codec),
`robot/vr_gateway/adapter.py` (thin fail-closed adapter), and
`robot/vr_gateway_ros/` (ROS 2 node). The ROS layer only moves JSON strings
between ROS topics and the gateway; it owns no safety decisions.

| direction | topic | type |
|-----------|-------|------|
| subscribe | `/valera/vr_gateway/command` | `std_msgs/msg/String` (raw JSON command) |
| publish | `/valera/vr_gateway/event` | `std_msgs/msg/String` (one message per event) |

The node defaults to a 20 ms poll timer and uses the simulation neck
configuration only. It uses `time.monotonic_ns` (not ROS Time) for watchdog
and handshake deadlines so `/clock` pauses or sim time cannot stop safety
evaluation. It never opens neck servos, the tracked base, or the
SO-101 arm. See `docs/vr_gateway_ros2_transport_v0_1.md` for the full topic
contract, JSON examples, monotonic-clock rationale, and limitations.

Run the transport and bridge tests without an installed ROS:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_vr_gateway_wire.py tests/test_vr_gateway_ros_node.py -v
```

Verify the full local hybrid demo chain:

```bash
python3 scripts/smoke_hybrid_demo.py
```

Collect a read-only hardware inventory for bring-up planning:

```bash
python3 scripts/collect_hardware_inventory.py
```

This writes ignored reports under `tmp/hardware-inventory/` and does not open
cameras, serial ports, or robot hardware.

Optional live camera probe, fail-closed unless explicitly enabled:

```bash
python3 scripts/run_live_camera_probe.py
python3 scripts/run_live_camera_probe.py --enable-live-camera
```

The live probe captures one frame only and does not move the robot or control the
arm. It is not part of the stable hybrid smoke path.

Physical demo runner for video preparation, fail-closed unless explicitly
enabled:

```bash
python3 scripts/run_physical_demo.py --enable-live-camera
.venv/bin/python scripts/check_physical_demo_output.py
```

The physical demo uses real live camera vision for object detection, then records
operator-confirmed manipulation and delivery steps. It does not move the robot or
control the arm directly, and it is not part of the stable hybrid smoke path.
See `docs/physical_demo_video.md` for the rehearsal and filming checklist.

Open the generated dashboard:

```bash
open data/runs/hybrid-fixture-task-001/dashboard.html
```

On Linux without `open`, use your browser or file manager to open the same
HTML file.

## Generated outputs

The hybrid demo writes local runtime artifacts under ignored paths:

- `data/runs/{task_id}/replay.json`
- `data/runs/{task_id}/dashboard.html`
- `data/evidence/{task_id}/...`

Generated outputs are ignored by git, along with temporary files under `tmp/`.
They are safe to regenerate locally and should not be committed.

## Project areas

- `docs/` - product, architecture, roadmap, decisions, and demo guides
- `robot/` - robot domain model, event log, simulation, evidence, and vision adapters
- `enterprise/` - enterprise integration schemas and process examples
- `scripts/` - repeatable helper and validation scripts
- `dashboard/` - local static dashboard rendering

## Adapter readiness

The adapter path is ready for real camera and arm implementations to be added
behind explicit safety gates:

- `robot/adapters/base.py`, `arm.py`, `camera.py`, and `vision.py` define
  project-owned contracts and result models.
- `robot/adapters/sim_arm.py`, `sim_camera.py`, and `sim_vision.py` provide
  deterministic simulation implementations.
- `robot/adapter_runtime.py` builds a simulation adapter bundle from explicit
  config and fails closed for hardware mode.
- `robot/adapter_sim_mission.py` proves the orchestration boundary by recording
  adapter results as events.

Real camera or arm adapters should be added as new implementation files, not by
changing the Valera task model. Hardware mode remains disabled until explicit
probe and safety gates exist.
