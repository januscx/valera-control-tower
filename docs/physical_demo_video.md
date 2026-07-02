# Physical Demo Video Rehearsal Guide

## A. Goal

Show Valera as a physical robotics PoC:

- real physical cube
- real live camera detection
- evidence capture
- operator-confirmed manipulation/delivery steps
- completed mission dashboard

Live vision is real. Manipulation steps are operator-confirmed. The script does
not move the robot or control the arm directly.

## B. Pre-flight checklist

- Valera is on `main` and the worktree is clean.
- `.venv` is activated.
- Orbbec Astra is connected.
- `janus` has `video` group access.
- `/dev/video0` is the RGB camera.
- `VALERA-CUBE-001` is visible and marker id `7` is flat and readable.
- Dashboard/evidence output directories are ignored by git.
- Do not commit generated runtime files.

## C. Commands

Stable smoke:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest
.venv/bin/python scripts/smoke_hybrid_demo.py
```

Physical demo:

```bash
.venv/bin/python scripts/run_physical_demo.py --enable-live-camera
```

Output check:

```bash
.venv/bin/python scripts/check_physical_demo_output.py
```

Dashboard location:

```text
data/runs/physical-demo-001/dashboard.html
```

Evidence location:

```text
data/evidence/physical-demo-001/
```

## D. What to confirm during the run

- grasp started
- object grasped
- delivery started
- object released
- delivery completed

## E. What the successful dashboard must show

- Final status `completed`
- Event count `13`
- Sequence `7` `object.found`
- Source `valera.live_camera_probe` for `object.found`
- `marker_id` `7`
- raw and annotated evidence refs
- `task.completed` at sequence `13`

## F. Suggested shot list for video

1. Robot, cube, and laptop/dashboard in frame.
2. Close-up of `VALERA-CUBE-001` marker.
3. Run command.
4. Live camera detection evidence / `object.found`.
5. Operator-confirmed grasp/release/delivery steps while robot/arm is visible.
6. Final completed dashboard.
7. Annotated evidence preview.

## G. Troubleshooting

`object.not_found`:

- flatten marker
- add white border
- reduce glare
- center cube
- improve lighting

Camera permission denied:

- check groups
- check `/dev/video*`
- user should be in `video` group

Wrong source label:

- dashboard should show `valera.live_camera_probe`, not `valera.real_vision_fixture`

Dashboard previews missing:

- copy `data/runs` and `data/evidence` together
- preserve relative folder structure

Generated files showing in git status:

- do not commit them
- verify `.gitignore`

## H. Copy artifacts to MacBook

These commands preserve the relative structure used by dashboard evidence links:

```bash
rm -rf "$HOME/Downloads/valera-physical-demo"
mkdir -p "$HOME/Downloads/valera-physical-demo/data/runs"
mkdir -p "$HOME/Downloads/valera-physical-demo/data/evidence"

scp -r valera:~/projects/valera-control-tower/data/runs/physical-demo-001 \
  "$HOME/Downloads/valera-physical-demo/data/runs/"

scp -r valera:~/projects/valera-control-tower/data/evidence/physical-demo-001 \
  "$HOME/Downloads/valera-physical-demo/data/evidence/"

open "$HOME/Downloads/valera-physical-demo/data/runs/physical-demo-001/dashboard.html"
```
