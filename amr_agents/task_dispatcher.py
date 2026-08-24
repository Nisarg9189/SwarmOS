#!/usr/bin/env python3
"""
Task Dispatcher
Central coordinator that dispatches tasks to agents and tracks progress.
"""

import argparse
import json
import logging
import sys
import time
import uuid
from typing import Dict, Optional
import threading

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
logger = logging.getLogger('task_dispatcher')


class TaskDispatcher:
    """Central task dispatcher for SwarmOS."""

    def __init__(self, zenoh_endpoint: str):
        self.zenoh_endpoint = zenoh_endpoint
        self.running = True

        # Task tracking
        self.tasks: Dict[str, dict] = {}
        self.task_claims: Dict[str, str] = {}  # task_id -> agent_id
        self.task_completions: Dict[str, float] = {}  # task_id -> completion_time_ms

        # Zenoh setup
        try:
            # Create a Config object for Zenoh connection
            # Use environment variables ZENOH_CONNECT_ENDPOINTS if available
            import os

            # Create config with Connect parameter
            conf = zenoh.Config()
            connect_endpoints = os.getenv('ZENOH_CONNECT_ENDPOINTS', zenoh_endpoint)
            if connect_endpoints:
                conf.insert_json5(f"connect/endpoints = ['{connect_endpoints}']")
            self.zenoh_session = zenoh.open(conf)

            logger.info(f"Connected to Zenoh")
        except Exception as e:
            logger.error(f"Failed to connect to Zenoh: {e}")
            raise RuntimeError(f"Zenoh connection failed: {e}")

        # Zenoh publishers
        self.task_events_pub = self.zenoh_session.declare_publisher(
            '/swarm/task/events'
        )

        # Zenoh subscribers
        self.task_status_sub = self.zenoh_session.declare_subscriber(
            '/swarm/agent/+/task_status'
        )

        logger.info("Task Dispatcher initialized")

    def dispatch_task(self, goal_x: float, goal_y: float, priority: int = 10, deadline_ms: int = 30000) -> str:
        """Dispatch a new task to the swarm."""
        task_id = f"task_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

        task = {
            'task_id': task_id,
            'goal': {'x': goal_x, 'y': goal_y},
            'priority': priority,
            'deadline_ms': deadline_ms,
            'created_ms': int(time.time() * 1000),
        }

        self.tasks[task_id] = task

        # Publish task event
        try:
            payload = {
                'timestamp_ms': int(time.time() * 1000),
                'event': 'task_dispatched',
                'task_id': task_id,
                'task': task,
            }
            self.task_events_pub.put(json.dumps(payload))
            logger.info(f"Dispatched task {task_id} to ({goal_x}, {goal_y})")
        except Exception as e:
            logger.error(f"Failed to dispatch task: {e}")

        return task_id

    def _handle_task_status(self, sample) -> None:
        """Handle task status updates from agents."""
        try:
            payload = json.loads(sample.payload.to_string())
            task_id = payload.get('task_id')
            agent_id = payload.get('agent_id')
            status = payload.get('status')

            if status == 'claimed':
                self.task_claims[task_id] = agent_id
                logger.info(f"Task {task_id} claimed by {agent_id}")

            elif status == 'completed':
                completion_time = payload.get('duration_ms', 0)
                self.task_completions[task_id] = completion_time
                logger.info(f"Task {task_id} completed by {agent_id} in {completion_time}ms")

            elif status == 'failed':
                reason = payload.get('reason', 'unknown')
                logger.warning(f"Task {task_id} failed: {reason}")
                # Could re-dispatch to another agent here
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Failed to parse task status: {e}")

    def run(self) -> None:
        """Main dispatcher loop."""
        logger.info("Starting task dispatcher")

        # Dispatch some sample tasks periodically
        task_counter = 0
        last_dispatch_time = time.time()

        while self.running:
            try:
                # Process task status updates
                try:
                    for sample in self.task_status_sub.try_recv():
                        self._handle_task_status(sample)
                except Exception:
                    pass

                # Dispatch new tasks periodically (every 10 seconds for demo)
                current_time = time.time()
                if current_time - last_dispatch_time > 10:
                    # Generate random task within warehouse bounds
                    goal_x = -15 + (task_counter % 30)
                    goal_y = -15 + ((task_counter // 3) % 30)
                    self.dispatch_task(goal_x, goal_y)
                    task_counter += 1
                    last_dispatch_time = current_time

                time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Dispatcher loop error: {e}")
                time.sleep(1)

    def shutdown(self) -> None:
        """Gracefully shut down the dispatcher."""
        logger.info("Shutting down task dispatcher")
        self.running = False
        try:
            self.zenoh_session.close()
        except Exception as e:
            logger.error(f"Zenoh close error: {e}")


def main():
    parser = argparse.ArgumentParser(description='SwarmOS Task Dispatcher')
    parser.add_argument(
        '--zenoh_endpoint',
        type=str,
        default='tcp/127.0.0.1:7447',
        help='Zenoh endpoint (e.g., tcp/zenoh-router:7447)'
    )

    args = parser.parse_args()

    dispatcher = TaskDispatcher(args.zenoh_endpoint)

    try:
        dispatcher.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        dispatcher.shutdown()


if __name__ == '__main__':
    main()
