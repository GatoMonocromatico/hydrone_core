#!/usr/bin/env bash
# Source ROS + the (optional) workspace overlay, then run whatever CMD/args
# were given. `docker exec` does NOT run this entrypoint, so the same sourcing
# is also baked into /root/.bashrc for interactive exec shells.
set -e
source /opt/ros/humble/setup.bash
if [ -f /workspace/install/setup.bash ]; then
  source /workspace/install/setup.bash
fi
exec "$@"
