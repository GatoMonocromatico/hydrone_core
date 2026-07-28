#!/usr/bin/env python3
"""Validacao ponta a ponta e medicao de latencia da ponte hibrida.

Publica WaypointCommand repetidamente, espera a MissionState com o
last_cmd_id correspondente, mede o round-trip e grava estatisticas em CSV.

    ros2 run bridge validate_hybrid_bridge.py --ros-args \\
        -p vehicle_id:=hydrone_drone \\
        -p latitude:=-22.90 -p longitude:=-43.20 -p altitude:=30.0 \\
        -p trials:=20
"""
import csv
import math
import statistics
import threading
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)

from bridge_msgs.msg import MissionState, WaypointCommand

# Deve espelhar MISSION_STATE_QOS de hybrid_bridge_node.py.
_MISSION_STATE_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

try:
    import psutil
except ImportError:
    psutil = None


class HybridBridgeValidator(Node):

    def __init__(self):
        super().__init__('validate_hybrid_bridge')

        self.declare_parameter('vehicle_id', 'hydrone_vehicle')
        self.declare_parameter('trials', 10)
        self.declare_parameter('interval_s', 3.0)
        self.declare_parameter('timeout_s', 5.0)
        self.declare_parameter('latitude', -22.90)
        self.declare_parameter('longitude', -43.20)
        self.declare_parameter('altitude', 30.0)
        self.declare_parameter('output_csv', 'hybrid_bridge_latency.csv')
        self.declare_parameter('stress_mode', False)
        self.declare_parameter('monitor_resources', True)

        self.vehicle_id = self.get_parameter('vehicle_id').value
        self.trials = self.get_parameter('trials').value
        self.interval_s = self.get_parameter('interval_s').value
        self.timeout_s = self.get_parameter('timeout_s').value
        self.latitude = self.get_parameter('latitude').value
        self.longitude = self.get_parameter('longitude').value
        self.altitude = self.get_parameter('altitude').value
        self.output_csv = self.get_parameter('output_csv').value
        # stress_mode: dispara o proximo comando sem esperar interval_s.
        self.stress_mode = self.get_parameter('stress_mode').value
        self.monitor_resources = (
            self.get_parameter('monitor_resources').value
            and psutil is not None)
        if (self.get_parameter('monitor_resources').value
                and psutil is None):
            self.get_logger().warn(
                'psutil nao instalado; monitoramento de CPU/RAM desabilitado.')

        self._pub = self.create_publisher(
            WaypointCommand, '/hydrone/waypoint_cmd', 10)
        self._sub = self.create_subscription(
            MissionState, '/hydrone/mission_state', self._on_state,
            _MISSION_STATE_QOS)

        self._pending_cmd_id = None
        self._sent_at = None
        self._results = []  # [(cmd_id, latencia_s), ...]

    def _on_state(self, msg: MissionState):
        if self._pending_cmd_id is None:
            return
        if msg.vehicle_id != self.vehicle_id:
            return
        if msg.last_cmd_id == self._pending_cmd_id:
            latency_s = time.monotonic() - self._sent_at
            self._results.append((self._pending_cmd_id, latency_s))
            self.get_logger().info(
                f'cmd_id={self._pending_cmd_id}: latencia '
                f'= {latency_s * 1000:.1f} ms')
            self._pending_cmd_id = None

    def run(self):
        self._resource_samples = []
        stop_monitor = threading.Event()
        monitor_thread = None
        if self.monitor_resources:
            monitor_thread = threading.Thread(
                target=self._monitor_resources_loop,
                args=(stop_monitor,), daemon=True)
            monitor_thread.start()

        try:
            self._run_trials()
        finally:
            if monitor_thread is not None:
                stop_monitor.set()
                monitor_thread.join(timeout=1.0)

        self._report()

    def _monitor_resources_loop(self, stop_event, sample_interval_s=0.2):
        process = psutil.Process()
        process.cpu_percent(interval=None)  # descarta a 1a leitura (0.0)
        while not stop_event.is_set():
            cpu = process.cpu_percent(interval=None)
            ram = process.memory_percent()
            self._resource_samples.append((cpu, ram))
            stop_event.wait(sample_interval_s)

    def _run_trials(self):
        for trial in range(1, self.trials + 1):
            cmd_id = trial

            cmd = WaypointCommand()
            cmd.header.stamp = self.get_clock().now().to_msg()
            cmd.cmd_id = cmd_id
            cmd.vehicle_id = self.vehicle_id
            cmd.latitude = self.latitude
            cmd.longitude = self.longitude
            cmd.altitude = self.altitude

            self._pending_cmd_id = cmd_id
            self._sent_at = time.monotonic()
            self._pub.publish(cmd)

            deadline = time.monotonic() + self.timeout_s
            while (self._pending_cmd_id is not None
                   and time.monotonic() < deadline):
                rclpy.spin_once(self, timeout_sec=0.05)

            if self._pending_cmd_id is not None:
                self.get_logger().warn(
                    f'cmd_id={cmd_id}: sem confirmacao em '
                    f'{self.timeout_s:.1f}s, descartando tentativa')
                self._pending_cmd_id = None
            elif not self.stress_mode:
                time.sleep(self.interval_s)

    def _report(self):
        if not self._results:
            self.get_logger().error(
                'Nenhuma tentativa teve sucesso: verifique se o mavros e '
                'a ponte hibrida estao rodando contra o SITL.')
            return

        latencies_ms = sorted(lat * 1000.0 for _, lat in self._results)
        mean_ms = statistics.mean(latencies_ms)
        stdev_ms = (statistics.stdev(latencies_ms)
                    if len(latencies_ms) > 1 else 0.0)
        max_ms = latencies_ms[-1]
        p50_ms = _percentile(latencies_ms, 50)
        p95_ms = _percentile(latencies_ms, 95)
        p99_ms = _percentile(latencies_ms, 99)

        self.get_logger().info(
            f'Latencia em {len(latencies_ms)}/{self.trials} tentativas: '
            f'media={mean_ms:.1f} ms, desvio_padrao={stdev_ms:.1f} ms, '
            f'p50={p50_ms:.1f} ms, p95={p95_ms:.1f} ms, '
            f'p99={p99_ms:.1f} ms, max={max_ms:.1f} ms')

        cpu_avg = cpu_max = ram_avg = ram_max = None
        if self._resource_samples:
            cpu_samples = [c for c, _ in self._resource_samples]
            ram_samples = [r for _, r in self._resource_samples]
            cpu_avg, cpu_max = statistics.mean(cpu_samples), max(cpu_samples)
            ram_avg, ram_max = statistics.mean(ram_samples), max(ram_samples)
            self.get_logger().info(
                f'CPU media={cpu_avg:.1f}%, CPU pico={cpu_max:.1f}%, '
                f'RAM media={ram_avg:.1f}%, RAM pico={ram_max:.1f}%')

        path = Path(self.output_csv)
        with path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['cmd_id', 'latencia_ms'])
            for cmd_id, lat in self._results:
                writer.writerow([cmd_id, f'{lat * 1000.0:.3f}'])
            writer.writerow([])
            writer.writerow(['media_ms', f'{mean_ms:.3f}'])
            writer.writerow(['desvio_padrao_ms', f'{stdev_ms:.3f}'])
            writer.writerow(['p50_ms', f'{p50_ms:.3f}'])
            writer.writerow(['p95_ms', f'{p95_ms:.3f}'])
            writer.writerow(['p99_ms', f'{p99_ms:.3f}'])
            writer.writerow(['max_ms', f'{max_ms:.3f}'])
            if cpu_avg is not None:
                writer.writerow(['cpu_media_pct', f'{cpu_avg:.2f}'])
                writer.writerow(['cpu_pico_pct', f'{cpu_max:.2f}'])
                writer.writerow(['ram_media_pct', f'{ram_avg:.2f}'])
                writer.writerow(['ram_pico_pct', f'{ram_max:.2f}'])
        self.get_logger().info(f'Resultados gravados em {path.resolve()}')


def _percentile(sorted_values, pct):
    if not sorted_values:
        return float('nan')
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return d0 + d1


def main(args=None):
    rclpy.init(args=args)
    node = HybridBridgeValidator()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
