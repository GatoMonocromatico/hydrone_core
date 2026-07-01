#!/usr/bin/env python3
"""Publica o estado da missao em mission/state (T10.2 - item a)."""
import rclpy
from rclpy.node import Node

from mission_interfaces.msg import MissionState


class MissionStatePublisher(Node):
    def __init__(self):
        super().__init__('mission_state_publisher')

        self.declare_parameter('vehicle', 'hydrone')
        self.declare_parameter('publish_rate_hz', 1.0)

        self.vehicle = self.get_parameter('vehicle').get_parameter_value().string_value
        rate = self.get_parameter('publish_rate_hz').get_parameter_value().double_value
        if rate <= 0.0:
            self.get_logger().warn(f'publish_rate_hz={rate} invalido, usando 1.0')
            rate = 1.0

        self.publisher = self.create_publisher(MissionState, 'mission/state', 10)
        self.timer = self.create_timer(1.0 / rate, self.publish_state)

        # Estado provisorio; sera alimentado pelo planejador/telemetria depois.
        self.phase = 'IDLE'
        self.current_waypoint = 0

        self.get_logger().info(f"publisher ativo para '{self.vehicle}' a {rate} Hz")

    def publish_state(self):
        msg = MissionState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.vehicle = self.vehicle
        msg.phase = self.phase
        msg.current_waypoint = self.current_waypoint
        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MissionStatePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
