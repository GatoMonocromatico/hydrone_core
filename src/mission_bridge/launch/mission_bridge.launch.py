"""Sobe os dois nos da missao sob o namespace do veiculo.

    ros2 launch mission_bridge mission_bridge.launch.py vehicle:=hydrone
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    vehicle = LaunchConfiguration('vehicle')

    return LaunchDescription([
        DeclareLaunchArgument(
            'vehicle', default_value='hydrone',
            description='Nome/namespace do veiculo: hydrone ou whiteboat'),
        Node(
            package='mission_bridge',
            executable='mission_state_publisher',
            name='mission_state_publisher',
            namespace=vehicle,
            parameters=[{'vehicle': vehicle}],
            output='screen',
        ),
        Node(
            package='mission_bridge',
            executable='command_relay',
            name='command_relay',
            namespace=vehicle,
            parameters=[{'vehicle': vehicle}],
            output='screen',
        ),
    ])
