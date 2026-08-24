#!/usr/bin/env python3
import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess


def generate_launch_description():
    # Declare arguments
    spawn_amrs_arg = DeclareLaunchArgument(
        'spawn_amrs',
        default_value='3',
        description='Number of AMRs to spawn'
    )

    # Get paths
    simulation_dir = str(Path(__file__).parent)
    world_file = os.path.join(simulation_dir, 'warehouse.world')

    ld = LaunchDescription([spawn_amrs_arg])

    # Start Gazebo simulator using Ignition Gazebo (via ros_gz_sim package)
    # This replaces gazebo_ros which is Gazebo Classic and not available in Jazzy
    gazebo_cmd = ExecuteProcess(
        cmd=[
            'bash', '-c',
            f'source /opt/ros/jazzy/setup.bash && ' +
            f'ign gazebo -r -v 4 {world_file}'
        ],
        output='screen'
    )
    ld.add_action(gazebo_cmd)

    return ld


if __name__ == '__main__':
    generate_launch_description()
