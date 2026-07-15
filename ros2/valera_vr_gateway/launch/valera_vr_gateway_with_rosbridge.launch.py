from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


TOPICS_GLOB = "[/valera/vr_gateway/command,/valera/vr_gateway/event]"
EMPTY_GLOB = "[]"


def generate_launch_description() -> LaunchDescription:
    address = LaunchConfiguration("rosbridge_address")
    port = LaunchConfiguration("rosbridge_port")
    rosbridge_launch = PathJoinSubstitution(
        [FindPackageShare("rosbridge_server"), "launch", "rosbridge_websocket_launch.xml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("rosbridge_address", default_value="127.0.0.1"),
            DeclareLaunchArgument("rosbridge_port", default_value="9090"),
            Node(
                package="valera_vr_gateway",
                executable="valera_vr_gateway_node",
                name="valera_vr_gateway",
                output="screen",
                parameters=[{"command_topic": "/valera/vr_gateway/command"},
                            {"event_topic": "/valera/vr_gateway/event"}],
            ),
            IncludeLaunchDescription(
                AnyLaunchDescriptionSource(rosbridge_launch),
                launch_arguments={
                    "address": address,
                    "port": port,
                    "topics_glob": TOPICS_GLOB,
                    "services_glob": EMPTY_GLOB,
                    "params_glob": EMPTY_GLOB,
                }.items(),
            ),
        ]
    )
