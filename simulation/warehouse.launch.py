#!/usr/bin/env python3
import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    # Declare arguments
    spawn_amrs = DeclareLaunchArgument(
        'spawn_amrs',
        default_value='3',
        description='Number of AMRs to spawn'
    )

    # Get paths
    simulation_dir = str(Path(__file__).parent)
    world_file = os.path.join(simulation_dir, 'warehouse.world')

    ld = LaunchDescription([
        spawn_amrs,
    ])

    # Start Gazebo using gazebo_ros
    gzserver_node = Node(
        package='gazebo_ros',
        executable='gzserver',
        arguments=[world_file, '--verbose'],
        output='screen',
    )
    ld.add_action(gzserver_node)

    # Start Gazebo client
    gzclient_node = Node(
        package='gazebo_ros',
        executable='gzclient',
        output='screen',
    )
    ld.add_action(gzclient_node)

    return ld


if __name__ == '__main__':
    generate_launch_description()
