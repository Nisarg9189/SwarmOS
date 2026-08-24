#!/usr/bin/env python3
import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory


def start_bridges_and_nav2(context, *args, **kwargs):
    """Start ros_gz_bridge and Nav2 bringup for each robot."""
    spawn_amrs_count = int(context.launch_configurations['spawn_amrs'])

    # Get the simulation package directory (handles both source and installed locations)
    try:
        simulation_dir = get_package_share_directory('simulation')
    except:
        # Fallback to source directory if package not found (for development)
        simulation_dir = str(Path(__file__).parent.parent)

    actions = []

    for i in range(spawn_amrs_count):
        robot_id = f"amr_{i}"

        # Start ros_gz_bridge for this robot (odometry and lidar)
        # Bridges: Gazebo /model/{robot_id}/* topics → ROS2 /{robot_id}/* topics
        # [  = Gazebo→ROS (incoming), ] = ROS→Gazebo (outgoing)
        # Remapping: /model/{robot_id}/odometry → /{robot_id}/odom
        #            /model/{robot_id}/lidar/scan → /{robot_id}/scan
        bridge_cmd = ExecuteProcess(
            cmd=[
                'bash', '-c',
                f'source /opt/ros/jazzy/setup.bash && ' +
                f'ros2 run ros_gz_bridge parameter_bridge ' +
                f'/model/{robot_id}/odometry_with_covariance@nav_msgs/msg/Odometry[gz.msgs.OdometryWithCovariance ' +
                f'/model/{robot_id}/lidar/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan ' +
                f'/model/{robot_id}/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist ' +
                f'--ros-args ' +
                f'-r /model/{robot_id}/odometry_with_covariance:=/{robot_id}/odom ' +
                f'-r /model/{robot_id}/lidar/scan:=/{robot_id}/scan'
            ],
            output='screen'
        )
        actions.append(bridge_cmd)

        # Start Nav2 bringup for this robot
        nav2_cmd = ExecuteProcess(
            cmd=[
                'bash', '-c',
                f'source /opt/ros/jazzy/setup.bash && ' +
                f'ros2 launch nav2_bringup bringup_launch.py ' +
                f'namespace:={robot_id} ' +
                f'use_namespace:=true ' +
                f'map:={simulation_dir}/warehouse_map.yaml ' +
                f'use_sim_time:=true'
            ],
            output='screen'
        )
        actions.append(nav2_cmd)

    return actions


def generate_launch_description():
    # Declare arguments
    spawn_amrs_arg = DeclareLaunchArgument(
        'spawn_amrs',
        default_value='3',
        description='Number of AMRs to spawn'
    )

    # Get paths
    try:
        simulation_dir = get_package_share_directory('simulation')
    except:
        # Fallback to source directory if package not found (for development)
        simulation_dir = str(Path(__file__).parent.parent)

    world_file = os.path.join(simulation_dir, 'warehouse.world')

    ld = LaunchDescription([spawn_amrs_arg])

    # Start Gazebo simulator using ros_gz_sim package
    # This replaces gazebo_ros which is Gazebo Classic and not available in Jazzy
    # The world file includes amr_0, amr_1, amr_2 models
    gazebo_cmd = ExecuteProcess(
        cmd=[
            'bash', '-c',
            f'export GZ_VERSION=garden && ' +
            f'source /opt/ros/jazzy/setup.bash && ' +
            f'. /opt/ros/jazzy/install/setup.bash 2>/dev/null; true && ' +
            f'ros2 launch ros_gz_sim gz_sim.launch.py gz_args:="-r -s -v 4 {world_file}"'
        ],
        output='screen'
    )
    ld.add_action(gazebo_cmd)

    # Start bridges and Nav2 stacks for each robot after Gazebo is ready (5 second delay)
    bridges_and_nav2_actions = TimerAction(
        period=5.0,
        actions=[OpaqueFunction(function=start_bridges_and_nav2)]
    )
    ld.add_action(bridges_and_nav2_actions)

    return ld


if __name__ == '__main__':
    generate_launch_description()
