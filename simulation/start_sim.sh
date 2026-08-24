#!/bin/bash
# Start warehouse simulation with Gazebo and Nav2

set -e

source /opt/ros/jazzy/setup.bash

# Start Gazebo in background
gazebo /workspace/simulation/warehouse.world &
GAZEBO_PID=$!

# Wait for Gazebo to start
sleep 5

# Start Nav2 for each AMR
for i in {0..2}; do
    echo "Starting Nav2 for amr_$i..."
    ros2 launch nav2_bringup bringup_launch.py \
        namespace:=amr_$i \
        use_namespace:=True \
        use_sim_time:=True \
        params_file:=/workspace/simulation/nav2_params.yaml &
done

# Wait for all processes
wait
