# Gazebo Harmonic + Quest 3 simulation design

Date: 2026-07-18

## Purpose and scope

Build a local, simulation-only execution path for Valera that proves the
future operational chain rather than a standalone Gazebo demo:

```text
Quest 3 -> rosbridge -> valera_vr_gateway -> simulation bridges/controllers
        -> Gazebo Harmonic -> simulated sensors -> Control Tower evidence
```

The first release (v1) is a VR-operated pickup-and-delivery demonstration in a
simple test room. The operator drives the simulated tracked base and commands
the simulated SO-101 arm using the existing Quest client. Gazebo supplies the
physics, robot state, and sensor data; the existing Control Tower records the
mission facts.

This is explicitly not a digital twin. It validates command routing, safety
behaviour, Quest UX, basic manipulation, and evidence flow. It makes no claim
of high-fidelity tracked-vehicle dynamics, calibrated arm dynamics, or a
faithful scan of the physical room.

## Decisions

| Area | Decision |
| --- | --- |
| Host stack | Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic. Do not use Gazebo Classic. |
| Control architecture | Keep `valera_vr_gateway` as the only Quest command ingress and safety-policy owner. Gazebo receives only internal ROS 2 commands. |
| Base command adapter | The gateway transport publishes encoded base targets to `/valera/internal/base_target`; `sim_base_bridge` alone derives stamped controller `cmd_vel` from them. |
| Base physics | Four hidden contact wheels: two on each side, equal commanded speed per side. Tracks and visible sprockets are visual-only and have no collision. |
| Arm control | A simulation-only arm velocity bridge maps the existing `JOINT_JOG` velocities to `velocity_controllers/JointGroupVelocityController`; it does not synthesize trajectories. |
| Gazebo actuation | `gz_ros2_control` owns simulated joint interfaces; ROS 2 controllers own motion commands. |
| Sensors | Gazebo sensor systems produce camera/IMU data; `ros_gz_bridge` or `ros_gz_image` moves them to ROS. This is separate from `gz_ros2_control`. |
| Environment | Versioned simple SDF test room. Defer Scaniverse/Blender room assets to a later, separate optimization task. |
| Quest network | A dedicated Quest-facing rosbridge instance exposes only the gateway command/event topics; it must not expose base, arm, sensor, Gazebo, service, or parameter interfaces. |
| Time | Gateway watchdog/session deadlines use steady monotonic wall time. Gazebo, TF, odometry and sensor headers use simulation time from `/clock`. |

## Gateway safety hardening prerequisite

No Gazebo package or controller integration may be implemented until the
existing gateway and ROS transport satisfy these safety contracts. This is
gateway work, not simulation work.

- A watchdog, `session.stop`, or E-stop must publish a zero `base.target` and
  zero/hold `arm.target` for every active or transitioning output, before or
  together with the corresponding `safety.stop` event. The ROS node must route
  those zero targets to the internal base and arm topics; `safety.stop` alone
  is not an actuator stop command.
- DRIVE → ARM must use a correlated base-stop acknowledgement. On entering
  `STOPPING_BASE`, the gateway creates a unique stop generation/token and
  emits a zero base target with that token. A stationary detector may acknowledge
  only the matching token after it observes both the controller's zero command
  and velocity below configured linear/angular thresholds continuously for a
  configured dwell time. `stationary_verified=false` must never complete the
  transition.
- ARM → DRIVE must have an explicit `STOPPING_ARM` deadline path. The gateway
  emits a zero arm velocity target, waits its configured arm brake dwell, and
  then either transitions to DRIVE or enters `SAFE_STOPPED` on timeout/failure.
  It must not remain indefinitely in `STOPPING_ARM`.
- The gateway test suite must cover watchdog, E-stop, `session.stop`, DRIVE →
  ARM and ARM → DRIVE, including zero-output emission and transition completion.

The base feedback path is deliberately local and not Quest-facing:

```text
gateway `BaseTargetEvent` (stop token)
  -> /valera/internal/base_target
  -> sim_base_bridge / diff_drive_controller
  -> /valera/base_controller/odom
  -> sim_stationary_detector
  -> /valera/internal/base_stop_ack (matching token)
  -> gateway ROS node -> gateway.handle_base_stop_ack(...)
```

The detector tracks the latest zero-command token, never derives a token from
an uncorrelated odometry message, and resets its dwell timer if either command
or measured speed becomes non-zero. It also requires consecutive fresh odometry
samples: each sample's monotonic receive age must be below configured
`odom_receive_timeout`, and an expired/missing sample immediately resets dwell
and forbids acknowledgement. A Gazebo pause therefore cannot convert one old
zero-speed message into a verified stop.

`JointGroupVelocityController` has no command timeout. The arm velocity bridge
therefore owns a steady-time lease. It publishes an all-zero array on lease
expiry even if no further gateway event arrives, and emits a monotonic heartbeat
for an external `sim_actuator_supervisor`. If that heartbeat disappears, the
supervisor publishes its own all-zero arm command and requests controller
deactivation; the launch profile also invokes this stop/deactivation path on an
unexpected arm-bridge process exit. The controller must be configured and
tested so deactivation does not retain a non-zero velocity command.

## Package and file boundaries

`trackbot_description` remains the source for robot geometry, link names,
limits, masses, and the existing kinematics values. It must not gain a
hardware-control implementation.

A new ROS 2 simulation package, tentatively `valera_gazebo_sim`, will contain:

- a Gazebo-specific robot overlay / generated simulation description;
- controller configuration;
- SDF models and the simple test-room world;
- launch files and ROS-Gazebo bridges;
- `sim_base_bridge`, `sim_stationary_detector`, and the arm velocity bridge;
- simulation-only tests and test fixtures.

The final implementation may choose Xacro plus Gazebo extensions or a generated
SDF model, but it must have one documented generation command and a validation
test that confirms all controlled joints match `trackbot_description`. It must
not maintain an untracked hand-edited second copy of the robot geometry.

`valera_vr_gateway` remains responsible for its current JSON contract,
mode/watchdog/E-stop state, and its Quest-facing publications:

- `/valera/vr_gateway/command` — `std_msgs/msg/String` command ingress;
- `/valera/vr_gateway/event` — `std_msgs/msg/String`.

The gateway ROS node additionally owns the internal encoded base-target and
base-stop-ack subscriptions/publications defined below. It must not convert a
gateway event directly to `/cmd_vel`; only `sim_base_bridge` may do that.

Neither new bridge is a hardware adapter. Both must be launchable only from the
simulation profile and must never enumerate, open, or command physical devices.

## ROS interfaces and namespaces

The simulation uses the `/valera` namespace. Controller names are fixed to
avoid topic ambiguity.

| Producer | Topic / interface | Type | Consumer | Contract |
| --- | --- | --- | --- | --- |
| Quest via rosbridge | `/valera/vr_gateway/command` | `std_msgs/msg/String` | gateway | Existing raw JSON command contract only. |
| gateway ROS node | `/valera/internal/base_target` | `std_msgs/msg/String` | `sim_base_bridge` | Canonical encoded `BaseTargetEvent`, extended with required `stop_token` for zero transition targets. This is the only carrier of base safety metadata. |
| `sim_base_bridge` | `/valera/base_controller/cmd_vel` | `geometry_msgs/msg/TwistStamped` | `diff_drive_controller` | Derive bounded controller velocity from the internal base target; validate finite values, stamp with ROS simulation time, and preserve zero commands. |
| gateway | `/valera/arm/command` | `std_msgs/msg/String` | sim arm velocity bridge | Existing raw JSON `arm.target` event. |
| sim arm velocity bridge | `/valera/arm_velocity_controller/commands` | `std_msgs/msg/Float64MultiArray` | `velocity_controllers/JointGroupVelocityController` | Ordered, finite, scaled joint velocities; all zeros on deadman release, watchdog, E-stop, or session stop. |
| controller manager | `/joint_states` | `sensor_msgs/msg/JointState` | `robot_state_publisher`, RViz, Control Tower adapters | Simulated state only. |
| base controller | `/valera/base_controller/odom`, `/tf` | `nav_msgs/msg/Odometry`, TF | diagnostics / later Nav2 | Odometry is an estimate, not ground truth. |
| `sim_stationary_detector` | `/valera/internal/base_stop_ack` | `std_msgs/msg/String` | gateway ROS node | Canonical encoded `BaseStopAckEvent`, extended with required `stop_token`; the node rejects unmatched, unverified, stale, or malformed acknowledgements before calling the gateway. Never exposed through rosbridge. |
| Gazebo sensor bridge | `/valera/sim/camera/*`, `/valera/sim/imu` | ROS sensor messages | simulation vision/evidence adapter | Published with simulation-time headers. |
| gateway | `/valera/vr_gateway/event` | `std_msgs/msg/String` | Quest via rosbridge | Existing event contract only. |
| arm velocity bridge | `/valera/internal/arm_bridge_heartbeat` | `std_msgs/msg/UInt64` | `sim_actuator_supervisor` | Monotonic sequence/heartbeat; loss triggers zero command and controller deactivation. Never exposed through rosbridge. |

The `diff_drive_controller` command topic is deliberately stamped: Jazzy
requires `geometry_msgs/msg/TwistStamped` on `~/cmd_vel`. Its built-in timeout
and task-space velocity/acceleration/jerk limits are configured as a second
motion-safety layer, not as a replacement for gateway watchdog logic.

## Robot and physics model

### Mobile base

The first model is a skid-steer approximation:

- `left_front_idler_joint` and `left_rear_drive_joint` form the left wheel
  group; `right_front_idler_joint` and `right_rear_drive_joint` form the right
  group. Each group receives the same controller velocity command.
- This is a **simulation-only override**: the description package documents
  both front joints as passive idlers for the physical approximation. They are
  velocity-commanded only to make the four hidden contacts act as one stable
  skid-steer model; this does not claim a mechanical drive path in Valera.
- The four existing broad cylindrical contacts are retained or replaced with
  equivalent hidden wheel contacts. Visual tread meshes, track links, and
  decorative sprockets are collision-free.
- Initial kinematic values remain wheel radius `0.115 m` and left/right
  separation `0.3776 m`; controller multipliers and odometry covariance are
  explicit tunable simulation parameters.
- The controller has finite velocity, acceleration, jerk, and command-timeout
  limits. Values are conservative and must be recorded with the launch profile.

This intentionally trades traction fidelity for stable, understandable control.
Velocity interfaces can slip and produce odometry error; calibration settings
must therefore be presented as demo tuning, not measured vehicle properties.

### Arm and gripper

The arm controller allow-list and fixed command order is `shoulder_pan`,
`shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper`.
`velocity_controllers/JointGroupVelocityController` accepts an ordered
`Float64MultiArray` on `~/commands`, so the bridge maps the gateway's
normalized `JOINT_JOG` values `[-1, 1]` to five separately configurable
revolute-joint limits in rad/s and a separately configurable gripper limit in
m/s. The command envelope fields `kind`, `deadman`, and `joint_velocity` are
mandatory. Individual allow-listed joint members inside `joint_velocity` are
optional and are explicitly zero when omitted. The bridge rejects unknown
joints and non-finite values. A missing or stale `/joint_states` sample, judged
by its monotonic receive timestamp against configured
`joint_state_receive_timeout`, blocks any non-zero output; it never blocks
publication of the all-zero stop array.

Deadman release, gateway watchdog, E-stop, and `session.stop` publish an
all-zero array in the same fixed order. Joint positions are consumed only to
prevent motion farther beyond a URDF limit; they are not integrated into a
trajectory. `left_clamp` remains a URDF mimic joint and has state but no
independent command interface. The bridge renews its steady-time command lease
only after producing a valid output; expiry sends zero without waiting for ROS
or simulation time. This v1 controller is not a substitute for a future
trajectory/planning interface.

### Sensor assumptions

The existing `imu_link` is used for a simulated IMU. A simulation-only camera
frame and mount pose are required for v1; their values are explicitly labelled
as uncalibrated placeholders. The first visual task uses a clearly detectable
test object and records simulated camera frames as evidence. It does not assert
that this camera corresponds to the physical Orbbec or any installed camera.

## Test room and manipulation scenario

The world contains only deterministic, repository-owned assets:

- a plane, enclosing walls and lighting;
- a work table / placement surface;
- a pickup object with a simple collision shape and distinct visual marker;
- named pickup and delivery zones;
- a fixed robot spawn pose and a repeatable object pose.

The acceptance mission is: start a Quest session, drive from spawn to pickup,
observe the object through the simulated camera, position the arm and close the
gripper, drive to delivery, release, and record mission events plus evidence.
Object attachment may be modelled initially using an explicitly documented
simulation grasp constraint; it must not be represented as validated physical
grasping.

`Charlotte.blend` and `charlotte2.fbx` are deferred. A future import task will
open the Blender source, establish metre scale and Z-up orientation, create a
decimated visual mesh, create separate low-complexity collision geometry, and
profile simulation performance before it replaces the test room.

The SO-101 mount has a separate fidelity gate: the current URDF defines
`so101_mount_joint` as `(0.120, -0.075, 0.065)` m. That value is provisional
until it is checked against the original CAD or a documented direct measurement.
No launch/configuration may silently substitute the old README value
`(0.165, -0.090, 0.065)` m.

## Clock semantics and safety

Two clocks are mandatory and must never be substituted for one another.

| Concern | Clock | Rule |
| --- | --- | --- |
| Gateway session timeout, command freshness and watchdog | `time.monotonic_ns()` / ROS steady clock | Continues while Gazebo is paused. |
| Gazebo physics, TF, odometry and sensor message headers | Gazebo `/clock` / `use_sim_time` | Stops when simulation pauses. |
| `sim_base_bridge` header stamp | ROS clock | Uses simulation time when `use_sim_time=true`; a zero/stale/unavailable stamp is handled explicitly. |

The safety invariant is: a pause must never preserve a live motion command.
If the gateway watchdog expires while Gazebo is paused, gateway output becomes
zero/hold in real time. When Gazebo resumes, no command issued before the pause
may resume motion without fresh valid operator input.

## Launch profiles and isolation

All profiles source ROS 2 Jazzy and set an explicit `ROS_DOMAIN_ID` supplied by
launch arguments. The default development profile uses a non-default documented
domain; CI selects its own value.

| Profile | Starts | Network exposure | Intended use |
| --- | --- | --- | --- |
| `sim_local` | Gazebo GUI/server, robot, controllers, sensor bridges, gateway, RViz optional | None; rosbridge absent | Development and repeatable desktop tests. |
| `sim_quest` | `sim_local` plus Quest-facing rosbridge | One LAN listener restricted to Quest IP by firewall | Operator-run Quest 3 demo. |
| `sim_headless` | Gazebo server and required nodes, no GUI or Quest | None | CI and deterministic launch/integration tests. |

The Quest-facing rosbridge must use a dedicated launch configuration that allows
only:

- publish: `/valera/vr_gateway/command`;
- subscribe: `/valera/vr_gateway/event`;
- services: none;
- parameters: none;
- no `rosapi` process.

The configured Jazzy rosbridge version must be checked during implementation for
its directional glob parameter names (`topics_pub_glob` and
`topics_sub_glob`). A launch test must fail if a broad topic glob, a service/
parameter glob, or `rosapi` is present. The host firewall is the second layer:
bind only the selected LAN interface and permit the configured static DHCP Quest
address and port, denying all other sources. rosbridge has no maintained ROS 2
authentication mechanism, so an untrusted LAN is out of scope.

## Installation target

The implementation guide will install binary packages, not compile Gazebo from
source, unless a compatibility check identifies a defect. The expected set is:

- Gazebo Harmonic (`gz-harmonic`) from the official OSRF repository;
- ROS-Gazebo integration (`ros-jazzy-ros-gz-sim`, `ros-jazzy-ros-gz-bridge`,
  image bridge as needed);
- `ros-jazzy-gz-ros2-control` and standard ROS 2 controller packages;
- `robot_state_publisher`, `xacro`, RViz, colcon and rosdep development tools;
- `ros-jazzy-rosbridge-server` for the Quest-specific profile.

The installation verification includes `gz sim --versions`, a stock Harmonic
world, ROS package discovery, an NVIDIA/OpenGL GUI run, and a headless world
run. CUDA availability alone is not accepted as evidence that Gazebo rendering
works.

## Acceptance tests

### Static and unit tests

- Description validation confirms the controlled joint allow-lists, mimic
  relationship, and wheel group names against `trackbot_description`.
- Base bridge tests cover malformed/non-finite input, zero command propagation,
  stamped output, stop-token preservation, and no command after a rejected
  message.
- Arm velocity bridge tests cover JSON validation, fixed joint ordering,
  revolute/prismatic scaling, all-zero stop commands, position-limit guards,
  stale joint-state rejection of non-zero outputs, steady-time lease expiry,
  mimic exclusion, and no hardware imports or device access.
- Gateway safety-hardening tests cover zero outputs for watchdog, E-stop and
  `session.stop`; correlated dwell-qualified base acknowledgement; rejection of
  `stationary_verified=false`, missing/old odometry, and unmatched stop tokens;
  deterministic completion/failure of both mode-switch directions; and arm
  controller zero/deactivation when either the gateway or arm bridge dies.
- Launch configuration tests assert profile membership, topic names, namespace,
  `use_sim_time`, controller limits, and rosbridge allow-lists.

### Integration tests

- Headless Gazebo spawns Valera, controllers activate, and the robot remains
  stationary until a valid command is received.
- A bounded gateway command yields movement, odometry and joint-state updates;
  a zero command stops the base.
- A valid arm jog reaches the named simulated joints at configured velocities;
  deadman release, watchdog, E-stop and `session.stop` produce all-zero arm
  controller output; no independent `left_clamp` command exists.
- Killing the gateway renews neither base nor arm leases; the arm bridge emits
  zero on lease expiry. Killing the arm bridge causes the external supervisor
  to emit zero and deactivate the arm velocity controller.
- Camera and IMU messages arrive through the sensor bridge with simulation-time
  headers; camera data can produce a Control Tower simulation evidence event.
- The full local scenario records a deterministic mission result without Quest,
  GPU GUI, network access, or physical hardware.

### Mandatory pause/watchdog test

1. Start a valid base command and verify movement.
2. Pause Gazebo while the gateway process continues running.
3. Wait past the real-time gateway watchdog deadline.
4. Verify the gateway emits its stop behaviour and the base bridge holds/zeros
   command state while simulation time is frozen.
5. Resume Gazebo and verify the robot does not move again.
6. Verify movement requires a fresh valid Quest command.

### Quest acceptance run

With a Quest 3 on its static DHCP reservation, start `sim_quest`, establish the
WebSocket session, and verify the headset can publish the one gateway command
topic and receive the one event topic. Attempted WebSocket publication to
`/cmd_vel`, arm, Gazebo, services, and parameters must fail. Complete the test
room mission and archive only simulation logs/evidence.

## Non-goals and follow-up work

- Nav2, mapping and autonomous navigation;
- real base, arm, camera, serial, USB, GPIO or actuator control;
- detailed track contact, terrain interaction or calibrated odometry;
- physical-camera calibration;
- Scaniverse room import;
- exposing ROS graph services or parameters to Quest;
- cloud dependencies.

After v1, separate designs may cover Nav2 and LiDAR, calibration against the
physical platform, high-fidelity track dynamics, and the optimized room scan.

## References

- Gazebo Harmonic binary installation: <https://gazebosim.org/docs/harmonic/install_ubuntu/>
- `gz_ros2_control` for Jazzy: <https://control.ros.org/jazzy/doc/gz_ros2_control/doc/index.html>
- Jazzy `diff_drive_controller` interfaces and limits: <https://control.ros.org/jazzy/doc/ros2_controllers/diff_drive_controller/doc/userdoc.html>
- Jazzy joint-group velocity controller: <https://control.ros.org/jazzy/doc/ros2_controllers/velocity_controllers/doc/userdoc.html>
- Jazzy migration: stamped `cmd_vel`: <https://control.ros.org/jazzy/doc/ros2_controllers/doc/migration.html>
- ROS-Gazebo sensor bridge examples: <https://docs.ros.org/en/jazzy/p/ros_gz_sim_demos/index.html>
- Gazebo mesh optimization guidance: <https://gazebosim.org/api/sim/8/blender_distort_meshes.html>
