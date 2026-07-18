# Valera TrackBot Wiper - URDF for Isaac Sim

This package describes the tracked Valera/Indystry robot built with two
windshield-wiper motors. The visual geometry was reconstructed from
`trackbot wiper v25.step` (Fusion revision 26, 2025-06-29), not from a generic
tracked chassis.

## Main file

`urdf/trackbot_wiper_v2.urdf`

## V2 with SO-101 arm

`urdf/trackbot_wiper_v2.urdf` keeps the original mobile base unchanged and
adds the SO-101 follower arm from the official TheRobotStudio simulation
model. The arm is fixed to the chassis top at `(0.165, -0.090, 0.065)` m in
`base_link`: 165 mm forward, 90 mm to the right, and 65 mm up. Its zero-yaw
direction is the robot's `+X` (forward).

The mounting offsets are reconstructed from the supplied tape-measure photos;
they should be treated as approximately +/- 5 mm until checked directly on
the hardware. The arm uses the official `new_calib` joint convention, where
the middle of each joint range is virtual zero. Its six actuated joints retain
their upstream names: `shoulder_pan`, `shoulder_lift`, `elbow_flex`,
`wrist_flex`, `wrist_roll`, and `gripper`.

The original angular jaw has been replaced by the Robonine parallel gripper.
`gripper` is now a 37 mm prismatic primary jaw and `left_clamp` mirrors it with
multiplier `-1`; the two simulated jaw travels total 75 mm. The physical design
is specified for an 84 mm full stroke, so update the limits only after checking
the assembled hardware. `gripper_frame_link` is the tool-centre point between
the jaw tips and remains available for IK and grasp planning.

The SO-101 URDF and meshes come from
<https://github.com/TheRobotStudio/SO-ARM100> commit
`fda892cba81032c46c40976a48c9ceadbf40a9ca` and are distributed under
Apache-2.0. A copy of that license is installed from
`third_party/SO-ARM100/LICENSE`.

The parallel-gripper meshes and kinematics come from
<https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper> commit
`3e6befa7c82a720df1f48587b38fe562fc67f2cc` and are distributed under
GPL-3.0. Its license is installed from
`third_party/SO-ARM100-101-Parallel-Gripper/LICENSE`.

Mesh references use `package://trackbot_description/...` URIs, so ROS 2 tools
resolve them from the installed package without repository-specific paths.

## Isaac Sim import

In Isaac Sim:

1. Open **File > Import** and select `urdf/trackbot_wiper_v2.urdf`.
2. Set **Robot Type** to `Mobile Manipulators` and **Base Type** to `Mobile`.
3. Enable **Merge Mesh** and leave **Merge Fixed Joints** disabled for the
   initial import.
4. Leave **Collision From Visuals** disabled. The URDF already contains the
   base primitives plus SO-101 and parallel-gripper collision meshes.
5. Enable **Allow Self-Collision** so non-adjacent arm links can collide with
   the chassis, running gear, and one another.
6. Import the robot, then configure velocity drives for:
   `left_rear_drive_joint` and `right_rear_drive_joint`.
7. Configure position drives for `shoulder_pan`, `shoulder_lift`,
   `elbow_flex`, `wrist_flex`, `wrist_roll`, and `gripper`. Conservative
   starting gains and force limits are in `config/isaac_sim_drives.yaml`.
   Apply and tune them on the imported USD; the plain URDF does not author
   per-joint Isaac/PhysX drive gains.
8. Keep `left_front_idler_joint` and `right_front_idler_joint` passive, and do
   not command `left_clamp` independently because it mimics `gripper`. Keep
   mimic-joint conversion enabled in the importer and remove any independent
   drive authored on `left_clamp`.
9. Inspect collider contacts before running. If the chassis box conflicts with
   a wheel cylinder, filter only these four pairs after import: `base_link`
   with each of `left_front_idler_link`, `right_front_idler_link`,
   `left_rear_drive_link`, and `right_rear_drive_link`. Do not disable
   self-collision globally. Apply any required pair filters before pressing
   **Play**.

For command-line conversion with the importer shipped in current Isaac Sim:

```bash
./python.sh standalone_examples/api/isaacsim.asset.importer.urdf/urdf_import.py \
  --urdf /absolute/path/to/trackbot_description/urdf/trackbot_wiper_v2.urdf \
  --usd-path /absolute/path/to/output \
  --robot-type "Mobile Manipulators" \
  --merge-mesh \
  --allow-self-collision \
  --no-fix-base
```

The command-line importer exposes global joint target/gain overrides, but this
robot needs mixed drive modes. Configure the two driven wheels as velocity
targets and the six manipulator joints as position targets on the imported USD
rather than applying one global `--joint-target-type`.

Do not enable **Merge Fixed Joints** or add `--merge-fixed-joints` for the
initial Isaac Sim 6 import. After importing, inspect the Stage tree and verify
that `imu_link` and `gps_link` exist as named `Xform` prims with these poses
relative to `base_link`:

| Prim | Translation | Rotation |
|---|---|---|
| `imu_link` | `(0, 0, 0.075)` m | `(0, 0, 0)` |
| `gps_link` | `(0.0001, 0.0250, 0.1910)` m | `(0, 0, 0)` |

Fixed-joint merging may be enabled later only after confirming that the
resulting USD preserves the sensor-frame names and transforms required by the
simulation. The URDF intentionally does not use the legacy `dont_collapse`
extension.

The exact importer switches can change between Isaac Sim releases. NVIDIA's
current references are:

- <https://docs.isaacsim.omniverse.nvidia.com/latest/importer_exporter/import_urdf.html>
- <https://docs.isaacsim.omniverse.nvidia.com/latest/importer_exporter/ext_isaacsim_asset_importer_urdf.html>

The old ROS 1 `SimpleTransmission` blocks were removed from v2. They do not
configure Isaac drives and are not a substitute for ROS 2 control. A Gazebo
Harmonic or real-hardware ROS 2 deployment should add a backend-specific
`ros2_control` block, hardware plugin, controller YAML, and launch file rather
than embedding a misleading generic transmission here.

## Differential-drive parameters

| Parameter | Value |
|---|---:|
| Effective wheel radius | 0.115 m |
| Left/right wheel separation | 0.3776 m |
| Front/rear axle separation | 0.3700 m |
| Maximum joint speed | 2.5 rad/s |
| Nominal maximum linear speed | 0.2875 m/s |

Use the rear drive joints with an Isaac differential controller. Both joint
axes are authored so a positive velocity moves the robot in `base_link` +X.
The same values are available in `config/kinematics.yaml`.

## Coordinate frames

- `base_link`: centre of the 500 x 318 x 130 mm chassis, +X forward, +Y left,
  +Z up.
- `imu_link`: nominal IMU mounting frame, 75 mm above the chassis centre.
- `gps_link`: top of the CAD RTK/GPS holder.
- `gripper_frame_link`: tool-centre point between the parallel jaw tips.

The base-only CAD-derived visual envelope is approximately 599 x 548 x 298 mm
including the tread shoes and mast. The contact cylinders extend 8 mm below
the tread mesh, making the base physics envelope about 306 mm high. With the
arm in its nominal zero pose and the parallel gripper closed, the v2 visual
AABB is approximately 891 x 548 x 492 mm. This is not a swept volume; use the
actual link collision meshes for motion planning.

## Physics model and assumptions

URDF cannot model a deforming chain of 70 articulated tread shoes efficiently.
The tread loops therefore remain fixed visual meshes, while four broad
cylinders provide contact. The rear pair is driven and the front pair is
passive. This is a deliberate skid-steer approximation that preserves the CAD
appearance and remains stable in rigid-body simulation.

The CAD does not contain trustworthy material assignments, batteries,
electronics, or measured assembly mass. The base mass remains an engineering
estimate of 12.4 kg. The SO-101 without its gripper is 0.533006 kg in this
URDF, and the parallel gripper is assigned its published 0.170 kg assembly
mass, giving 0.703006 kg for the arm and 13.103006 kg total. Replace these
values after weighing the finished robot and measuring its centre of mass.

For higher-fidelity tracked-vehicle dynamics, replace the cylindrical contact
model after URDF import with Isaac/PhysX surface-velocity or custom track
contact logic. Keep the URDF joints and visual meshes as the robot-description
source of truth.

## Source evidence used

- STEP/Fusion assembly and its 121 exported solids.
- The supplied side-plate drawing (500 mm long, 130 mm high, 370 mm axle
  spacing).
- The supplied STL/3MF parts and CAD renders.
- Robonine's SO-ARM100/101 Parallel Gripper simulation meshes and Xacro.
- Nikodem Bartnik's build video, *3D Printed Robot With Windshield Wiper
  Motors - Part 2*: <https://youtu.be/OgC_Jm3uUtc>.

The video confirms the M10 chassis rods, M5 motor mounting, front screw
tensioners, rear wiper-motor drive, and the later modular M8 clamped drive hub.
