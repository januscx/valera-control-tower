# VR Gateway ROS 2 Runtime Smoke v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Package the existing simulation-only VR Gateway ROS node as an installable ROS 2 Jazzy `ament_python` package and add repeatable launch/runtime smoke validation without touching hardware.

**Architecture:** Add a top-level `ros2/` package wrapper that installs the existing `robot` modules through setuptools package discovery, with no source duplication. Keep the production node ROS-topic-only and add launch files plus a test-only smoke harness; rosbridge is launched/configured only at the boundary and never embedded in the gateway node. Static pytest tests validate metadata, launch safety, process cleanup, and message scenarios; local ROS 2 smoke validates the installed package, while Pi5 validation is attempted separately.

**Tech Stack:** Python 3, setuptools/ament_python, ROS 2 Jazzy (`rclpy`, `std_msgs`, `ros2launch`), pytest, optional loopback WebSocket client, shell smoke tooling.

## Global Constraints

- Base commit: `c8928c8a1cc93b070a181a51978f6ba229e1bc1e`.
- Branch: `codex/vr-gateway-ros2-runtime-smoke-v0-1`.
- Draft PR only; do not merge.
- Simulation neck only; no base, arm, servos, cameras, serial, GPIO, USB, RC, `/cmd_vel`, or live Pi5 service/workspace changes.
- Preserve gateway safety policy, `ClockType.STEADY_TIME`, and `time.monotonic_ns`.
- Ordinary pytest must import the package without ROS installed.
- Do not claim runtime validation that was not observed.

---

### Task 1: Create isolated branch and inspect runtime interfaces

**Files:** None initially.

- [ ] Verify clean `main` at the requested base and create `codex/vr-gateway-ros2-runtime-smoke-v0-1`.
- [ ] Read the existing node, handlers, gateway, tests, docs, and installed Jazzy rosbridge launch files.
- [ ] Record exact rosbridge launch arguments/parameters and available local WebSocket clients.
- [ ] Confirm no source changes are needed for packaging until tests demonstrate a requirement.

### Task 2: Define failing package metadata tests

**Files:**
- Create: `tests/test_vr_gateway_ros_package.py`

**Interfaces:** Tests inspect `ros2/valera_vr_gateway/package.xml`, `setup.py`, `setup.cfg`, resource marker, and launch files without importing ROS.

- [ ] Test package name/version, `ament_python` build type, runtime dependencies, and absence of hardware/base/arm dependencies.
- [ ] Test setuptools package discovery includes `robot`, `robot.vr_gateway`, and `robot.vr_gateway_ros` from the repository without copying.
- [ ] Test console script exactly equals `valera_vr_gateway_node = robot.vr_gateway_ros.node:main`.
- [ ] Test launch files install and contain gateway-only versus rosbridge-only boundaries.
- [ ] Run the focused tests and observe the expected failure because the package files do not yet exist.

### Task 3: Implement minimal ament_python package

**Files:**
- Create: `ros2/valera_vr_gateway/package.xml`
- Create: `ros2/valera_vr_gateway/setup.py`
- Create: `ros2/valera_vr_gateway/setup.cfg`
- Create: `ros2/valera_vr_gateway/resource/valera_vr_gateway`
- Create: `ros2/valera_vr_gateway/launch/valera_vr_gateway.launch.py`
- Create: `ros2/valera_vr_gateway/launch/valera_vr_gateway_with_rosbridge.launch.py`
- Create: `ros2/valera_vr_gateway/README.md`

**Interfaces:**
- Package metadata declares `rclpy` and `std_msgs` runtime dependencies and `ament_python` build type.
- `setup.py` uses `find_packages(...)` with `package_dir={"": repo_root}` or equivalent explicit repository-root discovery so existing `robot` modules are installed without duplication.
- Console entry point is `valera_vr_gateway_node = robot.vr_gateway_ros.node:main`.
- Gateway-only launch starts only `valera_vr_gateway_node`.
- Rosbridge launch starts the gateway plus the installed `rosbridge_server` launch using the inspected Jazzy interface, loopback defaults, and an explicit allowlist of the two VR Gateway topics.

- [ ] Implement metadata and launch files to satisfy Task 2.
- [ ] Run focused metadata tests and `python3 setup.py --name`/metadata inspection.
- [ ] Build/install locally if ROS tooling is available; confirm `ros2 run valera_vr_gateway valera_vr_gateway_node` resolves.

### Task 4: Define failing smoke scenario and safety tests

**Files:**
- Create: `tests/test_vr_gateway_ros_smoke.py`
- Create: `scripts/smoke_vr_gateway_ros2.py`

**Interfaces:**
- Smoke harness accepts strict timeout options and a mode for gateway-only or rosbridge loopback smoke.
- Harness starts fresh subprocesses for state-isolated scenarios, records output, and always terminates children in a cleanup trap.
- Scenario assertions cover topic advertisement, session/recenter/pose event order and correlation, timeout, watchdog stop, malformed payload rejection, emergency stop, and empty event suppression.
- Test-only WebSocket code uses an available client or exits with an explicit pending result; no production node WebSocket code.

- [ ] Write tests for message sequence expectations and forbidden endpoints/imports.
- [ ] Run them and observe failure because the harness and launch/package interfaces are absent.
- [ ] Implement the harness around ROS CLI/topic APIs or a small test-only rclpy client, with subprocess isolation and cleanup.
- [ ] Add an optional loopback rosbridge WebSocket smoke using an already available client, never a production dependency.
- [ ] Run focused smoke tests locally.

### Task 5: Validate local ROS 2 runtime and packaging safety

**Files:**
- Modify: `tests/test_vr_gateway_ros_package.py` and `tests/test_vr_gateway_ros_smoke.py` only if observed interface details require it.

- [ ] Build in an isolated temporary ROS workspace using `/opt/ros/jazzy/setup.bash` and `colcon build --packages-select valera_vr_gateway`.
- [ ] Run the gateway-only launch smoke and all isolated scenarios.
- [ ] Run gateway-plus-rosbridge launch smoke and the loopback WebSocket smoke if a client is available.
- [ ] Verify process cleanup and inspect topics to prove no `/cmd_vel`, base, arm, camera, or unrelated topic endpoints were exposed.
- [ ] Attempt SSH alias `pi5` using only `/tmp/valera_vr_gateway_smoke_ws`; if unreachable, record validation as pending without changing the live workspace.

### Task 6: Document packaging and validation

**Files:**
- Create: `docs/vr_gateway_ros2_runtime_smoke_v0_1.md`
- Modify: `README.md` only if a concise link is appropriate.

- [ ] Document layout decision, exact build/run/cleanup commands, observed local/Pi5 outputs, topic allowlist, no-hardware proof, WebSocket status, and limitations.
- [ ] Explicitly distinguish local ROS validation from unavailable Pi5 validation.

### Task 7: Full verification and draft PR

**Files:** All changed files above.

- [ ] Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest`.
- [ ] Run `git diff --check origin/main...HEAD` and `git status --short`.
- [ ] Review the diff for source duplication, production WebSocket logic, hardware imports, unsafe topics, secrets, and generated junk.
- [ ] Commit in focused commits, push the branch, and open a draft PR titled `feat: package and smoke-test VR Gateway on ROS 2 Jazzy`.
- [ ] Report branch/commit SHAs, changed files, packaging layout, test results, Pi5 result, ROS topic result, WebSocket result, Actions result, hardware boundary proof, and Critical/Important/Minor findings.

## Self-review

- Packaging, launch interface inspection, smoke scenarios, WebSocket boundary, Pi5 attempt, tests, documentation, and draft PR are each covered.
- No task modifies gateway safety policy or hardware adapters.
- Runtime claims are conditional on observed command output.

