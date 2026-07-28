#!/usr/bin/env python3
"""Planejador de missao: sequencia waypoints por veiculo falando so o
protocolo Hydrone (WaypointCommand / MissionState) — nunca MAVLink/MAVROS.

Le uma lista ordenada de waypoints por veiculo de um YAML e avanca
automaticamente usando last_cmd_id (confirmacao) e waypoint_reached
(chegada), respeitando hold_time_s. Cada veiculo tem sua propria maquina
de estados, avancando em paralelo com os demais.

Nao validado contra SITL/MAVROS real (ambiente sem ROS2/rede). Sintaxe
checada com py_compile; a maquina de estados foi testada com rclpy
mockado (caminho feliz, hold_time_s, retry/timeout, multiplos veiculos,
carga do YAML) — todos os testes passaram, mas isso nao substitui um
teste real contra SITL.

    ros2 run bridge mission_planner_node.py --ros-args \\
        -p mission_file:=$(ros2 pkg prefix bridge)/share/bridge/config/missao_exemplo.yaml
"""
import time
from dataclasses import dataclass
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)

try:
    import yaml
except ImportError:
    yaml = None

from bridge_msgs.msg import MissionState, WaypointCommand

# Devem espelhar as filas de hybrid_bridge_node.py.
WAYPOINT_CMD_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
    durability=QoSDurabilityPolicy.VOLATILE,
)
MISSION_STATE_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

PENDING = 'PENDING'
WAITING_CONFIRM = 'WAITING_CONFIRM'
WAITING_REACHED = 'WAITING_REACHED'
HOLDING = 'HOLDING'
DONE = 'DONE'
FAILED = 'FAILED'


@dataclass
class VehicleMission:
    vehicle_id: str
    waypoints: list
    idx: int = 0
    state: str = PENDING
    cmd_id: int = 0
    sent_at: float = 0.0
    retries: int = 0
    hold_until: float = 0.0
    reached_warned: bool = False
    final_logged: bool = False


def _load_mission_file(path_str):
    if yaml is None:
        raise RuntimeError('pip install pyyaml')
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f'Arquivo de missao nao encontrado: {path}')
    with path.open('r') as f:
        data = yaml.safe_load(f) or {}
    vehicles_raw = data.get('vehicles') or {}
    if not vehicles_raw:
        raise ValueError(f'{path}: sem chave "vehicles"')

    missions = {}
    for vehicle_id, vdata in vehicles_raw.items():
        waypoints = (vdata or {}).get('waypoints') or []
        parsed = []
        for i, wp in enumerate(waypoints):
            try:
                parsed.append({
                    'latitude': float(wp['latitude']),
                    'longitude': float(wp['longitude']),
                    'altitude': float(wp['altitude']),
                    'hold_time_s': float(wp.get('hold_time_s', 0.0)),
                })
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f'{path}: waypoint {i} de "{vehicle_id}" invalido '
                    f'({exc})') from exc
        missions[vehicle_id] = VehicleMission(
            vehicle_id=vehicle_id, waypoints=parsed)
    return missions


class MissionPlannerNode(Node):

    def __init__(self):
        super().__init__('mission_planner')

        self.declare_parameter('mission_file', '')
        self.declare_parameter('cmd_confirm_timeout_s', 3.0)
        self.declare_parameter('max_cmd_retries', 5)
        self.declare_parameter('waypoint_reached_warn_after_s', 60.0)
        self.declare_parameter('tick_rate_hz', 2.0)

        mission_file = self.get_parameter('mission_file').value
        self.cmd_confirm_timeout_s = self.get_parameter(
            'cmd_confirm_timeout_s').value
        self.max_cmd_retries = self.get_parameter('max_cmd_retries').value
        self.waypoint_warn_after_s = self.get_parameter(
            'waypoint_reached_warn_after_s').value
        tick_rate_hz = self.get_parameter('tick_rate_hz').value

        if not mission_file:
            raise RuntimeError(
                'defina o parametro "mission_file" (ver '
                'config/missao_exemplo.yaml)')

        self._missions = _load_mission_file(mission_file)
        self._next_cmd_id = 1

        for vm in self._missions.values():
            if not vm.waypoints:
                vm.state = DONE
                vm.final_logged = True
                self.get_logger().warn(
                    f'"{vm.vehicle_id}": sem waypoints, nada a fazer')

        self._pub = self.create_publisher(
            WaypointCommand, '/hydrone/waypoint_cmd', WAYPOINT_CMD_QOS)
        self._sub = self.create_subscription(
            MissionState, '/hydrone/mission_state', self._on_mission_state,
            MISSION_STATE_QOS)
        self._timer = self.create_timer(1.0 / tick_rate_hz, self._tick)

        total_wps = sum(len(vm.waypoints) for vm in self._missions.values())
        self.get_logger().info(
            f'Planejador ativo: {len(self._missions)} veiculo(s), '
            f'{total_wps} waypoint(s)')

    def _on_mission_state(self, msg: MissionState):
        vm = self._missions.get(msg.vehicle_id)
        if vm is None or vm.state in (DONE, FAILED):
            return

        if vm.state == WAITING_CONFIRM and msg.last_cmd_id == vm.cmd_id:
            vm.state = WAITING_REACHED
            vm.reached_warned = False
            self.get_logger().info(
                f'"{vm.vehicle_id}" cmd_id={vm.cmd_id}: confirmado, '
                f'aguardando waypoint {vm.idx + 1}/{len(vm.waypoints)}')

        if (vm.state == WAITING_REACHED
                and msg.last_cmd_id == vm.cmd_id
                and msg.waypoint_reached):
            self._advance_or_hold(vm)

    def _advance_or_hold(self, vm: VehicleMission):
        hold_time_s = vm.waypoints[vm.idx]['hold_time_s']
        if hold_time_s > 0:
            vm.state = HOLDING
            vm.hold_until = time.monotonic() + hold_time_s
            self.get_logger().info(
                f'"{vm.vehicle_id}": waypoint {vm.idx + 1} alcancado, '
                f'pairando {hold_time_s:.1f}s')
        else:
            self.get_logger().info(
                f'"{vm.vehicle_id}": waypoint {vm.idx + 1} alcancado')
            self._go_to_next(vm)

    def _go_to_next(self, vm: VehicleMission):
        vm.idx += 1
        vm.state = DONE if vm.idx >= len(vm.waypoints) else PENDING

    def _tick(self):
        for vm in self._missions.values():
            if vm.state == PENDING:
                self._send_waypoint(vm, is_retry=False)
            elif vm.state == WAITING_CONFIRM:
                self._check_confirm_timeout(vm)
            elif vm.state == WAITING_REACHED:
                self._check_reached_timeout(vm)
            elif vm.state == HOLDING:
                if time.monotonic() >= vm.hold_until:
                    self._go_to_next(vm)

            if vm.state in (DONE, FAILED) and not vm.final_logged:
                vm.final_logged = True
                if vm.state == DONE:
                    self.get_logger().info(
                        f'"{vm.vehicle_id}": missao concluida')
                else:
                    self.get_logger().error(
                        f'"{vm.vehicle_id}": missao FALHOU no waypoint '
                        f'{vm.idx + 1} apos {self.max_cmd_retries} '
                        f'tentativa(s)')

        if all(vm.final_logged for vm in self._missions.values()):
            self._log_summary_once()

    def _send_waypoint(self, vm: VehicleMission, is_retry: bool):
        wp = vm.waypoints[vm.idx]
        if not is_retry:
            vm.cmd_id = self._next_cmd_id
            self._next_cmd_id += 1
            vm.retries = 0

        cmd = WaypointCommand()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.cmd_id = vm.cmd_id
        cmd.vehicle_id = vm.vehicle_id
        cmd.latitude = wp['latitude']
        cmd.longitude = wp['longitude']
        cmd.altitude = wp['altitude']
        cmd.hold_time_s = wp['hold_time_s']
        self._pub.publish(cmd)

        vm.sent_at = time.monotonic()
        vm.state = WAITING_CONFIRM
        action = 'reenviando' if is_retry else 'enviando'
        self.get_logger().info(
            f'"{vm.vehicle_id}" cmd_id={vm.cmd_id}: {action} waypoint '
            f'{vm.idx + 1}/{len(vm.waypoints)}')

    def _check_confirm_timeout(self, vm: VehicleMission):
        elapsed = time.monotonic() - vm.sent_at
        if elapsed < self.cmd_confirm_timeout_s:
            return
        if vm.retries >= self.max_cmd_retries:
            vm.state = FAILED
            return
        vm.retries += 1
        self.get_logger().warn(
            f'"{vm.vehicle_id}" cmd_id={vm.cmd_id}: sem confirmacao '
            f'(tentativa {vm.retries}/{self.max_cmd_retries})')
        self._send_waypoint(vm, is_retry=True)

    def _check_reached_timeout(self, vm: VehicleMission):
        if self.waypoint_warn_after_s <= 0 or vm.reached_warned:
            return
        if time.monotonic() - vm.sent_at < self.waypoint_warn_after_s:
            return
        vm.reached_warned = True
        self.get_logger().warn(
            f'"{vm.vehicle_id}" cmd_id={vm.cmd_id}: ainda sem '
            f'waypoint_reached apos {self.waypoint_warn_after_s:.0f}s '
            f'(aviso, nao falha)')

    def _log_summary_once(self):
        if getattr(self, '_summary_logged', False):
            return
        self._summary_logged = True
        done = [v for v in self._missions.values() if v.state == DONE]
        failed = [v for v in self._missions.values() if v.state == FAILED]
        self.get_logger().info(
            f'Missao encerrada: {len(done)} concluido(s), '
            f'{len(failed)} falhou(aram)')


def main(args=None):
    rclpy.init(args=args)
    try:
        node = MissionPlannerNode()
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f'[mission_planner] erro de configuracao: {exc}')
        rclpy.shutdown()
        return
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
