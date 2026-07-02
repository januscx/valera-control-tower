# Physical Demo v1 Tracking

## Goal

Prepare and track the next local physical demo milestone for Valera: live camera
marker detection plus operator-confirmed grasp, release, and delivery facts in
the event log. The software still does not move the base, control the arm, or
call actuators.

## Acceptance Criteria

- Local physical run completes with task id `physical-demo-001`.
- `python3 scripts/check_physical_demo_output.py` passes.
- Dashboard opens and shows final status `completed`.
- Replay event count is 13.
- `object.found` source is `valera.live_camera_probe`.
- Detected marker id is 7.
- Raw and annotated PNG evidence files exist.
- Generated runtime files under `data/runs/`, `data/evidence/`, `data/dashboard/`,
  and `tmp/` are not committed.

## Out Of Scope

- No base movement.
- No arm motion.
- No actuator calls.
- No ROS2.
- No cloud, server, database, or dashboard service.
- No SAP, ERP, or other enterprise system integration.
- No frontend rewrite.

## Local Rehearsal Commands

Run only on an operator-controlled local machine where camera access is intended:

```bash
python3 scripts/run_physical_demo.py --enable-live-camera
python3 scripts/check_physical_demo_output.py
```

Optional stable local checks that do not access hardware:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
python3 scripts/smoke_hybrid_demo.py
python3 scripts/run_adapter_sim_demo.py
```

## Evidence And Output Checklist

- `data/runs/physical-demo-001/replay.json`
- `data/runs/physical-demo-001/dashboard.html`
- Raw PNG evidence under `data/evidence/physical-demo-001/`
- Annotated PNG evidence under `data/evidence/physical-demo-001/`
- Dashboard timeline includes `task.completed`
- Dashboard details show `object.found` from `valera.live_camera_probe`
- Replay records operator-confirmed manipulation steps, not software motion

## Follow-Up PR Slices

- PR A: CI stable demo chain.
- PR B: Physical demo rehearsal run notes after real Valera execution.
- PR C: Camera adapter probe contract, still perception-only.
- PR D: SO-ARM probe/readiness adapter, no torque or motion.
- PR E: Tracked base probe/readiness adapter, no movement.
