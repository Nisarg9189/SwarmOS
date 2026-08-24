# Gazebo Simulation + Nav2 Stack

Warehouse environment with 3 autonomous mobile robots (AMRs) and navigation stack.

## Files

- `warehouse.world` — Gazebo world definition (to be created)
- `warehouse.launch.py` — ROS 2 launch file for simulation
- `nav2_params.yaml` — Navigation stack parameters
- `models/` — Robot and environment models

## Launch

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch simulation warehouse.launch.py spawn_amrs:=3
```

## Topics Published by Simulation

- `/tf` — Robot transforms (odometry, map frame)
- `/scan` — LiDAR point cloud (simulated)
- `/amr_N/local_costmap/costmap` — Local occupancy grid
- `/amr_N/global_costmap/costmap` — Global map

## Integration with Agents

Agents subscribe to these topics to:
1. Read own position via TF lookups
2. Detect obstacles via LiDAR
3. Query costmaps for path planning

Agents publish `/move_base_simple/goal` to Nav2, which controls robot motion.

## Testing

```bash
# In one terminal: start sim
ros2 launch simulation warehouse.launch.py

# In another: verify topics
ros2 topic list
ros2 topic hz /tf
```
