# valera_vr_gateway

This is an `ament_python` packaging wrapper around the repository's existing
`robot.vr_gateway` and `robot.vr_gateway_ros` modules. The wrapper deliberately
does not copy those modules: setuptools discovers them from the repository root
when the package is built from this checkout.

The gateway-only launch starts the simulation neck node. The rosbridge launch
adds the Jazzy `rosbridge_websocket_launch.xml` interface with loopback-only
defaults and a topic allowlist containing only the VR Gateway command and event
topics. It does not add WebSocket code to the production node.
