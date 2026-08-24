"""Zenoh coordination protocol monitor."""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, List, Callable, Any
from dataclasses import asdict

try:
    import zenoh
    ZENOH_AVAILABLE = True
except ImportError:
    ZENOH_AVAILABLE = False

from .models import (
    Waypoint, CoordinationStatus, RobotState, CoordinationEvent
)

logger = logging.getLogger(__name__)


class ZenohMonitor:
    """Monitor Zenoh coordination protocol topics."""

    def __init__(self, warehouse_id: str = "wh1", zenoh_endpoint: str = "tcp/127.0.0.1:7447"):
        """Initialize Zenoh monitor.

        Args:
            warehouse_id: Warehouse identifier for topic scoping
            zenoh_endpoint: Zenoh router endpoint (default: tcp/127.0.0.1:7447 for host connection)
        """
        self.warehouse_id = warehouse_id
        self.zenoh_endpoint = zenoh_endpoint
        self.session = None
        self.subscriptions: Dict[str, Any] = {}
        self.initialized = False
        self.discovered_robots: set = set()  # Track discovered robot IDs

        # Cached state (always initialize these)
        self.robot_state: Dict[str, Dict[str, Any]] = {}  # robot_id -> latest state msg
        self.robot_intent: Dict[str, Dict[str, Any]] = {}  # robot_id -> latest intent msg
        self.robot_task: Dict[str, Dict[str, Any]] = {}  # robot_id -> latest task msg

        # Callbacks
        self.on_state_updated: Optional[Callable] = None
        self.on_intent_updated: Optional[Callable] = None
        self.on_coordination_event: Optional[Callable] = None
        self.on_robot_discovered: Optional[Callable] = None  # Called when a robot is discovered

        if not ZENOH_AVAILABLE:
            logger.warning("Zenoh not available - coordination monitoring disabled")
            return

    def connect(self) -> bool:
        """Connect to Zenoh router."""
        if not ZENOH_AVAILABLE:
            logger.warning("Cannot connect to Zenoh: not installed")
            return False

        try:
            # Create config with explicit endpoint (supports both localhost and remote endpoints)
            conf = zenoh.Config.from_json5(f"{{ connect: {{ endpoints: ['{self.zenoh_endpoint}'] }} }}")
            self.session = zenoh.open(conf)
            self.initialized = True
            logger.info(f"Connected to Zenoh router at {self.zenoh_endpoint}")

            # Auto-discover robots by subscribing to agent status wildcard
            self._subscribe_to_agent_discovery()

            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zenoh at {self.zenoh_endpoint}: {e}")
            self.initialized = False
            return False

    def _subscribe_to_agent_discovery(self) -> None:
        """Subscribe to agent status messages to discover robots."""
        if not self.initialized or not self.session:
            return

        try:
            key = "swarm/agent/+/status"

            def on_agent_status(sample):
                try:
                    # Extract robot_id from topic path: swarm/agent/{robot_id}/status
                    parts = sample.key_expr.split('/')
                    if len(parts) >= 3:
                        robot_id = parts[2]  # parts: ['swarm', 'agent', 'amr_0', 'status']

                        # Parse message
                        msg = json.loads(sample.payload.to_bytes().decode('utf-8'))

                        # Store state
                        self.robot_state[robot_id] = msg

                        # Notify about discovery if new
                        if robot_id not in self.discovered_robots:
                            self.discovered_robots.add(robot_id)
                            if self.on_robot_discovered:
                                self.on_robot_discovered(robot_id)
                            logger.info(f"Discovered robot: {robot_id}")

                        # Emit state update callback
                        if self.on_state_updated:
                            self.on_state_updated(robot_id, msg)

                except Exception as e:
                    logger.debug(f"Error parsing agent status message: {e}")

            sub = self.session.declare_subscriber(key, on_agent_status)
            self.subscriptions["agent_discovery"] = sub
            logger.info(f"Subscribed to agent discovery: {key}")

        except Exception as e:
            logger.error(f"Failed to subscribe to agent discovery: {e}")

    def subscribe_to_robots(self, robot_ids: List[str]) -> None:
        """Subscribe to state/intent for a set of robots."""
        if not self.initialized or not self.session:
            logger.warning("Zenoh not initialized")
            return

        for robot_id in robot_ids:
            # Subscribe to agent-published topics (new pattern)
            self._subscribe_to_agent_intent(robot_id)
            self._subscribe_to_agent_task(robot_id)

            # Also subscribe to legacy warehouse coordinator topics if they exist
            self._subscribe_to_robot_state(robot_id)
            self._subscribe_to_robot_negotiate(robot_id)

    def _subscribe_to_agent_intent(self, robot_id: str) -> None:
        """Subscribe to a robot's intent (planned route) via agent topic."""
        if not self.initialized or not self.session:
            return

        try:
            # Subscribe to agent's intent topic (swarm/agent/{robot_id}/intent)
            key = f"swarm/agent/{robot_id}/intent"

            def on_intent(sample):
                try:
                    msg = json.loads(sample.payload.to_bytes().decode('utf-8'))
                    self.robot_intent[robot_id] = msg

                    if self.on_intent_updated:
                        self.on_intent_updated(robot_id, msg)

                    # Emit coordination event
                    if self.on_coordination_event:
                        event = CoordinationEvent(
                            timestamp=time.time(),
                            robot_id=robot_id,
                            event_type="route_updated",
                            details={
                                "path_length": len(msg.get("path", [])) if isinstance(msg.get("path"), list) else 0,
                                "next_waypoint": msg.get("next_waypoint"),
                            }
                        )
                        self.on_coordination_event(event)

                except Exception as e:
                    logger.debug(f"Error parsing agent intent message from {robot_id}: {e}")

            sub = self.session.declare_subscriber(key, on_intent)
            self.subscriptions[f"{robot_id}/agent_intent"] = sub
            logger.debug(f"Subscribed to agent intent: {key}")

        except Exception as e:
            logger.error(f"Failed to subscribe to agent intent for {robot_id}: {e}")

    def _subscribe_to_agent_task(self, robot_id: str) -> None:
        """Subscribe to a robot's task messages via agent topic."""
        if not self.initialized or not self.session:
            return

        try:
            key = f"swarm/agent/{robot_id}/task_status"

            def on_task(sample):
                try:
                    msg = json.loads(sample.payload.to_bytes().decode('utf-8'))
                    self.robot_task[robot_id] = msg

                except Exception as e:
                    logger.debug(f"Error parsing agent task message from {robot_id}: {e}")

            sub = self.session.declare_subscriber(key, on_task)
            self.subscriptions[f"{robot_id}/agent_task"] = sub
            logger.debug(f"Subscribed to agent task: {key}")

        except Exception as e:
            logger.error(f"Failed to subscribe to agent task for {robot_id}: {e}")

    def _subscribe_to_robot_state(self, robot_id: str) -> None:
        """Subscribe to a robot's state messages."""
        if not self.initialized or not self.session:
            return

        try:
            key = f"swarmos/{self.warehouse_id}/robot/{robot_id}/state"

            def on_state(sample):
                try:
                    msg = json.loads(sample.payload.to_bytes().decode('utf-8'))
                    self.robot_state[robot_id] = msg

                    if self.on_state_updated:
                        self.on_state_updated(robot_id, msg)

                except Exception as e:
                    logger.debug(f"Error parsing state message from {robot_id}: {e}")

            sub = self.session.declare_subscriber(key, on_state)
            self.subscriptions[f"{robot_id}/state"] = sub
            logger.debug(f"Subscribed to state: {key}")

        except Exception as e:
            logger.error(f"Failed to subscribe to state for {robot_id}: {e}")

    def _subscribe_to_robot_intent(self, robot_id: str) -> None:
        """Subscribe to a robot's intent (planned route)."""
        if not self.initialized or not self.session:
            return

        try:
            key = f"swarmos/{self.warehouse_id}/robot/{robot_id}/intent"

            def on_intent(sample):
                try:
                    msg = json.loads(sample.payload.to_bytes().decode('utf-8'))
                    self.robot_intent[robot_id] = msg

                    if self.on_intent_updated:
                        self.on_intent_updated(robot_id, msg)

                    # Emit coordination event
                    if self.on_coordination_event:
                        event = CoordinationEvent(
                            timestamp=time.time(),
                            robot_id=robot_id,
                            event_type="route_updated",
                            details={
                                "path_length": len(msg.get("path", [])),
                                "deadline": msg.get("deadline"),
                            }
                        )
                        self.on_coordination_event(event)

                except Exception as e:
                    logger.debug(f"Error parsing intent message from {robot_id}: {e}")

            sub = self.session.declare_subscriber(key, on_intent)
            self.subscriptions[f"{robot_id}/intent"] = sub
            logger.debug(f"Subscribed to intent: {key}")

        except Exception as e:
            logger.error(f"Failed to subscribe to intent for {robot_id}: {e}")

    def _subscribe_to_robot_task(self, robot_id: str) -> None:
        """Subscribe to a robot's task messages."""
        if not self.initialized or not self.session:
            return

        try:
            key = f"swarmos/{self.warehouse_id}/robot/{robot_id}/task"

            def on_task(sample):
                try:
                    msg = json.loads(sample.payload.to_bytes().decode('utf-8'))
                    self.robot_task[robot_id] = msg

                except Exception as e:
                    logger.debug(f"Error parsing task message from {robot_id}: {e}")

            sub = self.session.declare_subscriber(key, on_task)
            self.subscriptions[f"{robot_id}/task"] = sub
            logger.debug(f"Subscribed to task: {key}")

        except Exception as e:
            logger.error(f"Failed to subscribe to task for {robot_id}: {e}")

    def _subscribe_to_robot_negotiate(self, robot_id: str) -> None:
        """Subscribe to a robot's negotiation messages (conflict resolution)."""
        if not self.initialized or not self.session:
            return

        try:
            key = f"swarmos/{self.warehouse_id}/robot/{robot_id}/negotiate"

            def on_negotiate(sample):
                try:
                    msg = json.loads(sample.payload.to_bytes().decode('utf-8'))

                    if self.on_coordination_event:
                        kind = msg.get("kind", "?")
                        event = CoordinationEvent(
                            timestamp=time.time(),
                            robot_id=robot_id,
                            event_type=f"negotiation_{kind.lower()}",
                            details={
                                "kind": kind,
                                "segment": msg.get("segment"),
                            },
                            severity="info" if kind != "YIELD" else "warning"
                        )
                        self.on_coordination_event(event)

                except Exception as e:
                    logger.debug(f"Error parsing negotiate message from {robot_id}: {e}")

            sub = self.session.declare_subscriber(key, on_negotiate)
            self.subscriptions[f"{robot_id}/negotiate"] = sub
            logger.debug(f"Subscribed to negotiate: {key}")

        except Exception as e:
            logger.error(f"Failed to subscribe to negotiate for {robot_id}: {e}")

    def get_robot_intent(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest intent (planned route) for a robot."""
        return self.robot_intent.get(robot_id)

    def get_robot_state_msg(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest state message from Zenoh for a robot."""
        return self.robot_state.get(robot_id)

    def update_robot_from_zenoh(self, robot_id: str, robot_state: RobotState) -> None:
        """Update a RobotState with data from Zenoh messages."""
        if robot_id not in self.robot_state:
            return

        msg = self.robot_state[robot_id]

        # Update pose from position data
        position = msg.get("position", {})
        if isinstance(position, dict):
            robot_state.pose.x = float(position.get("x", 0.0))
            robot_state.pose.y = float(position.get("y", 0.0))
            robot_state.pose.theta = float(position.get("theta", 0.0))

        # Update velocity data
        velocity = msg.get("velocity", {})
        if isinstance(velocity, dict):
            robot_state.velocity.vx = float(velocity.get("vx", 0.0))
            robot_state.velocity.vy = float(velocity.get("vy", 0.0))
            robot_state.velocity.omega = float(velocity.get("omega", 0.0))

        # Update coordination status from state field
        status_str = msg.get("state", "idle").lower()
        robot_state.is_online = True

        # Update from intent msg for coordination status
        if robot_id in self.robot_intent:
            intent = msg.get("intent", {})
            priority = intent.get("priority", 50)
            # Use priority to infer coordination status
            if priority >= 80:
                robot_state.coordination_status = CoordinationStatus.ACTIVE
            elif priority <= 20:
                robot_state.coordination_status = CoordinationStatus.YIELDING
            else:
                robot_state.coordination_status = CoordinationStatus.ACTIVE

        robot_state.blocked_by = msg.get("blocked_by")

        # Update from IntentMsg if available
        if robot_id in self.robot_intent:
            intent = self.robot_intent[robot_id]
            path_data = intent.get("path", [])

            # Convert path to Waypoint objects if available
            if path_data and isinstance(path_data, list):
                robot_state.planned_route = [
                    Waypoint(
                        x=wp.get("x", 0),
                        y=wp.get("y", 0),
                        eta=wp.get("eta"),
                        etd=wp.get("etd"),
                        cell_id=wp.get("cell_id"),
                    )
                    for wp in path_data
                ]

    def unsubscribe_from_robot(self, robot_id: str) -> None:
        """Unsubscribe from a robot's topics."""
        for suffix in ["state", "intent", "task", "negotiate"]:
            key = f"{robot_id}/{suffix}"
            if key in self.subscriptions:
                try:
                    self.subscriptions[key].undeclare()
                    del self.subscriptions[key]
                    logger.debug(f"Unsubscribed from {key}")
                except Exception as e:
                    logger.debug(f"Error unsubscribing from {key}: {e}")

    def shutdown(self) -> None:
        """Clean up Zenoh resources."""
        for sub in self.subscriptions.values():
            try:
                sub.undeclare()
            except Exception:
                pass

        if self.session:
            try:
                self.session.close()
            except Exception:
                pass

        logger.info("Zenoh monitor shutdown complete")
