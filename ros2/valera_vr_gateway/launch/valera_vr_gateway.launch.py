from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            Node(
                package="valera_vr_gateway",
                executable="valera_vr_gateway_node",
                name="valera_vr_gateway",
                output="screen",
                parameters=[{"command_topic": "/valera/vr_gateway/command"},
                            {"event_topic": "/valera/vr_gateway/event"}],
            )
        ]
    )
