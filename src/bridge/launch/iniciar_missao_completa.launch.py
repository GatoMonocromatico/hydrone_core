"""Sobe MAVROS + ponte hibrida (drone + barco) + planejador de missao."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bridge_share = get_package_share_directory('bridge')
    default_mission_file = os.path.join(
        bridge_share, 'config', 'missao_exemplo.yaml')

    drone_fcu_url_arg = DeclareLaunchArgument(
        'drone_fcu_url', default_value='udp://:14550@')
    boat_fcu_url_arg = DeclareLaunchArgument(
        'boat_fcu_url', default_value='udp://:14560@')
    mission_file_arg = DeclareLaunchArgument(
        'mission_file', default_value=default_mission_file)

    ponte_hibrida = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bridge_share, 'launch',
                         'iniciar_ponte_hibrida.launch.py')),
        launch_arguments={
            'drone_fcu_url': LaunchConfiguration('drone_fcu_url'),
            'boat_fcu_url': LaunchConfiguration('boat_fcu_url'),
        }.items(),
    )

    mission_planner = Node(
        package='bridge',
        executable='mission_planner_node.py',
        name='mission_planner',
        output='screen',
        parameters=[{'mission_file': LaunchConfiguration('mission_file')}],
    )

    return LaunchDescription([
        drone_fcu_url_arg,
        boat_fcu_url_arg,
        mission_file_arg,
        ponte_hibrida,
        mission_planner,
    ])
