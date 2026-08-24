"""Execute scenarios in the simulation."""

import asyncio
import logging
import math
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    from rclpy.node import Node
    from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ScenarioExecutor:
    """Execute a scenario configuration in ROS 2."""

    # Delays from scenario_runner.py
    INITIALPOSE_DELAY_S = 3.0
    GOAL_DELAY_S = 6.0

    def __init__(self, node: Node, scenario: Dict[str, Any]):
        """Initialize executor with ROS node and scenario."""
        if not ROS_AVAILABLE:
            raise RuntimeError("ROS 2 not available")

        self.node = node
        self.scenario = scenario
        self.is_running = False
        self.start_time = 0.0
        self.tasks: List[asyncio.Task] = []

        # Create publishers
        self._create_publishers()

        logger.info(
            f"ScenarioExecutor ready: {scenario.get('name', '?')} "
            f"with {len(scenario.get('robots', []))} robots"
        )

    def _create_publishers(self):
        """Create ROS 2 publishers for goal pose and initial pose."""
        self.initialpose_pubs = {}
        self.goal_pubs = {}

        for robot in self.scenario.get('robots', []):
            robot_id = robot['id']

            # Publisher for initial pose (for AMCL localization)
            self.initialpose_pubs[robot_id] = self.node.create_publisher(
                PoseWithCovarianceStamped,
                f"{robot_id}/initialpose",
                10
            )

            # Publisher for navigation goals
            self.goal_pubs[robot_id] = self.node.create_publisher(
                PoseStamped,
                f"{robot_id}/goal_pose",
                10
            )

    async def start(self):
        """Start scenario execution."""
        if self.is_running:
            logger.warning("Scenario already running")
            return

        self.is_running = True
        self.start_time = datetime.now().timestamp()

        logger.info(f"Starting scenario: {self.scenario.get('name', '?')}")

        # Schedule initial poses
        self._schedule_task(
            self.INITIALPOSE_DELAY_S,
            self._publish_initial_poses
        )

        # Schedule goals
        self._schedule_task(
            self.GOAL_DELAY_S,
            self._publish_goals
        )

        # Schedule scenario events
        for event in self.scenario.get('events', []):
            delay = float(event.get('at_time', 0))
            self._schedule_task(delay, lambda e=event: self._execute_event(e))

    def _schedule_task(self, delay_s: float, callback):
        """Schedule a callback to run after delay."""
        async def _run():
            try:
                await asyncio.sleep(delay_s)
                if self.is_running:
                    callback()
            except asyncio.CancelledError:
                logger.debug(f"Task cancelled after {delay_s}s")
            except Exception as e:
                logger.error(f"Error in scheduled task: {e}")

        task = asyncio.create_task(_run())
        self.tasks.append(task)

    def _publish_initial_poses(self):
        """Publish initial poses for AMCL."""
        for robot in self.scenario.get('robots', []):
            robot_id = robot['id']
            spawn = robot.get('spawn', {})

            msg = PoseWithCovarianceStamped()
            msg.header.frame_id = 'map'
            msg.header.stamp = self.node.get_clock().now().to_msg()
            msg.pose.pose.position.x = float(spawn.get('x', 0.0))
            msg.pose.pose.position.y = float(spawn.get('y', 0.0))
            msg.pose.pose.position.z = float(spawn.get('z', 0.0))

            # Convert yaw to quaternion
            yaw = float(spawn.get('yaw', 0.0))
            msg.pose.pose.orientation.x = 0.0
            msg.pose.pose.orientation.y = 0.0
            msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
            msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

            # Tight covariance (this is the exact spawn pose from Gazebo)
            msg.pose.covariance[0] = 0.01  # x variance
            msg.pose.covariance[7] = 0.01  # y variance
            msg.pose.covariance[35] = 0.01  # theta variance

            self.initialpose_pubs[robot_id].publish(msg)
            logger.info(f"Published initial pose for {robot_id} at ({spawn.get('x')}, {spawn.get('y')})")

    def _publish_goals(self):
        """Publish navigation goals."""
        for robot in self.scenario.get('robots', []):
            robot_id = robot['id']
            goal = robot.get('goal', {})

            msg = PoseStamped()
            msg.header.frame_id = 'map'
            msg.header.stamp = self.node.get_clock().now().to_msg()
            msg.pose.position.x = float(goal.get('x', 0.0))
            msg.pose.position.y = float(goal.get('y', 0.0))
            msg.pose.position.z = 0.0
            msg.pose.orientation.x = 0.0
            msg.pose.orientation.y = 0.0
            msg.pose.orientation.z = 0.0
            msg.pose.orientation.w = 1.0  # Identity orientation

            self.goal_pubs[robot_id].publish(msg)
            logger.info(f"Published goal for {robot_id}: ({goal.get('x')}, {goal.get('y')})")

    def _execute_event(self, event: Dict[str, Any]):
        """Execute a scenario event."""
        event_type = event.get('type', '')
        logger.info(f"Executing event: {event_type} at t={event.get('at_time')}")

        # Event types from scenario_config.py:
        # - spawn_obstacle: {name, model, pose: {x, y, z?, yaw?}}
        # - remove_obstacle: {name}
        # - robot_failure: {robot_id, duration?}
        # - network_disruption: {robot_id, duration}

        # Full event handling requires Gazebo service calls and other ROS components
        # For now, just log the event; can be extended later
        logger.debug(f"Event details: {event}")

    async def stop(self):
        """Stop scenario execution."""
        logger.info("Stopping scenario")
        self.is_running = False
        for task in self.tasks:
            if not task.done():
                task.cancel()
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []

    def is_active(self) -> bool:
        """Check if scenario is running."""
        return self.is_running
