# hydrone_core

An early ROS1/catkin package: a `bridge` that brings up `mavros` for two
vehicles side by side (`uav1`/`uav2`), each in its own namespace, as a
starting point for talking to multiple MAVLink vehicles from ROS at once.
No further logic is implemented on this branch — it's a launch-file-only
prototype from before the project moved to ROS2.

The real, current Hydrone autonomy work lives elsewhere:

- **[Hydrone CBR 2026 autonomy stack](https://github.com/GatoMonocromatico/joao_pessoa_2026)**
  (fork of the team repo) — the full ROS2 Humble stack flown in simulation
  and on real hardware for RoboCup Brasil's Flying Robot League: vision,
  navigation, mission state machine, controller.
- **[Hybrid ROS2↔MAVLink bridge validation](https://github.com/hydrone-furg/hydrone_core/pull/2)**
  — the same idea this package started (a bridge in front of MAVROS), taken
  to a working ROS2 implementation and validated end-to-end against real
  ArduPilot SITL: 4 real bugs found and fixed, latency measured (drone
  ~4.0ms, boat ~3.3ms round-trip through the bridge), state machine
  validated on both vehicles simultaneously.
