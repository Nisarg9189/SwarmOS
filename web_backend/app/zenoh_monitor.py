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

    def __init__(self, warehouse_id: str = "wh1"):
        """Initialize Zenoh monitor."""
        if not ZENOH_AVAILABLE:
            logger.warning("Zenoh not available - coordination monitoring disabled")
            self.initialized = False
            return

        self.warehouse_id = warehouse_id
        self.session = None
        self.subscriptions: Dict[str, Any] = {}
        self.initialized = False

        # Cached state
        self.robot_state: Dict[str, Dict[str, Any]] = {}  # robot_id -> latest state msg
        self.robot_intent: Dict[str, Dict[str, Any]] = {}  # robot_id -> latest intent msg
        self.robot_task: Dict[str, Dict[str, Any]] = {}  # robot_id -> latest task msg

        # Callbacks
        self.on_state_updated: Optional[Callable] = None
        self.on_intent_updated: Optional[Callable] = None
        self.on_coordination_event: Optional[Callable] = None

    def connect(self) -> bool:
        """Connect to Zenoh router."""
        if not ZENOH_AVAILABLE:
            logger.warning("Cannot connect to Zenoh: not installed")
            return False

        try:
            conf = zenoh.Config()
            # Use default config which connects to local router on localhost:7447
            self.session = zenoh.open(conf)
            self.initialized = True
            logger.info("Connected to Zenoh router")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zenoh: {e}")
            self.initialized = False
            return False

    def subscribe_to_robots(self, robot_ids: List[str]) -> None:
        """Subscribe to state/intent for a set of robots."""
        if not self.initialized or not self.session:
            logger.warning("Zenoh not initialized")
            return

        for robot_id in robot_ids:
            self._subscribe_to_robot_state(robot_id)
            self._subscribe_to_robot_intent(robot_id)
            self._subscribe_to_robot_task(robot_id)
            self._subscribe_to_robot_negotiate(robot_id)

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

        # Update from StateMsg
        status_str = msg.get("status", "ACTIVE")
        if status_str == "ACTIVE":
            robot_state.coordination_status = CoordinationStatus.ACTIVE
        elif status_str == "YIELDING":
            robot_state.coordination_status = CoordinationStatus.YIELDING
        elif status_str == "HOLDING":
            robot_state.coordination_status = CoordinationStatus.HOLDING
        elif status_str == "FAILED":
            robot_state.coordination_status = CoordinationStatus.FAILED

        robot_state.blocked_by = msg.get("blocked_by")

        # Update from IntentMsg if available
        if robot_id in self.robot_intent:
            intent = self.robot_intent[robot_id]
            path_data = intent.get("path", [])

            # Convert path to Waypoint objects
            robot_state.planned_route = [
                Waypoint(
                    x=wp["x"],
                    y=wp["y"],
                    eta=wp["eta"],
                    etd=wp["etd"],
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
