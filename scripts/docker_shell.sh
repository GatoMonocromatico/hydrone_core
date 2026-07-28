#!/usr/bin/env bash
# Open an extra ROS-ready shell in the already-running Hydrone Core container.
# Use one shell per long-running process (e.g. the bridge launch in one, the
# latency validator in another).
set -e
cd "$(dirname "$0")/.."
exec docker compose -f docker/docker-compose.yml exec hydrone bash
