"""FastAPI backend for simulation control center."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Set, Optional

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .ros_bridge import RoSBridge
from .zenoh_monitor import ZenohMonitor
from .scenario_executor import ScenarioExecutor
from .models import (
    RobotState, SimulationStatus, Pose, Velocity, CoordinationEvent,
    NavigationEvent, SimulationEvent, Scenario, WarehouseGraph,
    RobotStatus, CoordinationStatus
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# Pydantic models for API requests
class GoalRequest(BaseModel):
    """Request to send a goal to a robot."""
    x: float
    y: float


class ScenarioStartRequest(BaseModel):
    """Request to start a scenario."""
    scenario_name: str


# Global state
ros_bridge = RoSBridge()
zenoh_monitor = ZenohMonitor()

# WebSocket connections
connected_clients: Set[WebSocket] = set()

# Event logging
event_log: List[Dict] = []
MAX_EVENT_LOG_SIZE = 1000

# Scenario execution
current_scenario_executor: Optional[ScenarioExecutor] = None


async def background_task_manager():
    """Background task to process ROS messages and emit events."""
    while True:
        try:
            # Process ROS messages (non-blocking)
            await ros_bridge.spin_once()

            # Update robot states with Zenoh data
            for robot_id, robot_state in ros_bridge.robots.items():
                zenoh_monitor.update_robot_from_zenoh(robot_id, robot_state)

            # Broadcast state updates to WebSocket clients
            for robot_id, robot_state in ros_bridge.robots.items():
                if connected_clients:
                    event = {
                        "type": "robot_state",
                        "robot_id": robot_id,
                        "data": {
                            "id": robot_state.id,
                            "pose": {"x": robot_state.pose.x, "y": robot_state.pose.y, "theta": robot_state.pose.theta},
                            "velocity": {"vx": robot_state.velocity.vx, "vy": robot_state.velocity.vy, "omega": robot_state.velocity.omega},
                            "status": robot_state.status.value,
                            "coordination_status": robot_state.coordination_status.value,
                            "blocked_by": robot_state.blocked_by,
                            "is_online": robot_state.is_online,
                        }
                    }
                    await broadcast_event(event)

            # Broadcast simulation status
            if connected_clients:
                status = ros_bridge.get_simulation_status()
                event = {
                    "type": "simulation_status",
                    "data": {
                        "status": status.status,
                        "sim_time": status.sim_time,
                        "num_active_robots": status.num_active_robots,
                        "num_navigating_robots": status.num_navigating_robots,
                    }
                }
                await broadcast_event(event)

            await asyncio.sleep(0.1)  # 10 Hz update rate

        except Exception as e:
            logger.error(f"Error in background task: {e}")
            await asyncio.sleep(1)


async def broadcast_event(event: Dict) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    dead_clients = set()

    for client in connected_clients:
        try:
            await client.send_json(event)
        except Exception as e:
            logger.debug(f"Error broadcasting to client: {e}")
            dead_clients.add(client)

    # Clean up dead connections
    for client in dead_clients:
        connected_clients.discard(client)


def ros_bridge_callbacks():
    """Set up ROS bridge callbacks."""

    def on_robot_state_changed(robot_id: str, state: RobotState):
        # Robot state updated - event will be broadcast by background task
        pass

    def on_sim_time_changed(sim_time: float):
        # Simulation time updated - event will be broadcast by background task
        pass

    def on_robot_added(robot_id: str):
        logger.info(f"Robot discovered: {robot_id}")
        # Subscribe to Zenoh topics for this robot
        zenoh_monitor.subscribe_to_robots([robot_id])

    def on_robot_removed(robot_id: str):
        logger.info(f"Robot removed: {robot_id}")
        zenoh_monitor.unsubscribe_from_robot(robot_id)

    ros_bridge.on_robot_state_changed = on_robot_state_changed
    ros_bridge.on_sim_time_changed = on_sim_time_changed
    ros_bridge.on_robot_added = on_robot_added
    ros_bridge.on_robot_removed = on_robot_removed


def zenoh_callbacks():
    """Set up Zenoh monitor callbacks."""

    def on_robot_discovered(robot_id: str):
        """Handle robot discovery from Zenoh."""
        # Create a RobotState for this robot if it doesn't exist
        if robot_id not in ros_bridge.robots:
            ros_bridge.robots[robot_id] = RobotState(
                id=robot_id,
                namespace=f'/{robot_id}',
                pose=Pose(0.0, 0.0, 0.0),
                velocity=Velocity(),
                status=RobotStatus.IDLE,
                coordination_status=CoordinationStatus.ACTIVE,
            )
            logger.info(f"Created robot state for discovered robot: {robot_id}")

            # Subscribe to Zenoh topics for this robot
            zenoh_monitor.subscribe_to_robots([robot_id])

    async def on_coordination_event(event: CoordinationEvent):
        # Log and broadcast coordination events
        event_log.append({
            "timestamp": event.timestamp,
            "type": "coordination",
            "robot_id": event.robot_id,
            "event_type": event.event_type,
            "details": event.details,
            "severity": event.severity,
        })
        if len(event_log) > MAX_EVENT_LOG_SIZE:
            event_log.pop(0)

        if connected_clients:
            await broadcast_event({
                "type": "coordination_event",
                "data": {
                    "robot_id": event.robot_id,
                    "event_type": event.event_type,
                    "severity": event.severity,
                }
            })

    # Note: Zenoh callbacks are sync, so we schedule broadcasts
    def on_coordination_event_sync(event: CoordinationEvent):
        try:
            asyncio.create_task(on_coordination_event(event))
        except Exception as e:
            logger.debug(f"Error creating broadcast task: {e}")

    zenoh_monitor.on_robot_discovered = on_robot_discovered
    zenoh_monitor.on_coordination_event = on_coordination_event_sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup on startup/shutdown."""
    global current_scenario_executor
    logger.info("Starting simulation web backend...")

    # Initialize ROS bridge with graceful degradation
    ros_connected = ros_bridge.connect()
    if ros_connected:
        # Load warehouse graph
        if not ros_bridge.load_warehouse_graph('/workspace/simulation/config/warehouse_graph.yaml'):
            logger.warning("Failed to load warehouse graph from ROS 2")
        ros_bridge_callbacks()
    else:
        logger.warning("ROS 2 not available - running in degraded mode")

    # Initialize Zenoh monitor
    zenoh_monitor.connect()
    zenoh_callbacks()

    # Start background task
    background_task = asyncio.create_task(background_task_manager())

    logger.info("Backend initialized and running (ROS 2 available: %s)", ros_connected)

    yield

    # Cleanup on shutdown
    logger.info("Shutting down...")
    if current_scenario_executor:
        await current_scenario_executor.stop()
    background_task.cancel()
    ros_bridge.shutdown()
    zenoh_monitor.shutdown()


# Create FastAPI app
app = FastAPI(
    title="SwarmOS Simulation Control Center",
    description="Web interface for multi-robot warehouse simulation",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- REST API Endpoints -----

@app.get("/api/simulation/status")
async def get_simulation_status() -> SimulationStatus:
    """Get current simulation status."""
    return ros_bridge.get_simulation_status()


@app.get("/api/robots")
async def get_robots() -> List[Dict]:
    """Get list of all robots and their current state."""
    robots = []
    for robot_id, state in ros_bridge.robots.items():
        robots.append({
            "id": state.id,
            "namespace": state.namespace,
            "pose": {"x": state.pose.x, "y": state.pose.y, "theta": state.pose.theta},
            "status": state.status.value,
            "coordination_status": state.coordination_status.value,
            "is_online": state.is_online,
        })
    return robots


@app.get("/api/robots/{robot_id}")
async def get_robot(robot_id: str) -> Dict:
    """Get detailed state for a specific robot."""
    if robot_id not in ros_bridge.robots:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} not found")

    state = ros_bridge.robots[robot_id]

    return {
        "id": state.id,
        "namespace": state.namespace,
        "pose": {"x": state.pose.x, "y": state.pose.y, "theta": state.pose.theta},
        "velocity": {"vx": state.velocity.vx, "vy": state.velocity.vy, "omega": state.velocity.omega},
        "status": state.status.value,
        "coordination_status": state.coordination_status.value,
        "blocked_by": state.blocked_by,
        "current_goal": state.current_goal,
        "planned_route": [
            {"x": wp.x, "y": wp.y, "eta": wp.eta, "etd": wp.etd, "cell_id": wp.cell_id}
            for wp in state.planned_route
        ],
        "is_online": state.is_online,
        "last_update_time": state.last_update_time,
    }


@app.get("/api/warehouse/graph")
async def get_warehouse_graph() -> Dict:
    """Get warehouse topology graph."""
    if not ros_bridge.warehouse_graph:
        return {"nodes": [], "edges": []}

    graph = ros_bridge.warehouse_graph
    return {
        "nodes": [
            {"id": n.id, "x": n.x, "y": n.y}
            for n in graph.nodes
        ],
        "edges": [
            {"from": e.from_node, "to": e.to_node, "segment_id": e.segment_id}
            for e in graph.edges
        ]
    }


@app.post("/api/robots/{robot_id}/goal")
async def send_goal(robot_id: str, request: GoalRequest) -> Dict:
    """Send a goal to a robot (safe, preserves coordination).

    This is the safe pattern:
    - Publishes to goal_pose topic (CoordAgent listens)
    - Does not bypass coordination architecture
    - CoordAgent's _nav_active guard prevents concurrent dispatch
    """
    success = await ros_bridge.send_goal(robot_id, request.x, request.y)

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to send goal to {robot_id}")

    # Log event
    event_log.append({
        "timestamp": asyncio.get_event_loop().time(),
        "type": "navigation",
        "robot_id": robot_id,
        "event_type": "goal_sent",
        "details": {"x": request.x, "y": request.y},
        "severity": "info",
    })

    return {"status": "ok", "robot_id": robot_id, "goal": {"x": request.x, "y": request.y}}


@app.post("/api/robots/{robot_id}/cancel")
async def cancel_goal(robot_id: str) -> Dict:
    """Cancel the current goal for a robot."""
    if robot_id not in ros_bridge.robots:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} not found")

    # In Phase 2, we just need to acknowledge the request
    # In Phase 5+, we'll implement actual Nav2 cancellation

    return {"status": "ok", "robot_id": robot_id, "message": "Cancel request acknowledged"}


@app.post("/api/simulation/start")
async def start_simulation() -> Dict:
    """Start the simulation."""
    ros_bridge.sim_started = True
    return {"status": "ok", "message": "Simulation started"}


@app.post("/api/simulation/stop")
async def stop_simulation() -> Dict:
    """Stop the simulation."""
    ros_bridge.sim_started = False
    return {"status": "ok", "message": "Simulation stopped"}


@app.post("/api/scenarios/{scenario_name}/start")
async def start_scenario(scenario_name: str) -> Dict:
    """Start a scenario with proper execution.

    This endpoint:
    1. Loads the scenario YAML
    2. Creates a ScenarioExecutor
    3. Publishes initial poses and goals at proper times
    4. Executes scenario events
    """
    global current_scenario_executor

    scenario = ros_bridge.load_scenario(scenario_name)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_name} not found")

    # Stop any running scenario first
    if current_scenario_executor:
        await current_scenario_executor.stop()
        current_scenario_executor = None

    # Verify ROS is available
    if not ros_bridge.ros_initialized or not ros_bridge.node:
        raise HTTPException(status_code=500, detail="ROS 2 not available")

    try:
        # Create and start executor
        executor = ScenarioExecutor(ros_bridge.node, scenario.__dict__)
        await executor.start()
        current_scenario_executor = executor

        ros_bridge.sim_started = True

        logger.info(f"Started scenario {scenario_name}")

        return {
            "status": "ok",
            "scenario": scenario_name,
            "num_robots": len(scenario.robots),
            "num_events": len(scenario.events),
            "message": "Scenario started successfully"
        }
    except Exception as e:
        logger.error(f"Failed to start scenario {scenario_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start scenario: {str(e)}")


@app.get("/api/scenarios")
async def list_scenarios() -> List[str]:
    """List available scenarios."""
    return ["normal_ops", "overlapping_paths", "blocked_aisle", "robot_failure", "network_disruption"]


@app.get("/api/events")
async def get_events(limit: int = 100) -> List[Dict]:
    """Get recent events from the event log."""
    return event_log[-limit:]


# ----- WebSocket Endpoint -----

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    connected_clients.add(websocket)

    logger.info("WebSocket client connected")

    try:
        # Keep connection open
        while True:
            # Receive ping/pong or close message
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        connected_clients.discard(websocket)
        logger.info("WebSocket client disconnected")


# ----- Health Check -----

@app.get("/api/health")
async def health_check() -> Dict:
    """Health check endpoint with detailed service status."""
    has_robots = len(ros_bridge.robots) > 0
    is_ros2_healthy = ros_bridge.ros_initialized or has_robots

    health_status = {
        "status": "healthy" if (is_ros2_healthy and zenoh_monitor.initialized) else "degraded",
        "timestamp": asyncio.get_event_loop().time(),
        "services": {
            "ros2": {
                "status": "connected" if is_ros2_healthy else "disconnected",
                "available": is_ros2_healthy,
                "num_robots_discovered": len(ros_bridge.robots),
            },
            "zenoh": {
                "status": "connected" if zenoh_monitor.initialized else "disconnected",
                "available": zenoh_monitor.initialized,
            },
            "warehouse_graph": {
                "status": "loaded" if ros_bridge.warehouse_graph else "not_loaded",
                "available": ros_bridge.warehouse_graph is not None,
                "num_nodes": len(ros_bridge.warehouse_graph.nodes) if ros_bridge.warehouse_graph else 0,
            },
        },
        "websocket_clients": len(connected_clients),
        "scenario_running": current_scenario_executor is not None,
    }

    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
