"""
Pytest configuration and fixtures for web backend tests.
Sets up mocks for ROS 2 and Zenoh to allow testing without actual ROS.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock ROS 2 modules BEFORE importing app
sys.modules["rclpy"] = MagicMock()
sys.modules["rclpy.context"] = MagicMock()
sys.modules["rclpy.node"] = MagicMock()
sys.modules["rclpy.client"] = MagicMock()
sys.modules["rclpy.action"] = MagicMock()
sys.modules["std_msgs"] = MagicMock()
sys.modules["std_msgs.msg"] = MagicMock()
sys.modules["nav2_msgs"] = MagicMock()
sys.modules["nav2_msgs.action"] = MagicMock()
sys.modules["geometry_msgs"] = MagicMock()
sys.modules["geometry_msgs.msg"] = MagicMock()
sys.modules["zenoh"] = MagicMock()

# Now we can import app with mocked ROS
from app.main import app, ros_bridge, zenoh_monitor
from app.models import (
    RobotState, Pose, Velocity, NavigationState,
    CoordinationStatus, SimulationStatus, Waypoint,
    WarehouseGraph, WarehouseNode, WarehouseEdge
)


@pytest.fixture
def mock_ros_bridge():
    """Mock ROS bridge with realistic data."""
    bridge = MagicMock()
    bridge.ros_initialized = True
    bridge.robots = {}
    bridge.sim_started = False
    bridge.warehouse_graph = WarehouseGraph(
        nodes=[
            WarehouseNode(id="n1", x=0.0, y=0.0),
            WarehouseNode(id="n2", x=10.0, y=0.0),
            WarehouseNode(id="n3", x=10.0, y=10.0),
            WarehouseNode(id="n4", x=0.0, y=10.0),
        ],
        edges=[
            WarehouseEdge(from_node="n1", to_node="n2", segment_id="s1"),
            WarehouseEdge(from_node="n2", to_node="n3", segment_id="s2"),
            WarehouseEdge(from_node="n3", to_node="n4", segment_id="s3"),
            WarehouseEdge(from_node="n4", to_node="n1", segment_id="s4"),
        ]
    )

    # Mock methods
    bridge.connect = MagicMock(return_value=True)
    bridge.load_warehouse_graph = MagicMock(return_value=True)
    bridge.spin_once = AsyncMock()
    bridge.get_simulation_status = MagicMock(return_value=SimulationStatus(
        status="running",
        sim_time=100.0,
        num_active_robots=0,
        num_navigating_robots=0
    ))
    bridge.send_goal = AsyncMock(return_value=True)
    bridge.shutdown = MagicMock()

    return bridge


@pytest.fixture
def mock_zenoh_monitor():
    """Mock Zenoh monitor."""
    monitor = MagicMock()
    monitor.initialized = True
    monitor.connect = MagicMock()
    monitor.update_robot_from_zenoh = MagicMock()
    monitor.subscribe_to_robots = MagicMock()
    monitor.unsubscribe_from_robot = MagicMock()
    monitor.shutdown = MagicMock()

    return monitor


@pytest.fixture
async def client(mock_ros_bridge, mock_zenoh_monitor):
    """Create test client with mocked ROS/Zenoh."""
    # Patch the global ros_bridge and zenoh_monitor
    with patch("app.main.ros_bridge", mock_ros_bridge):
        with patch("app.main.zenoh_monitor", mock_zenoh_monitor):
            from httpx import AsyncClient, ASGITransport
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac


@pytest.fixture
def sample_robot():
    """Create a sample robot state for testing."""
    return RobotState(
        id="robot_1",
        namespace="/robot_1",
        pose=Pose(x=5.0, y=5.0, theta=0.0),
        velocity=Velocity(vx=0.0, vy=0.0, omega=0.0),
        status=NavigationState.IDLE,
        coordination_status=CoordinationStatus.FREE,
        blocked_by=None,
        is_online=True,
        current_goal=Pose(x=10.0, y=10.0, theta=0.0),
        planned_route=[
            Waypoint(x=6.0, y=5.0, eta=1.0, etd=2.0, cell_id="n2"),
            Waypoint(x=10.0, y=10.0, eta=5.0, etd=5.0, cell_id="n3"),
        ],
        last_update_time=100.0
    )
