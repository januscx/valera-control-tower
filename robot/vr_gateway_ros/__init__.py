"""ROS 2 transport slice for the Unity VR Gateway.

This package is an adapter only. It must never host session state, sequence or
timestamp decisions, watchdog policy, E-stop semantics, neck safety limits, or
base/arm control. Those concerns live exclusively in
:mod:`robot.vr_gateway`. The ROS node here only moves raw JSON strings between
ROS topics and the transport-neutral gateway.

ROS 2 imports are isolated to :mod:`robot.vr_gateway_ros.node` so the rest of
the package - and the pure-Python test suite - imports without an installed ROS.
"""