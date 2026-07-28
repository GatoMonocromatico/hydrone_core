#!/usr/bin/env python3
"""Ponte de traducao ROS2 <-> MAVLink (via MAVROS), um no por veiculo.

  Planejador -> /hydrone/waypoint_cmd -> mavros/setpoint_position/global
  MAVROS (mavros/state, mavros/global_position/global) -> /hydrone/mission_state -> Planejador

Nenhuma mensagem MAVLink e tratada aqui; a traducao e responsabilidade do MAVROS.
"""
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
    qos_profile_sensor_data,
)

from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode

from bridge_msgs.msg import MissionState, WaypointCommand

EARTH_RADIUS_M = 6371000.0

# Telemetria de alta taxa: so a amostra mais recente importa, e um assinante
# tardio deve receber o ultimo estado imediatamente.
MISSION_STATE_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# Comando discreto: perder um e pior que a latencia extra de garantir entrega.
WAYPOINT_CMD_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
    durability=QoSDurabilityPolicy.VOLATILE,
)


def haversine_distance_m(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2.0) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


class HybridBridgeNode(Node):

    def __init__(self):
        super().__init__('hybrid_bridge')

        self.declare_parameter('vehicle_id', 'hydrone_vehicle')
        self.declare_parameter('auto_set_guided', True)
        self.declare_parameter('auto_arm', False)
        self.declare_parameter('guided_mode_name', 'GUIDED')
        self.declare_parameter('waypoint_acceptance_radius_m', 2.0)
        self.declare_parameter('state_publish_rate_hz', 5.0)

        self.vehicle_id = self.get_parameter('vehicle_id').value
        self.auto_set_guided = self.get_parameter('auto_set_guided').value
        self.auto_arm = self.get_parameter('auto_arm').value
        self.guided_mode_name = self.get_parameter('guided_mode_name').value
        self.acceptance_radius_m = self.get_parameter(
            'waypoint_acceptance_radius_m').value
        state_rate_hz = self.get_parameter('state_publish_rate_hz').value

        # Lado planejador: topicos globais, roteados por vehicle_id.
        self._cmd_sub = self.create_subscription(
            WaypointCommand, '/hydrone/waypoint_cmd',
            self._on_waypoint_command, WAYPOINT_CMD_QOS)
        self._state_pub = self.create_publisher(
            MissionState, '/hydrone/mission_state', MISSION_STATE_QOS)

        # Lado MAVROS: dentro do namespace do veiculo (ex.: /hydrone_drone/mavros/...).
        self._setpoint_pub = self.create_publisher(
            GeoPoseStamped, 'mavros/setpoint_position/global', 10)
        self._mavros_state_sub = self.create_subscription(
            State, 'mavros/state', self._on_mavros_state,
            qos_profile_sensor_data)
        self._position_sub = self.create_subscription(
            NavSatFix, 'mavros/global_position/global',
            self._on_position, qos_profile_sensor_data)
        self._set_mode_client = self.create_client(
            SetMode, 'mavros/set_mode')
        self._arming_client = self.create_client(
            CommandBool, 'mavros/cmd/arming')

        self._connected = False
        self._armed = False
        self._mode = ''
        self._current_lat = math.nan
        self._current_lon = math.nan
        self._current_alt = math.nan
        self._last_cmd_id = 0
        self._target_lat = math.nan
        self._target_lon = math.nan
        self._target_alt = math.nan

        self._state_timer = self.create_timer(
            1.0 / state_rate_hz, self._publish_mission_state)

        self.get_logger().info(f'Ponte hibrida ativa para "{self.vehicle_id}"')

    # -- MAVROS -> Hydrone --------------------------------------------
    def _on_mavros_state(self, msg: State):
        self._connected = msg.connected
        self._armed = msg.armed
        self._mode = msg.mode

    def _on_position(self, msg: NavSatFix):
        self._current_lat = msg.latitude
        self._current_lon = msg.longitude
        self._current_alt = msg.altitude

    def _publish_mission_state(self):
        msg = MissionState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'wgs84'
        msg.vehicle_id = self.vehicle_id
        msg.connected = self._connected
        msg.armed = self._armed
        msg.mode = self._mode
        msg.latitude = self._current_lat
        msg.longitude = self._current_lon
        msg.altitude = self._current_alt
        msg.last_cmd_id = self._last_cmd_id
        msg.target_latitude = self._target_lat
        msg.target_longitude = self._target_lon
        msg.target_altitude = self._target_alt
        msg.waypoint_reached = self._is_waypoint_reached()
        self._state_pub.publish(msg)

    def _is_waypoint_reached(self):
        if self._last_cmd_id == 0:
            return False
        if math.isnan(self._current_lat) or math.isnan(self._target_lat):
            return False
        distance = haversine_distance_m(
            self._current_lat, self._current_lon,
            self._target_lat, self._target_lon)
        return distance <= self.acceptance_radius_m

    # -- Hydrone -> MAVROS ----------------------------------------------
    def _on_waypoint_command(self, msg: WaypointCommand):
        if msg.vehicle_id and msg.vehicle_id != self.vehicle_id:
            return

        self.get_logger().info(
            f'cmd_id={msg.cmd_id}: novo waypoint '
            f'({msg.latitude:.6f}, {msg.longitude:.6f}, {msg.altitude:.1f} m)')

        self._target_lat = msg.latitude
        self._target_lon = msg.longitude
        self._target_alt = msg.altitude
        self._last_cmd_id = msg.cmd_id

        if self.auto_set_guided and self._mode != self.guided_mode_name:
            self._request_mode(self.guided_mode_name)
        if self.auto_arm and not self._armed:
            self._request_arm(True)

        setpoint = GeoPoseStamped()
        setpoint.header.stamp = self.get_clock().now().to_msg()
        setpoint.header.frame_id = 'wgs84'
        setpoint.pose.position.latitude = msg.latitude
        setpoint.pose.position.longitude = msg.longitude
        setpoint.pose.position.altitude = msg.altitude
        setpoint.pose.orientation.w = 1.0
        self._setpoint_pub.publish(setpoint)

        # Confirmacao imediata, fora do ciclo periodico de telemetria.
        self._publish_mission_state()

    def _request_mode(self, mode_name):
        if not self._set_mode_client.service_is_ready():
            self.get_logger().warn('mavros/set_mode ainda nao disponivel')
            return
        req = SetMode.Request()
        req.custom_mode = mode_name
        self._set_mode_client.call_async(req)

    def _request_arm(self, value):
        if not self._arming_client.service_is_ready():
            self.get_logger().warn('mavros/cmd/arming ainda nao disponivel')
            return
        req = CommandBool.Request()
        req.value = value
        self._arming_client.call_async(req)


def main(args=None):
    rclpy.init(args=args)
    node = HybridBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
