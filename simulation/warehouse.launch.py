#!/usr/bin/env python3
import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.launch_context import LaunchContext


def generate_launch_description():
    # Declare arguments
    spawn_amrs = DeclareLaunchArgument(
        'spawn_amrs',
        default_value='3',
        description='Number of AMRs to spawn'
    )

    # Get paths
    simulation_dir = str(Path(__file__).parent)

    ld = LaunchDescription([
        spawn_amrs,
    ])

    # Start Gazebo with warehouse world
    gazebo_node = Node(
        package='gazebo_ros',
        executable='gazebo',
        arguments=[os.path.join(simulation_dir, 'warehouse.world')],
        output='screen',
        launch_type='background',
    )
    ld.add_action(gazebo_node)

    # Spawn AMRs
    num_amrs = 3
    for i in range(num_amrs):
        robot_id = f'amr_{i}'

        # Create simple URDF for robot spawn
        urdf_content = f"""<?xml version="1.0"?>
<robot name="{robot_id}">
  <link name="base_link">
    <inertial>
      <mass value="10.0"/>
      <inertia ixx="0.1" ixy="0" ixz="0" iyy="0.1" iyz="0" izz="0.1"/>
    </inertial>
    <collision>
      <geometry>
        <cylinder radius="0.25" length="0.5"/>
      </geometry>
    </collision>
    <visual>
      <geometry>
        <cylinder radius="0.25" length="0.5"/>
      </geometry>
      <material name="blue">
        <color rgba="0 0 1 1"/>
      </material>
    </visual>
  </link>

  <link name="caster_wheel">
    <inertial>
      <mass value="0.5"/>
      <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>
    </inertial>
    <collision>
      <geometry>
        <sphere radius="0.05"/>
      </geometry>
    </collision>
    <visual>
      <geometry>
        <sphere radius="0.05"/>
      </geometry>
    </visual>
  </link>

  <joint name="caster_joint" type="fixed">
    <origin xyz="0 0 -0.3" rpy="0 0 0"/>
    <parent link="base_link"/>
    <child link="caster_wheel"/>
  </joint>

  <link name="left_wheel"/>
  <link name="right_wheel"/>

  <joint name="left_wheel_joint" type="continuous">
    <origin xyz="0 0.2 0" rpy="1.5708 0 0"/>
    <parent link="base_link"/>
    <child link="left_wheel"/>
    <axis xyz="0 0 1"/>
  </joint>

  <joint name="right_wheel_joint" type="continuous">
    <origin xyz="0 -0.2 0" rpy="1.5708 0 0"/>
    <parent link="base_link"/>
    <child link="right_wheel"/>
    <axis xyz="0 0 1"/>
  </joint>

  <link name="lidar_link"/>
  <joint name="lidar_joint" type="fixed">
    <origin xyz="0 0 0.3" rpy="0 0 0"/>
    <parent link="base_link"/>
    <child link="lidar_link"/>
  </joint>
</robot>"""

        urdf_path = f'/tmp/{robot_id}.urdf'
        with open(urdf_path, 'w') as f:
            f.write(urdf_content)

        # Initial spawn position
        x_pos = i * 2 - 2
        y_pos = i * 2 - 2

        spawn_node = Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=[
                '-entity', robot_id,
                '-file', urdf_path,
                '-x', str(x_pos),
                '-y', str(y_pos),
                '-z', '0.25',
            ],
            output='screen',
        )
        ld.add_action(spawn_node)

        # Start Nav2 for this robot
        nav2_yaml = os.path.join(simulation_dir, 'nav2_params.yaml')

        # Create a parameterized nav2_params for this robot
        nav2_config = f"""
amr_{i}:
  amcl:
    ros__parameters:
      use_sim_time: true
      initial_pose:
        x: {x_pos}
        y: {y_pos}
        z: 0.0
        yaw: 0.0
  bt_navigator:
    ros__parameters:
      use_sim_time: true
  controller_server:
    ros__parameters:
      use_sim_time: true
  local_costmap:
    local_costmap:
      ros__parameters:
        use_sim_time: true
  global_costmap:
    global_costmap:
      ros__parameters:
        use_sim_time: true
  planner_server:
    ros__parameters:
      use_sim_time: true
"""
        robot_nav2_yaml = f'/tmp/nav2_params_{i}.yaml'
        with open(robot_nav2_yaml, 'w') as f:
            f.write(nav2_config)

        nav2_node = Node(
            package='nav2_bringup',
            executable='bringup_launch.py',
            arguments=[
                f'namespace:=amr_{i}',
                f'use_namespace:=True',
                f'use_sim_time:=True',
                f'params_file:={nav2_yaml}',
            ],
            output='screen',
        )
        ld.add_action(nav2_node)

        # Create robot state publisher and TF for each robot
        tf_node = Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name=f'robot_state_publisher_{i}',
            namespace=f'amr_{i}',
            parameters=[{'use_sim_time': True, 'robot_description': urdf_content}],
            output='screen',
        )
        ld.add_action(tf_node)

    return ld


if __name__ == '__main__':
    generate_launch_description()
