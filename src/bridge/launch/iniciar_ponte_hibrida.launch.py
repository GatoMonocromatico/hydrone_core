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
        # NB: no name='mavros' here. mavros_node is a two-node container
        # (router + UAS); a blanket __node:=mavros remap collapses both to the
        # same name and aborts with "create_service ... existing ... pullRequest".
        # Namespace is nested as <vehicle>/mavros so mavros topics land at
        # /hydrone_drone/mavros/* -- exactly what the bridge subscribes to
        # (bridge is in /hydrone_drone and asks for the relative 'mavros/...').
        namespace=f'{DRONE_NAMESPACE}/mavros',
        output='screen',
        parameters=[{
            'fcu_url': LaunchConfiguration('drone_fcu_url'),
            'target_system_id': 1,
            'system_id': 255,
            'component_id': 240,
            # The param plugin busy-loops fetching ~1379 params from ArduPilot
            # 4.8-dev, pegging a CPU core and starving DDS. The bridge needs
            # none of these list-fetching plugins, so deny them.
            'plugin_denylist': ['param', 'waypoint', 'geofence', 'rallypoint'],
        }],
    )

    boat_mavros = Node(
        package='mavros',
        executable='mavros_node',
        # See note on the drone node above: no name='mavros' remap.
        namespace=f'{BOAT_NAMESPACE}/mavros',
        output='screen',
        parameters=[{
            'fcu_url': LaunchConfiguration('boat_fcu_url'),
            'target_system_id': 2,
            'system_id': 255,
            'component_id': 241,
            'plugin_denylist': ['param', 'waypoint', 'geofence', 'rallypoint'],
        }],
    )

    drone_bridge = Node(
        package='bridge',
        executable='hybrid_bridge_node.py',
        name='hybrid_bridge',
        namespace=DRONE_NAMESPACE,
        output='screen',
        parameters=[{
            'vehicle_id': DRONE_NAMESPACE,
            # 2.0 m is tight for SITL GPS + vehicle overshoot; 5.0 m makes
            # waypoint_reached fire reliably without being loose enough to
            # trigger before the vehicle actually travels there.
            'waypoint_acceptance_radius_m': 5.0,
        }],
    )

    boat_bridge = Node(
        package='bridge',
        executable='hybrid_bridge_node.py',
        name='hybrid_bridge',
        namespace=BOAT_NAMESPACE,
        output='screen',
        parameters=[{
            'vehicle_id': BOAT_NAMESPACE,
            'waypoint_acceptance_radius_m': 5.0,
        }],
    )

    return LaunchDescription([
        drone_fcu_url_arg,
        boat_fcu_url_arg,
        drone_mavros,
        boat_mavros,
        drone_bridge,
        boat_bridge,
    ])
