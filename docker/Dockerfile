# Hydrone Core — runtime for the ROS 2 <-> MAVLink bridge (mavros x2 + ponte hibrida x2).
#
# Base is Ubuntu 22.04 Jammy / Python 3.10, i.e. ABI-compatible with the
# Ubuntu 22 distrobox used for topic inspection — bridge_msgs built here can be
# sourced from the distrobox to `ros2 topic echo` the custom messages.
#
# SITL and QGroundControl are expected to run on the HOST; this image only runs
# the ROS nodes, so no X11/GPU is needed.
FROM ros:humble

SHELL ["/bin/bash", "-c"]

# ros:humble already ships colcon, rosdep, build-essential and the rosidl
# generators. We add mavros (+ msgs), the geoid dataset tooling that mavros
# needs for altitude, and the Python libs the nodes/validator use.
#   - geographiclib-get-geoids egm96-5: without the geoid dataset mavros logs a
#     fatal error and global_position never comes up properly.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-humble-mavros \
      ros-humble-mavros-msgs \
      ros-humble-rosidl-default-generators \
      geographiclib-tools \
      python3-yaml \
      python3-psutil \
 && geographiclib-get-geoids egm96-5 \
 && rm -rf /var/lib/apt/lists/*

# Every interactive shell (docker exec ... bash) sources ROS and, once built,
# the workspace overlay — so extra shells are ready with no manual sourcing.
RUN echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc \
 && echo '[ -f /workspace/install/setup.bash ] && source /workspace/install/setup.bash' >> /root/.bashrc

WORKDIR /workspace

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Keep the container alive so you can attach as many shells as you like.
CMD ["sleep", "infinity"]
