"""ROS 2 bridge for simulation control."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Dict, List, Callable, Any, TYPE_CHECKING
from datetime import datetime
from pathlib import Path

try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
    from nav_msgs.msg import Odometry, OccupancyGrid
    from rosgraph_msgs.msg import Clock
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False

if TYPE_CHECKING:
    from nav_msgs.msg import Odometry, OccupancyGrid
    from rosgraph_msgs.msg import Clock

import yaml

from .models import (
    Pose, Velocity, RobotState, SimulationStatus, RobotStatus,
    CoordinationStatus, WarehouseGraph, WarehouseNode, WarehouseEdge, Scenario
)

logger = logging.getLogger(__name__)


class RoSBridge:
    """Bridge between FastAPI and ROS 2."""

    def __init__(self):
        """Initialize ROS 2 bridge."""
        # Always initialize these regardless of ROS availability
        self.node = None
        self.ros_initialized = False
        self.subscriptions = {}
        self.clock_sub = None
        self.map_sub = None
        self.odom_subs = {}
        self.goal_pubs = {}
        self.robots: Dict[str, RobotState] = {}
        self.sim_time = 0.0
        self.sim_started = False
        self.warehouse_map: Optional[OccupancyGrid] = None
        self.warehouse_graph: Optional[WarehouseGraph] = None
        self.on_robot_state_changed: Optional[Callable] = None
        self.on_sim_time_changed: Optional[Callable] = None
        self.on_robot_added: Optional[Callable] = None
        self.on_robot_removed: Optional[Callable] = None
        self.nav_active: Dict[str, bool] = {}

        if not ROS_AVAILABLE:
            logger.warning("ROS 2 not available - running in simulation-only mode")
            self._initialize_mock_robots()
            return

        try:
            if not rclpy.ok():
                rclpy.init()

            self.node = rclpy.create_node('simulation_web_backend')
            self.ros_initialized = True
            logger.info("ROS 2 initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ROS 2: {e}")
            self.ros_initialized = False
            self.node = None
            self._initialize_mock_robots()

    def _initialize_mock_robots(self) -> None:
        """Initialize mock robots and warehouse graph for testing when ROS 2 is unavailable."""
        import time
        current_time = time.time()

        mock_robots = [
            RobotState(
                id="robot_1",
                namespace="/amr_0",
                pose=Pose(x=0.0, y=0.0, theta=0.0),
                velocity=Velocity(vx=0.0, vy=0.0, omega=0.0),
                status=RobotStatus.IDLE,
                coordination_status=CoordinationStatus.ACTIVE,
                is_online=True,
                last_update_time=current_time,
            ),
            RobotState(
                id="robot_2",
                namespace="/amr_1",
                pose=Pose(x=0.0, y=0.0, theta=0.0),
                velocity=Velocity(vx=0.0, vy=0.0, omega=0.0),
                status=RobotStatus.IDLE,
                coordination_status=CoordinationStatus.ACTIVE,
                is_online=True,
                last_update_time=current_time,
            ),
            RobotState(
                id="robot_3",
                namespace="/amr_2",
                pose=Pose(x=0.0, y=0.0, theta=0.0),
                velocity=Velocity(vx=0.0, vy=0.0, omega=0.0),
                status=RobotStatus.IDLE,
                coordination_status=CoordinationStatus.YIELDING,
                is_online=True,
                last_update_time=current_time,
            ),
        ]

        for robot in mock_robots:
            self.robots[robot.id] = robot
            logger.info(f"Initialized mock robot: {robot.id}")

        mock_nodes = [
            WarehouseNode(id="node_0", x=0.0, y=0.0),
            WarehouseNode(id="node_1", x=5.0, y=0.0),
            WarehouseNode(id="node_2", x=10.0, y=0.0),
            WarehouseNode(id="node_3", x=0.0, y=5.0),
            WarehouseNode(id="node_4", x=5.0, y=5.0),
            WarehouseNode(id="node_5", x=10.0, y=5.0),
            WarehouseNode(id="node_6", x=0.0, y=10.0),
            WarehouseNode(id="node_7", x=5.0, y=10.0),
            WarehouseNode(id="node_8", x=10.0, y=10.0),
            WarehouseNode(id="node_9", x=15.0, y=0.0),
            WarehouseNode(id="node_10", x=15.0, y=5.0),
            WarehouseNode(id="node_11", x=15.0, y=10.0),
            WarehouseNode(id="node_12", x=0.0, y=15.0),
            WarehouseNode(id="node_13", x=5.0, y=15.0),
            WarehouseNode(id="node_14", x=10.0, y=15.0),
        ]

        mock_edges = [
            WarehouseEdge(from_node="node_0", to_node="node_1", segment_id="seg_0_1"),
            WarehouseEdge(from_node="node_1", to_node="node_2", segment_id="seg_1_2"),
            WarehouseEdge(from_node="node_0", to_node="node_3", segment_id="seg_0_3"),
            WarehouseEdge(from_node="node_1", to_node="node_4", segment_id="seg_1_4"),
            WarehouseEdge(from_node="node_2", to_node="node_5", segment_id="seg_2_5"),
            WarehouseEdge(from_node="node_3", to_node="node_4", segment_id="seg_3_4"),
            WarehouseEdge(from_node="node_4", to_node="node_5", segment_id="seg_4_5"),
            WarehouseEdge(from_node="node_3", to_node="node_6", segment_id="seg_3_6"),
            WarehouseEdge(from_node="node_4", to_node="node_7", segment_id="seg_4_7"),
            WarehouseEdge(from_node="node_5", to_node="node_8", segment_id="seg_5_8"),
            WarehouseEdge(from_node="node_2", to_node="node_9", segment_id="seg_2_9"),
            WarehouseEdge(from_node="node_5", to_node="node_10", segment_id="seg_5_10"),
            WarehouseEdge(from_node="node_8", to_node="node_11", segment_id="seg_8_11"),
            WarehouseEdge(from_node="node_6", to_node="node_7", segment_id="seg_6_7"),
            WarehouseEdge(from_node="node_7", to_node="node_8", segment_id="seg_7_8"),
        ]

        self.warehouse_graph = WarehouseGraph(nodes=mock_nodes, edges=mock_edges)
        logger.info(f"Initialized mock warehouse graph with {len(mock_nodes)} nodes")

    def connect(self) -> bool:
        """Establish ROS 2 connection."""
        if not self.ros_initialized or not self.node:
            logger.warning("ROS 2 not initialized, skipping connection")
            return False

        try:
            # Subscribe to global topics
            self._subscribe_to_clock()
            self._subscribe_to_map()
            logger.info("Connected to ROS 2 global topics")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to ROS 2: {e}")
            return False

    def _subscribe_to_clock(self) -> None:
        """Subscribe to simulation clock."""
        if not self.node:
            return

        def on_clock(msg: Clock):
            self.sim_time = msg.clock.sec + msg.clock.nanosec / 1e9
            if self.on_sim_time_changed:
                self.on_sim_time_changed(self.sim_time)

        self.clock_sub = self.node.create_subscription(Clock, '/clock', on_clock, 10)

    def _subscribe_to_map(self) -> None:
        """Subscribe to occupancy grid map."""
        if not self.node:
            return

        def on_map(msg: OccupancyGrid):
            self.warehouse_map = msg

        self.map_sub = self.node.create_subscription(OccupancyGrid, '/map', on_map, 1)

    def subscribe_to_robot(self, robot_id: str) -> bool:
        """Subscribe to a specific robot's odometry."""
        if not self.ros_initialized or not self.node:
            return False

        try:
            # Subscribe to odometry
            def on_odom(msg: Odometry, rid=robot_id):
                self._handle_odom(rid, msg)

            odom_sub = self.node.create_subscription(
                Odometry, f'/{robot_id}/odom', on_odom, 10
            )
            self.odom_subs[robot_id] = odom_sub

            # Create goal publisher
            goal_pub = self.node.create_publisher(PoseStamped, f'/{robot_id}/goal_pose', 10)
            self.goal_pubs[robot_id] = goal_pub

            # Initialize navigation state tracking
            self.nav_active[robot_id] = False

            # Create robot state if not exists
            if robot_id not in self.robots:
                self.robots[robot_id] = RobotState(
                    id=robot_id,
                    namespace=f'/{robot_id}',
                    pose=Pose(0.0, 0.0, 0.0),
                    velocity=Velocity(),
                    status=RobotStatus.IDLE,
                    coordination_status=CoordinationStatus.ACTIVE,
                )
                if self.on_robot_added:
                    self.on_robot_added(robot_id)
                logger.info(f"Subscribed to robot {robot_id}")

            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to robot {robot_id}: {e}")
            return False

    def unsubscribe_from_robot(self, robot_id: str) -> None:
        """Unsubscribe from a robot."""
        if robot_id in self.odom_subs:
            self.node.destroy_subscription(self.odom_subs[robot_id])
            del self.odom_subs[robot_id]

        if robot_id in self.goal_pubs:
            self.node.destroy_publisher(self.goal_pubs[robot_id])
            del self.goal_pubs[robot_id]

        if robot_id in self.robots:
            del self.robots[robot_id]
            if self.on_robot_removed:
                self.on_robot_removed(robot_id)
            logger.info(f"Unsubscribed from robot {robot_id}")

    def _handle_odom(self, robot_id: str, msg: Odometry) -> None:
        """Handle odometry update from a robot."""
        try:
            # Extract pose
            pos = msg.pose.pose.position
            quat = msg.pose.pose.orientation

            # Convert quaternion to yaw
            import math
            theta = math.atan2(
                2.0 * (quat.w * quat.z + quat.x * quat.y),
                1.0 - 2.0 * (quat.y * quat.y + quat.z * quat.z)
            )

            # Extract velocity
            vel = msg.twist.twist

            # Update robot state
            if robot_id not in self.robots:
                self.subscribe_to_robot(robot_id)

            robot = self.robots[robot_id]
            robot.pose = Pose(pos.x, pos.y, theta)
            robot.velocity = Velocity(vel.linear.x, vel.linear.y, vel.angular.z)
            robot.last_update_time = time.time()
            robot.is_online = True

            if self.on_robot_state_changed:
                self.on_robot_state_changed(robot_id, robot)

        except Exception as e:
            logger.error(f"Error handling odometry for {robot_id}: {e}")

    async def send_goal(self, robot_id: str, x: float, y: float) -> bool:
        """Send a goal to a robot (safe, via goal_pose topic).

        This is the safe pattern that preserves SWA-11 fix:
        - Publishes to goal_pose topic (CoordAgent listens)
        - Does not bypass coordination architecture
        - CoordAgent's _nav_active guard prevents concurrent dispatch
        """
        if not self.ros_initialized or not self.node:
            logger.warning(f"Cannot send goal to {robot_id}: ROS not initialized")
            return False

        if robot_id not in self.goal_pubs:
            logger.warning(f"Robot {robot_id} not subscribed, subscribing now")
            self.subscribe_to_robot(robot_id)

        try:
            # Create goal message
            goal_msg = PoseStamped()
            goal_msg.header.frame_id = "map"
            if self.node:
                goal_msg.header.stamp = self.node.get_clock().now().to_msg()
            goal_msg.pose.position.x = x
            goal_msg.pose.position.y = y
            goal_msg.pose.orientation.w = 1.0  # Identity rotation

            # Publish (this is safe - CoordAgent handles dispatch safety)
            pub = self.goal_pubs[robot_id]
            pub.publish(goal_msg)

            logger.info(f"Goal sent to {robot_id}: ({x:.2f}, {y:.2f})")
            return True

        except Exception as e:
            logger.error(f"Failed to send goal to {robot_id}: {e}")
            return False

    def get_simulation_status(self) -> SimulationStatus:
        """Get current simulation status."""
        sim_running = self.sim_started and len(self.robots) > 0

        navigating = sum(
            1 for r in self.robots.values()
            if r.status in [RobotStatus.NAVIGATING, RobotStatus.REROUTING]
        )

        return SimulationStatus(
            status="running" if sim_running else "stopped",
            sim_time=self.sim_time,
            wall_time=datetime.now(),
            num_active_robots=len([r for r in self.robots.values() if r.is_online]),
            num_navigating_robots=navigating,
            num_completed_goals=0,  # Tracked by coordinator in Phase 2+
        )

    def load_warehouse_graph(self, graph_yaml_path: Optional[str] = None) -> Optional[WarehouseGraph]:
        """Load warehouse topology graph from YAML."""
        if graph_yaml_path is None:
            # Try default locations
            candidates = [
                Path("/workspace/install/swarm_coordination_agent/share/swarm_coordination_agent/config/warehouse_graph.yaml"),
                Path("ros2_ws/src/swarm_coordination_agent/config/warehouse_graph.yaml"),
                Path("/opt/ros_ws/src/swarm_coordination_agent/config/warehouse_graph.yaml"),
            ]
            graph_yaml_path = next((p for p in candidates if p.exists()), None)

        if not graph_yaml_path or not Path(graph_yaml_path).exists():
            logger.warning(f"Warehouse graph YAML not found at {graph_yaml_path}")
            return None

        try:
            with open(graph_yaml_path) as f:
                data = yaml.safe_load(f)

            nodes = [
                WarehouseNode(id=n['id'], x=n['x'], y=n['y'])
                for n in data.get('nodes', [])
            ]
            edges = [
                WarehouseEdge(
                    from_node=e['from'],
                    to_node=e['to'],
                    segment_id=e['segment_id']
                )
                for e in data.get('edges', [])
            ]

            self.warehouse_graph = WarehouseGraph(nodes=nodes, edges=edges)
            logger.info(f"Loaded warehouse graph: {len(nodes)} nodes, {len(edges)} edges")
            return self.warehouse_graph

        except Exception as e:
            logger.error(f"Failed to load warehouse graph: {e}")
            return None

    def load_scenario(self, scenario_name: str) -> Optional[Scenario]:
        """Load scenario configuration from YAML."""
        candidates = [
            Path(f"/workspace/install/warehouse_sim/share/warehouse_sim/config/scenarios/{scenario_name}.yaml"),
            Path(f"warehouse_sim/config/scenarios/{scenario_name}.yaml"),
            Path(f"/opt/ros_ws/src/warehouse_sim/config/scenarios/{scenario_name}.yaml"),
        ]

        scenario_path = next((p for p in candidates if p.exists()), None)
        if not scenario_path:
            logger.warning(f"Scenario {scenario_name} not found")
            return None

        try:
            with open(scenario_path) as f:
                data = yaml.safe_load(f)

            return Scenario(
                name=data.get('name', scenario_name),
                description=data.get('description', ''),
                robots=data.get('robots', []),
                obstacles=data.get('obstacles', []),
                events=data.get('events', []),
            )
        except Exception as e:
            logger.error(f"Failed to load scenario {scenario_name}: {e}")
            return None

    async def spin_once(self) -> None:
        """Process one batch of ROS messages (non-blocking)."""
        if self.ros_initialized and self.node:
            try:
                rclpy.spin_once(self.node, timeout_sec=0.001)
            except Exception as e:
                logger.debug(f"Error in ROS spin: {e}")

    def shutdown(self) -> None:
        """Clean up ROS 2 resources."""
        if self.ros_initialized and self.node:
            self.node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
            logger.info("ROS 2 bridge shutdown complete")
