from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('scout_host', default_value='scout',
                              description='Hostname or Tailscale IP of the Scout robot'),
        DeclareLaunchArgument('scout_port', default_value='9090',
                              description='rosbridge WebSocket port on Scout'),
        DeclareLaunchArgument('reconnect_interval', default_value='5.0',
                              description='Seconds between reconnection attempts'),

        Node(
            package='scout_bridge',
            executable='scout_cmd_bridge',
            name='scout_cmd_bridge',
            parameters=[{
                'scout_host': LaunchConfiguration('scout_host'),
                'scout_port': LaunchConfiguration('scout_port'),
                'reconnect_interval': LaunchConfiguration('reconnect_interval'),
            }],
            output='screen',
        ),
    ])
