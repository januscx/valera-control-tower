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

## Expected output

The command should print:

- `Task id: hybrid-fixture-task-001`
- `Final status: completed`
- `Event count: 14`
- `Replay path: /.../data/runs/hybrid-fixture-task-001/replay.json`
- `Dashboard path: /.../data/runs/hybrid-fixture-task-001/dashboard.html`
- Evidence paths under `data/evidence/hybrid-fixture-task-001/`

## Open the dashboard

Open the generated static dashboard:

```bash
open data/runs/hybrid-fixture-task-001/dashboard.html
```

On Linux without `open`, open the same file directly in a browser.

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
