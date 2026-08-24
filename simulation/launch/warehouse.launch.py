#!/usr/bin/env python3
import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory


def start_bridges_and_odom_tf(context, *args, **kwargs):
    """Start ros_gz_bridge and odometry-to-TF converters for each robot."""
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

        # Start odometry-to-TF converter for this robot
        # Reads /{robot_id}/odom and publishes /tf with odom→base_link transform
        # This must start before Nav2 to ensure TF frames exist
        odom_to_tf_cmd = ExecuteProcess(
            cmd=[
                'bash', '-c',
                f'source /opt/ros/jazzy/setup.bash && ' +
                f'python3 {simulation_dir}/odom_to_tf.py {robot_id}'
            ],
            output='screen'
        )
        actions.append(odom_to_tf_cmd)

    return actions


def start_nav2(context, *args, **kwargs):
    """Start Nav2 bringup for each robot (after bridges and TF converters are ready)."""
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

        # Generate robot-specific nav2_params with absolute frame IDs
        # This works around namespace resolution issues
        nav2_params_file = os.path.join(simulation_dir, f'nav2_params_{robot_id}.yaml')

        # Read the base nav2_params and replace relative frame IDs with absolute ones
        with open(os.path.join(simulation_dir, 'nav2_params.yaml'), 'r') as f:
            nav2_params = f.read()

        # Replace relative frame IDs with absolute ones that include the robot namespace
        nav2_params = nav2_params.replace('odom_frame_id: "odom"', f'odom_frame_id: "{robot_id}/odom"')
        nav2_params = nav2_params.replace('global_frame: odom', f'global_frame: {robot_id}/odom')
        nav2_params = nav2_params.replace('robot_base_frame: base_link', f'robot_base_frame: {robot_id}/base_link')
        nav2_params = nav2_params.replace('odom_topic: odom', f'odom_topic: /{robot_id}/odom')

        # Write the robot-specific params file
        with open(nav2_params_file, 'w') as f:
            f.write(nav2_params)

        # Start Nav2 bringup for this robot with the robot-specific params
        nav2_cmd = ExecuteProcess(
            cmd=[
                'bash', '-c',
                f'source /opt/ros/jazzy/setup.bash && ' +
                f'ros2 launch nav2_bringup bringup_launch.py ' +
                f'namespace:={robot_id} ' +
                f'use_namespace:=true ' +
                f'params_file:={nav2_params_file} ' +
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

    # Start bridges and odometry-to-TF converters after Gazebo is ready (5 second delay)
    bridges_and_odom_tf_actions = TimerAction(
        period=5.0,
        actions=[OpaqueFunction(function=start_bridges_and_odom_tf)]
    )
    ld.add_action(bridges_and_odom_tf_actions)

    # Start Nav2 stacks after bridges and TF converters are ready (10 second delay total)
    nav2_actions = TimerAction(
        period=10.0,
        actions=[OpaqueFunction(function=start_nav2)]
    )
    ld.add_action(nav2_actions)

    return ld


if __name__ == '__main__':
    generate_launch_description()
