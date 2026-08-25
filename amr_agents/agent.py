#!/usr/bin/env python3
"""
SwarmOS Coordination Agent
Handles decentralized multi-robot coordination, collision avoidance, and task assignment.
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
import threading
import numpy as np

# ROS 2
import rclpy
from rclpy.node import Node
from rclpy.clock import ROSClock
from geometry_msgs.msg import PoseStamped, TwistStamped, Twist
from tf2_ros import TransformListener, Buffer, TransformException
from std_msgs.msg import Header
from nav_msgs.msg import OccupancyGrid

# Zenoh
try:
    import zenoh
except ImportError:
    print("ERROR: eclipse-zenoh not installed. Run: pip install eclipse-zenoh")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger('agent')


@dataclass
class SensorData:
    """Current sensor readings and peer states."""
    timestamp_ms: int
    position: np.ndarray  # [x, y, theta]
    velocity: np.ndarray  # [vx, vy, omega]
    goal: Optional[np.ndarray]  # [x, y]
    obstacles: List[np.ndarray]  # List of [x, y, radius]
    battery_pct: float
    peer_states: Dict[str, dict]  # {agent_id: {pos, vel, intent, ...}}
    task_id: Optional[str] = None


@dataclass
class Plan:
    """Next action plan."""
    next_waypoint: np.ndarray  # [x, y]
    desired_velocity: np.ndarray  # [vx, vy]
    priority: int  # 0-100
    reason: str
    task_id: Optional[str]
    confidence: float  # 0.0-1.0


class CoordinationAgent(Node):
    """Main coordination agent for a single AMR."""

    def __init__(self, robot_id: str, zenoh_endpoint: str):
        super().__init__(f'agent_{robot_id}')

        self.robot_id = robot_id
        self.zenoh_endpoint = zenoh_endpoint
        self.running = True
        self.current_plan: Optional[Plan] = None
        self.blocked_since_ms: Optional[int] = None
        self.peer_states: Dict[str, dict] = {}
        self.last_position: Optional[np.ndarray] = None
        self.active_goal: Optional[np.ndarray] = None
        self.active_task_id: Optional[str] = None

        # ROS 2 setup
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.goal_pub = self.create_publisher(
            PoseStamped,
            f'/{robot_id}/goal_pose',
            10
        )
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            f'/{robot_id}/cmd_vel',
            10
        )

        # Zenoh setup
        try:
            # Create a Config object for Zenoh connection
            # Use environment variables ZENOH_CONNECT_ENDPOINTS if available
            import os

            # Create config with Connect parameter
            connect_endpoints = os.getenv('ZENOH_CONNECT_ENDPOINTS', zenoh_endpoint)
            if connect_endpoints:
                conf = zenoh.Config.from_json5(f"{{ connect: {{ endpoints: ['{connect_endpoints}'] }} }}")
            else:
                conf = zenoh.Config()
            self.zenoh_session = zenoh.open(conf)

            logger.info(f"Connected to Zenoh")
        except Exception as e:
            logger.error(f"Failed to connect to Zenoh: {e}")
            raise RuntimeError(f"Zenoh connection failed: {e}")

        # Zenoh subscribers
        self.peer_status_sub = self.zenoh_session.declare_subscriber(
            f'swarm/agent/+/status'
        )
        self.peer_intent_sub = self.zenoh_session.declare_subscriber(
            f'swarm/agent/+/intent'
        )
        self.task_events_sub = self.zenoh_session.declare_subscriber(
            f'swarm/task/events'
        )

        # Zenoh publishers
        self.status_pub = self.zenoh_session.declare_publisher(
            f'swarm/agent/{robot_id}/status'
        )
        self.intent_pub = self.zenoh_session.declare_publisher(
            f'swarm/agent/{robot_id}/intent'
        )
        self.task_status_pub = self.zenoh_session.declare_publisher(
            f'swarm/agent/{robot_id}/task_status'
        )

        logger.info(f"Agent {robot_id} initialized")

    def sense(self) -> SensorData:
        """Read current state from ROS 2 topics and Zenoh subscriptions."""
        timestamp_ms = int(time.time() * 1000)

        # Read own position from TF
        try:
            tf = self.tf_buffer.lookup_transform(
                'map',
                f'{self.robot_id}/base_link',
                rclpy.time.Time()
            )
            x = tf.transform.translation.x
            y = tf.transform.translation.y
            # Simple theta extraction from quaternion (simplified)
            q = tf.transform.rotation
            theta = np.arctan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
            position = np.array([x, y, theta])
        except (TransformException, AttributeError):
            position = np.array([0.0, 0.0, 0.0])

        # Default values
        velocity = np.array([0.0, 0.0, 0.0])
        goal = self.active_goal  # keep working toward the currently-claimed task, if any
        obstacles = []
        battery_pct = 100.0

        # Read peer states from Zenoh (non-blocking poll)
        try:
            for sample in self.peer_status_sub.try_recv():
                try:
                    payload = json.loads(sample.payload.to_string())
                    agent_id = payload.get('agent_id')
                    if agent_id and agent_id != self.robot_id:
                        self.peer_states[agent_id] = {
                            'position': payload.get('position'),
                            'velocity': payload.get('velocity'),
                            'goal': payload.get('goal'),
                            'state': payload.get('state'),
                            'timestamp_ms': payload.get('timestamp_ms', timestamp_ms),
                        }
                except (json.JSONDecodeError, KeyError):
                    pass
        except Exception:
            pass

        # Read peer intents
        try:
            for sample in self.peer_intent_sub.try_recv():
                try:
                    payload = json.loads(sample.payload.to_string())
                    agent_id = payload.get('agent_id')
                    if agent_id in self.peer_states:
                        self.peer_states[agent_id]['intent'] = payload.get('next_waypoint')
                        self.peer_states[agent_id]['priority'] = payload.get('priority', 50)
                except (json.JSONDecodeError, KeyError):
                    pass
        except Exception:
            pass

        # Read task events (non-blocking)
        try:
            for sample in self.task_events_sub.try_recv():
                try:
                    payload = json.loads(sample.payload.to_string())
                    if payload.get('event') == 'task_dispatched':
                        task_id = payload.get('task_id')
                        task = payload.get('task', {})
                        if self._can_claim_task(task):
                            goal = np.array([
                                task.get('goal', {}).get('x', 0),
                                task.get('goal', {}).get('y', 0)
                            ])
                            self.active_goal = goal
                            self.active_task_id = task_id
                            try:
                                self.task_status_pub.put(json.dumps({
                                    'agent_id': self.robot_id,
                                    'task_id': task_id,
                                    'status': 'claimed',
                                }))
                            except Exception:
                                pass
                except (json.JSONDecodeError, KeyError):
                    pass
        except Exception:
            pass

        return SensorData(
            timestamp_ms=timestamp_ms,
            position=position,
            velocity=velocity,
            goal=goal,
            obstacles=obstacles,
            battery_pct=battery_pct,
            peer_states=self.peer_states,
            task_id=self.active_task_id
        )

    def plan(self, sensor_data: SensorData) -> Plan:
        """Compute next waypoint given sensed state."""
        priority = 50  # Default priority
        reason = "idle"
        confidence = 0.9
        next_waypoint = sensor_data.position[:2].copy()
        desired_velocity = np.array([0.0, 0.0])

        # If we have a goal, plan towards it
        if sensor_data.goal is not None:
            direction = sensor_data.goal - sensor_data.position[:2]
            distance = np.linalg.norm(direction)

            if distance > 0.25:  # Not at goal yet
                # Normalize direction and scale by max speed
                direction_norm = direction / distance if distance > 0 else np.array([0, 0])
                next_waypoint = sensor_data.position[:2] + direction_norm * 0.5
                desired_velocity = direction_norm * 0.5
                reason = "moving_to_task"
            else:
                reason = "goal_reached"
                if self.active_task_id is not None:
                    try:
                        self.task_status_pub.put(json.dumps({
                            'agent_id': self.robot_id,
                            'task_id': self.active_task_id,
                            'status': 'completed',
                            'duration_ms': int(time.time() * 1000) - sensor_data.timestamp_ms,
                        }))
                    except Exception:
                        pass
                self.active_goal = None
                self.active_task_id = None

        # Check for deadlock
        if self.is_blocked(sensor_data):
            priority = 10  # Yield priority if blocked
            reason = "blocked_recovering"

        # Deadlock resolution: check collision with peers
        for peer_id, peer_state in sensor_data.peer_states.items():
            if 'position' not in peer_state:
                continue

            peer_pos = np.array([
                peer_state['position'].get('x', 0),
                peer_state['position'].get('y', 0)
            ])
            distance = np.linalg.norm(sensor_data.position[:2] - peer_pos)

            # If collision likely (within 1 meter)
            if distance < 1.0 and distance > 0:
                peer_priority = peer_state.get('priority', 50)

                # Tiebreaker: agent with lower ID yields
                if self.robot_id < peer_id:
                    # We have priority, increase it
                    priority = max(priority, 80)
                else:
                    # Peer has priority, decrease ours
                    priority = min(priority, 20)
                    reason = "yielding"

        return Plan(
            next_waypoint=next_waypoint,
            desired_velocity=desired_velocity,
            priority=priority,
            reason=reason,
            task_id=sensor_data.task_id,
            confidence=confidence
        )

    def execute(self, plan: Plan) -> bool:
        """Command Nav2 to move to next waypoint."""
        try:
            # Publish goal to Nav2
            goal_pose = PoseStamped()
            goal_pose.header.frame_id = 'map'
            goal_pose.header.stamp = self.get_clock().now().to_msg()
            goal_pose.pose.position.x = float(plan.next_waypoint[0])
            goal_pose.pose.position.y = float(plan.next_waypoint[1])
            goal_pose.pose.position.z = 0.0
            goal_pose.pose.orientation.w = 1.0

            self.goal_pub.publish(goal_pose)
            logger.debug(f"Published goal: {plan.next_waypoint}")
            return True
        except Exception as e:
            logger.error(f"Failed to execute plan: {e}")
            return False

    def publish_state(self, sensor_data: SensorData) -> None:
        """Publish own status to Zenoh."""
        try:
            payload = {
                'agent_id': self.robot_id,
                'timestamp_ms': sensor_data.timestamp_ms,
                'position': {
                    'x': float(sensor_data.position[0]),
                    'y': float(sensor_data.position[1]),
                    'theta': float(sensor_data.position[2]),
                },
                'velocity': {
                    'vx': float(sensor_data.velocity[0]),
                    'vy': float(sensor_data.velocity[1]),
                    'omega': float(sensor_data.velocity[2]),
                },
                'battery_pct': float(sensor_data.battery_pct),
                'max_speed_ms': 0.5,
            }

            if sensor_data.goal is not None:
                payload['goal'] = {
                    'x': float(sensor_data.goal[0]),
                    'y': float(sensor_data.goal[1]),
                }
                payload['state'] = 'moving'
            else:
                payload['state'] = 'idle'

            self.status_pub.put(json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to publish state: {e}")

    def publish_intent(self, plan: Plan) -> None:
        """Publish movement intent to Zenoh."""
        try:
            payload = {
                'agent_id': self.robot_id,
                'timestamp_ms': int(time.time() * 1000),
                'next_waypoint': {
                    'x': float(plan.next_waypoint[0]),
                    'y': float(plan.next_waypoint[1]),
                },
                'desired_velocity': {
                    'vx': float(plan.desired_velocity[0]),
                    'vy': float(plan.desired_velocity[1]),
                },
                'priority': int(plan.priority),
                'reason': plan.reason,
                'confidence': float(plan.confidence),
            }

            if plan.task_id:
                payload['task_id'] = plan.task_id

            self.intent_pub.put(json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to publish intent: {e}")

    def is_blocked(self, sensor_data: SensorData) -> bool:
        """Check if agent is stationary despite having a goal."""
        if sensor_data.goal is None:
            self.blocked_since_ms = None
            return False

        if self.last_position is not None:
            distance = np.linalg.norm(sensor_data.position[:2] - self.last_position)
            if distance < 0.1:  # Less than 10cm movement
                if self.blocked_since_ms is None:
                    self.blocked_since_ms = sensor_data.timestamp_ms
                else:
                    blocked_duration = sensor_data.timestamp_ms - self.blocked_since_ms
                    if blocked_duration > 5000:  # 5 seconds
                        return True
            else:
                self.blocked_since_ms = None

        self.last_position = sensor_data.position[:2].copy()
        return False

    def _can_claim_task(self, task: dict) -> bool:
        """Decide whether to claim a task."""
        if self.active_task_id is not None:
            return False
        target_robot = task.get('robot_id')
        if target_robot is not None:
            return target_robot == self.robot_id
        return True

    def run_control_loop(self) -> None:
        """Main control loop running in main thread."""
        logger.info(f"Control loop started for {self.robot_id}")
        loop_rate_hz = 20
        loop_period_s = 1.0 / loop_rate_hz
        last_iteration_time = time.time()
        iteration_count = 0

        try:
            while self.running and rclpy.ok():
                try:
                    logger.debug(f"Starting iteration {iteration_count}")
                    sensor_data = self.sense()
                    logger.debug(f"Sensed data: pos={sensor_data.position}")
                    plan = self.plan(sensor_data)
                    self.current_plan = plan

                    self.execute(plan)
                    self.publish_state(sensor_data)
                    self.publish_intent(plan)

                    iteration_count += 1
                    if iteration_count % 20 == 0:
                        logger.info(f"Control loop iteration {iteration_count} for {self.robot_id}")

                    # Rate limiting using wall-clock time (avoids ROS 2 clock issues)
                    elapsed = time.time() - last_iteration_time
                    sleep_time = max(0, loop_period_s - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    last_iteration_time = time.time()
                except Exception as e:
                    logger.error(f"Control loop error: {e}", exc_info=True)
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Control loop fatal error: {e}", exc_info=True)

    def start(self) -> None:
        """Start the agent's control loop (runs synchronously in current thread)."""
        logger.info(f"Starting agent {self.robot_id}")
        self.run_control_loop()

    def shutdown(self) -> None:
        """Gracefully shut down the agent."""
        logger.info(f"Shutting down agent {self.robot_id}")
        self.running = False

        try:
            self.zenoh_session.close()
        except Exception as e:
            logger.error(f"Zenoh close error: {e}")


def main():
    parser = argparse.ArgumentParser(description='SwarmOS Coordination Agent')
    parser.add_argument(
        '--robot_id',
        type=str,
        default='amr_0',
        help='Robot ID (e.g., amr_0, amr_1)'
    )
    parser.add_argument(
        '--zenoh_endpoint',
        type=str,
        default='tcp/127.0.0.1:7447',
        help='Zenoh endpoint (e.g., tcp/zenoh-router:7447)'
    )

    args = parser.parse_args()

    # Initialize ROS 2
    rclpy.init(args=sys.argv[1:])

    # Create and start agent
    try:
        agent = CoordinationAgent(args.robot_id, args.zenoh_endpoint)
        agent.start()

        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if 'agent' in locals():
            agent.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
