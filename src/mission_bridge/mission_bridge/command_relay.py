#!/usr/bin/env python3
"""Assina comandos em mission/command e repassa ao veiculo (T10.2 - item b)."""
import rclpy
from rclpy.node import Node

from mission_interfaces.msg import MissionCommand


class CommandRelay(Node):
    def __init__(self):
        super().__init__('command_relay')

        self.declare_parameter('vehicle', 'hydrone')
        self.vehicle = self.get_parameter('vehicle').get_parameter_value().string_value

        self.subscription = self.create_subscription(
            MissionCommand, 'mission/command', self.on_command, 10)

        self.get_logger().info(f"relay ativo, ouvindo comandos de '{self.vehicle}'")

    def on_command(self, msg: MissionCommand):
        if self.vehicle and msg.vehicle and msg.vehicle != self.vehicle:
            return  # comando de outro veiculo

        # Latencia: stamp vem do planejador.
        now = self.get_clock().now().to_msg()
        latency_ms = (
            (now.sec - msg.header.stamp.sec) * 1000.0
            + (now.nanosec - msg.header.stamp.nanosec) / 1e6)

        self.get_logger().info(
            f"cmd '{msg.command}' p/ '{msg.vehicle}' wp={msg.waypoint} "
            f"target=({msg.target_position.x:.1f}, {msg.target_position.y:.1f}, "
            f"{msg.target_position.z:.1f})  latencia={latency_ms:.1f} ms")

        self.relay_to_vehicle(msg)

    def relay_to_vehicle(self, msg: MissionCommand):
        # TODO: traduzir comando -> chamadas MAVROS/MAVLink do veiculo.
        pass


def main(args=None):
    rclpy.init(args=args)
    node = CommandRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
