# Docker setup — Hydrone Core

Runs the ROS 2 nodes (2× mavros + 2× ponte híbrida, optionally the mission
planner) in a container. **SITL and QGroundControl run on the host** — the
container only talks to them over UDP via `network_mode: host`.

Base image `ros:humble` is Ubuntu 22.04 / Python 3.10, so it is ABI-compatible
with the Ubuntu 22 distrobox: `bridge_msgs` built here can be sourced from the
distrobox to inspect the custom topics.

## Prerequisites

- Docker + the Compose plugin (`docker compose`).
- Both SITL instances already running on the host, each with a `--out` pointing
  at the mavros ports below (see `../validacao_runbook.md`).

## Ports (host)

| Stream | Port | Consumer |
|--------|------|----------|
| drone MAVLink | 14550 | mavros (container) |
| boat MAVLink  | 14560 | mavros (container) |
| drone MAVLink | 14445 | QGroundControl (host) |
| boat MAVLink  | 14446 | QGroundControl (host) |

## Bring it up

```bash
scripts/docker_up.sh
```

This builds the image, starts the container detached, and drops you into a
ROS-ready shell. **First run only**, build the workspace inside that shell:

```bash
colcon build --symlink-install
source install/setup.bash          # or just open a fresh shell
```

Then follow the validation runbook (`../validacao_runbook.md`). Typical layout:

```bash
# shell 1 — the bridge stack
ros2 launch bridge iniciar_ponte_hibrida.launch.py

# shell 2 (scripts/docker_shell.sh) — latency validator
ros2 run bridge validate_hybrid_bridge.py --ros-args -p vehicle_id:=hydrone_drone
```

Open extra shells with `scripts/docker_shell.sh`.

## Talking to the distrobox

For `ros2 topic echo` from the distrobox to work, both environments must match:

- **`ROS_DOMAIN_ID`** — same value. Export it before `docker_up.sh` (or put it in
  a `.env` next to the compose file); it defaults to `0`.
- **`RMW_IMPLEMENTATION`** — same DDS vendor (different vendors do not
  interoperate). Defaults to `rmw_fastrtps_cpp` (Humble's default).
- The distrobox must **source the same `install/setup.bash`** (or its own build
  of `bridge_msgs`) to deserialize the custom messages.

```bash
# example: run on domain 7 with Cyclone DDS in both places
export ROS_DOMAIN_ID=7
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
scripts/docker_up.sh
```

## Caveats

- **Root-owned build artifacts.** The container runs as root, so `build/`,
  `install/`, `log/` created under the repo will be root-owned on the host. The
  distrobox can still *read/source* them fine (that is all it needs). To clean
  from the host use `sudo rm -rf build install log`, or delete them from inside
  the container.
- **Port already in use.** With host networking, mavros binds 14550/14560 on the
  host. Make sure nothing else (a stray mavros, a previous container) holds them.
- **Arming/takeoff.** `auto_arm` is not exposed as a launch arg and defaults to
  false; ArduCopter will not take off from a position setpoint. See section 7 of
  the runbook for the manual `mode guided` / `arm throttle` / `takeoff` path.
```
