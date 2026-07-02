# Valera Hybrid Evidence Demo

This guide is for running, verifying, and recording the local Hybrid Evidence
Demo. The demo does not use live camera capture, robot movement, arm control,
networking, cloud storage, or a dashboard server.

## Preconditions

- The repository virtual environment is active.
- `requirements-dev.txt` has been installed.
- OpenCV contrib is available, including `cv2.aruco`.

## Run

From the repository root:

```bash
python3 scripts/run_hybrid_demo.py
```

To run the adapter-backed simulation path for camera, vision, and arm adapter
boundaries:

```bash
python3 scripts/run_adapter_sim_demo.py
```

This writes:

- `data/runs/adapter-sim-demo-001/replay.json`
- `data/runs/adapter-sim-demo-001/dashboard.html`

The adapter simulation demo uses only synthetic artifacts such as
`sim://camera/wrist/frame-000001`. It does not use OpenCV, live camera capture,
serial ports, USB devices, LeRobot, or arm motion.

To verify the full local demo chain, including replay, dashboard, evidence
files, and previews:

```bash
python3 scripts/smoke_hybrid_demo.py
```

## Expected output

The command should print:

- `Task id: hybrid-fixture-task-001`
- `Final status: completed`
- `Event count: 14`
- `Replay path: /.../data/runs/hybrid-fixture-task-001/replay.json`
- `Dashboard path: /.../data/runs/hybrid-fixture-task-001/dashboard.html`
- Evidence paths under `data/evidence/hybrid-fixture-task-001/`

For `scripts/run_adapter_sim_demo.py`, the command should print:

- `PASS: Adapter simulation demo`
- `Task id: adapter-sim-demo-001`
- `Final status: completed`
- `Event count: 18`
- Replay and dashboard paths under `data/runs/adapter-sim-demo-001/`

## Open the dashboard

Open the generated static dashboard:

```bash
open data/runs/hybrid-fixture-task-001/dashboard.html
```

On Linux without `open`, open the same file directly in a browser.

For structured image evidence refs, the dashboard shows local evidence links and
inline previews when the referenced files are under `data/evidence/`.

## Optional live camera probe

The live camera probe is an opt-in perception check for a local robot camera. It
captures one frame only, runs the existing `real_vision` marker detector, writes
a replay and dashboard under `data/runs/live-camera-probe-001/`, and then exits.
It does not move the robot, control the arm, or call hardware actuators.

By default it fails closed before opening any camera:

```bash
python3 scripts/run_live_camera_probe.py
```

To explicitly allow one-frame local camera access:

```bash
python3 scripts/run_live_camera_probe.py --enable-live-camera
```

The live camera probe is not part of the stable hybrid smoke path.

## Camera and arm adapter handoff

The current adapter demo establishes the handoff point for real hardware work:

1. Camera implementations should conform to `CameraAdapter`, select cameras by
   `CameraRole`, and return `FrameCaptureResult` with artifact references.
2. Vision implementations should conform to `VisionAdapter` and return
   deterministic project-owned `VisionResult` data for a given artifact.
3. Arm implementations should conform to `ArmAdapter`; initial hardware work
   should remain probe-only and must not enable torque or move the arm.
4. `robot/adapter_runtime.py` is the single place to add explicit non-simulation
   adapter selection after safety gates are designed.

Until those gates exist, hardware mode intentionally fails closed.

## Physical demo runner

For physical demo video preparation, run:

```bash
python3 scripts/run_physical_demo.py --enable-live-camera
.venv/bin/python scripts/check_physical_demo_output.py
```

This runner uses real live camera perception for `object.found`, then asks the
operator to explicitly confirm grasp, release, and delivery steps before those
events are recorded. It does not move the robot, control the arm directly, or
call actuators. It writes a replay and dashboard under
`data/runs/physical-demo-001/` and is not part of the stable hybrid smoke path.
Use `docs/physical_demo_video.md` as the concise rehearsal and filming guide.

## Demo video walkthrough

1. Run `python3 scripts/run_hybrid_demo.py`.
2. Open `data/runs/hybrid-fixture-task-001/dashboard.html`.
3. Show the mission summary.
4. Show the event timeline.
5. Point out the `object.found` event.
6. Show that `object.found` uses `real_vision`.
7. Show `marker_id`, `detection_score`, `corners`, and `bounding_box`.
8. Show the raw and annotated evidence refs.
9. Show the final `task.completed` event.

## Troubleshooting

If `cv2` is missing, reinstall the development requirements:

```bash
python3 -m pip install -r requirements-dev.txt
```

If `cv2.aruco` is missing, confirm that the installed OpenCV package includes
the contrib modules. The fixture detector requires `cv2.aruco`.

If pytest loads unrelated local plugins, run tests with plugin autoloading
disabled:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

If generated files do not appear in `git status`, that is expected. Runtime
artifacts under `data/evidence/`, `data/dashboard/`, `data/runs/`, and `tmp/`
are ignored by git.

If the dashboard is hard to find, use the path printed by
`scripts/run_hybrid_demo.py`. The default hybrid dashboard is:

```text
data/runs/hybrid-fixture-task-001/dashboard.html
```
