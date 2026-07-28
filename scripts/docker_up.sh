#!/usr/bin/env bash
# Build (if needed) and start the Hydrone Core container, then drop into a
# ROS-ready shell. SITL and QGroundControl run on the HOST, not in here.
set -e
cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker/docker-compose.yml)

# `up` (no --build) reuses the cached image and never contacts the registry.
# The image is built automatically on first run (when it doesn't exist yet).
# After editing the Dockerfile, force a rebuild with:  scripts/docker_up.sh --build
BUILD_ARG=()
if [ "${1:-}" = "--build" ]; then
  BUILD_ARG=(--build)
  shift
fi

"${COMPOSE[@]}" up -d "${BUILD_ARG[@]}"

cat <<'EOF'

Container 'hydrone_core' is up (network=host, ipc=host).
First run only — build the workspace once from inside the shell:

    colcon build --symlink-install
    source install/setup.bash

Open more shells anytime with: scripts/docker_shell.sh

EOF

exec "${COMPOSE[@]}" exec hydrone bash
