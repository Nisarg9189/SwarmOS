#!/usr/bin/env python3
import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def spawn_robots_and_nav2(context, *args, **kwargs):
    """Spawn AMRs and start Nav2 stacks."""
    spawn_amrs_count = int(context.launch_configurations['spawn_amrs'])
    simulation_dir = str(Path(__file__).parent)

    actions = []

    # Spawn each robot as a model in Gazebo
    for i in range(spawn_amrs_count):
        robot_id = f"amr_{i}"

        # Define a minimal robot model in SDF format
        robot_sdf = f'''<?xml version="1.0" ?>
<sdf version="1.7">
  <model name="{robot_id}">
    <pose>{i*3} {i*3} 0 0 0 0</pose>
    <link name="base_link">
      <inertial>
        <mass>20</mass>
        <inertia>
          <ixx>0.1</ixx>
          <ixy>0</ixy>
          <ixz>0</ixz>
          <iyy>0.1</iyy>
          <iyz>0</iyz>
          <izz>0.2</izz>
        </inertia>
      </inertial>
      <collision name="base_collision">
        <geometry>
          <cylinder>
            <radius>0.25</radius>
            <length>0.3</length>
          </cylinder>
        </geometry>
      </collision>
      <visual name="base_visual">
        <geometry>
          <cylinder>
            <radius>0.25</radius>
            <length>0.3</length>
          </cylinder>
        </geometry>
        <material>
          <ambient>0.1 0.1 0.5 1</ambient>
          <diffuse>0.1 0.1 0.8 1</diffuse>
        </material>
      </visual>
    </link>
    <plugin filename="libignition-gazebo-pose-publisher-system.so" name="pose_publisher">
      <publish_link_pose>true</publish_link_pose>
      <publish_sensor_pose>true</publish_sensor_pose>
    </plugin>
  </model>
</sdf>'''

        # Escape quotes for shell command
        robot_sdf_escaped = robot_sdf.replace('"', '\\"')

        # Spawn the robot using ros2 service
        spawn_cmd = ExecuteProcess(
            cmd=['bash', '-c', f'''
              ros2 service call /spawn_entity ros_gz_sim/SpawnEntity "{{name: '{robot_id}', xml: ''{robot_sdf_escaped}''}}"
            '''],
            output='screen'
        )
        actions.append(spawn_cmd)

        # Start Nav2 bringup for this robot with proper namespace
        nav2_cmd = ExecuteProcess(
            cmd=[
                'bash', '-c',
                f'source /opt/ros/jazzy/setup.bash && ' + \
                f'ros2 launch nav2_bringup bringup_launch.py ' + \
                f'namespace:={robot_id} ' + \
                f'use_namespace:=true ' + \
                f'map:={simulation_dir}/warehouse_map.yaml ' + \
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
    simulation_dir = str(Path(__file__).parent)
    world_file = os.path.join(simulation_dir, 'warehouse.world')

    ld = LaunchDescription([spawn_amrs_arg])

    # Start Gazebo simulator using ros_gz_sim
    gazebo_cmd = ExecuteProcess(
        cmd=[
            'bash', '-c',
            f'source /opt/ros/jazzy/setup.bash && ' +
            f'ros2 launch ros_gz_sim gz_sim.launch.py gz_args:="-r -v4 {world_file}"'
        ],
        output='screen'
    )
    ld.add_action(gazebo_cmd)

    # Spawn robots and Nav2 after Gazebo is ready
    ld.add_action(
        TimerAction(
            period=5.0,
            actions=[OpaqueFunction(function=spawn_robots_and_nav2)]
        )
    )

    return ld


if __name__ == '__main__':
    generate_launch_description()
