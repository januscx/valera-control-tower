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

Run the hybrid evidence demo:

```bash
python3 scripts/run_hybrid_demo.py
```

Verify the full local hybrid demo chain:

```bash
python3 scripts/smoke_hybrid_demo.py
```

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
```

The physical demo uses real live camera vision for object detection, then records
operator-confirmed manipulation and delivery steps. It does not move the robot or
control the arm directly, and it is not part of the stable hybrid smoke path.

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
