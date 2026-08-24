#!/usr/bin/env python3
"""Convert odometry messages to TF2 transforms.

Reads Odometry messages and broadcasts the corresponding TF transform
from the odometry frame to the robot's base_link frame.
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped
import sys


class OdomToTf(Node):
    def __init__(self, robot_id):
        super().__init__(f'odom_to_tf_{robot_id}')
        self.robot_id = robot_id
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_subscription(
            Odometry,
            f'/{robot_id}/odom',
            self.odom_callback,
            10
        )

    def odom_callback(self, msg):
        """Convert odometry message to TF transform."""
        t = TransformStamped()
        t.header.stamp = msg.header.stamp
        t.header.frame_id = msg.header.frame_id  # Usually "odom"
        t.child_frame_id = f'{self.robot_id}/base_link'
        t.transform.translation.x = msg.pose.pose.position.x
        t.transform.translation.y = msg.pose.pose.position.y
        t.transform.translation.z = msg.pose.pose.position.z
        t.transform.rotation = msg.pose.pose.orientation
        self.tf_broadcaster.sendTransform(t)


if __name__ == '__main__':
    rclpy.init()
    if len(sys.argv) > 1:
        robot_id = sys.argv[1]
    else:
        robot_id = 'amr_0'
    node = OdomToTf(robot_id)
    rclpy.spin(node)
