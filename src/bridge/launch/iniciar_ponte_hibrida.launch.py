"""Sobe MAVROS + ponte hibrida para o par drone + barco.

As duas pontes falam os mesmos topicos globais /hydrone/waypoint_cmd e
/hydrone/mission_state; o roteamento por veiculo e feito por vehicle_id.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

DRONE_NAMESPACE = 'hydrone_drone'
BOAT_NAMESPACE = 'hydrone_boat'


def generate_launch_description():
    drone_fcu_url_arg = DeclareLaunchArgument(
        'drone_fcu_url', default_value='udp://:14550@')
    boat_fcu_url_arg = DeclareLaunchArgument(
        'boat_fcu_url', default_value='udp://:14560@')

    drone_mavros = Node(
        package='mavros',
        executable='mavros_node',
        name='mavros',
        namespace=DRONE_NAMESPACE,
        output='screen',
        parameters=[{
            'fcu_url': LaunchConfiguration('drone_fcu_url'),
            'target_system_id': 1,
            'system_id': 255,
            'component_id': 240,
        }],
    )

    boat_mavros = Node(
        package='mavros',
        executable='mavros_node',
        name='mavros',
        namespace=BOAT_NAMESPACE,
        output='screen',
        parameters=[{
            'fcu_url': LaunchConfiguration('boat_fcu_url'),
            'target_system_id': 2,
            'system_id': 255,
            'component_id': 241,
        }],
    )

    drone_bridge = Node(
        package='bridge',
        executable='hybrid_bridge_node.py',
        name='hybrid_bridge',
        namespace=DRONE_NAMESPACE,
        output='screen',
        parameters=[{'vehicle_id': DRONE_NAMESPACE}],
    )

    boat_bridge = Node(
        package='bridge',
        executable='hybrid_bridge_node.py',
        name='hybrid_bridge',
        namespace=BOAT_NAMESPACE,
        output='screen',
        parameters=[{'vehicle_id': BOAT_NAMESPACE}],
    )

    return LaunchDescription([
        drone_fcu_url_arg,
        boat_fcu_url_arg,
        drone_mavros,
        boat_mavros,
        drone_bridge,
        boat_bridge,
    ])
