from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    uav1_mavros = Node(
        package="mavros",
        executable="mavros_node",
        name="mavros",
        namespace="uav1",
        output="screen",
        parameters=[
            {
                "fcu_url": "udp://:14557@",
                "target_system_id": 1,
                "system_id": 255,
                "component_id": 240,
            }
        ],
    )

    uav2_mavros = Node(
        package="mavros",
        executable="mavros_node",
        name="mavros",
        namespace="uav2",
        output="screen",
        parameters=[
            {
                "fcu_url": "udp://:14556@",
                "target_system_id": 2,
                "system_id": 255,
                "component_id": 241,
            }
        ],
    )

    return LaunchDescription([uav1_mavros, uav2_mavros])
