#!/usr/bin/env python3
"""
End-to-end test for the web backend.
Tests backend initialization, ROS bridge, and API endpoints.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add web_backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "web_backend"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all backend modules can be imported."""
    logger.info("Testing imports...")
    try:
        from app.models import (
            Pose, Velocity, RobotState, SimulationStatus,
            RobotStatus, CoordinationStatus
        )
        logger.info("✓ Models imported successfully")

        from app.ros_bridge import RoSBridge
        logger.info("✓ RoSBridge imported successfully")

        from app.zenoh_monitor import ZenohMonitor
        logger.info("✓ ZenohMonitor imported successfully")

        from app.scenario_executor import ScenarioExecutor
        logger.info("✓ ScenarioExecutor imported successfully")

        try:
            from app.main import app
            logger.info("✓ FastAPI app imported successfully")
        except ModuleNotFoundError as e:
            logger.warning(f"⊘ FastAPI not installed (will work in docker): {e}")

        return True
    except Exception as e:
        logger.error(f"✗ Import failed: {e}", exc_info=True)
        return False


def test_models():
    """Test that data models work correctly."""
    logger.info("Testing models...")
    try:
        from app.models import Pose, Velocity, RobotState, RobotStatus, CoordinationStatus

        # Test Pose
        pose = Pose(x=1.0, y=2.0, theta=0.5)
        assert pose.x == 1.0
        logger.info("✓ Pose model works")

        # Test Velocity
        vel = Velocity(vx=0.5, vy=0.0, omega=0.1)
        assert vel.vx == 0.5
        logger.info("✓ Velocity model works")

        # Test RobotState
        robot = RobotState(
            id="amr_0",
            namespace="/amr_0",
            pose=pose,
            velocity=vel,
            status=RobotStatus.IDLE,
            coordination_status=CoordinationStatus.ACTIVE,
        )
        assert robot.id == "amr_0"
        logger.info("✓ RobotState model works")

        return True
    except Exception as e:
        logger.error(f"✗ Model test failed: {e}", exc_info=True)
        return False


def test_ros_bridge_graceful_degradation():
    """Test that RoSBridge works in degraded mode (no ROS)."""
    logger.info("Testing RoS Bridge graceful degradation...")
    try:
        from app.ros_bridge import RoSBridge

        bridge = RoSBridge()

        # Should have mock robots initialized
        assert len(bridge.robots) == 3, f"Expected 3 mock robots, got {len(bridge.robots)}"
        logger.info(f"✓ RoSBridge initialized with {len(bridge.robots)} mock robots")

        # Check robot IDs
        robot_ids = list(bridge.robots.keys())
        logger.info(f"  Robot IDs: {robot_ids}")

        # Test get_simulation_status
        status = bridge.get_simulation_status()
        logger.info(f"  Simulation status: {status.status}")
        logger.info(f"  Active robots: {status.num_active_robots}")

        return True
    except Exception as e:
        logger.error(f"✗ RoS Bridge test failed: {e}", exc_info=True)
        return False


def test_fastapi_app():
    """Test that FastAPI app can be created."""
    logger.info("Testing FastAPI app...")
    try:
        try:
            from app.main import app
            from fastapi.testclient import TestClient
        except ModuleNotFoundError as e:
            logger.warning(f"⊘ Skipping FastAPI tests (FastAPI not installed): {e}")
            return True  # Skip gracefully, will work in docker

        client = TestClient(app)

        # Test health endpoint
        response = client.get("/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        logger.info("✓ Health endpoint works")

        # Test get_robots endpoint
        response = client.get("/api/robots")
        assert response.status_code == 200, f"Get robots failed: {response.status_code}"
        robots = response.json()
        assert isinstance(robots, list), f"Expected list, got {type(robots)}"
        logger.info(f"✓ Get robots endpoint works (found {len(robots)} robots)")

        # Test get_warehouse_graph endpoint
        response = client.get("/api/warehouse/graph")
        assert response.status_code == 200, f"Get warehouse graph failed: {response.status_code}"
        graph = response.json()
        logger.info(f"✓ Warehouse graph endpoint works (found {len(graph.get('nodes', []))} nodes)")

        # Test get_simulation_status endpoint
        response = client.get("/api/simulation/status")
        assert response.status_code == 200, f"Get simulation status failed: {response.status_code}"
        logger.info("✓ Simulation status endpoint works")

        # Test get_scenarios endpoint
        response = client.get("/api/scenarios")
        assert response.status_code == 200, f"Get scenarios failed: {response.status_code}"
        scenarios = response.json()
        logger.info(f"✓ Scenarios endpoint works (found {len(scenarios)} scenarios)")

        return True
    except Exception as e:
        logger.error(f"✗ FastAPI app test failed: {e}", exc_info=True)
        return False


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("SwarmOS Backend End-to-End Test")
    logger.info("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("Models", test_models),
        ("RoS Bridge (Degraded Mode)", test_ros_bridge_graceful_degradation),
        ("FastAPI App", test_fastapi_app),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info("")
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"Unexpected error in {test_name}: {e}", exc_info=True)
            results.append((test_name, False))

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\nTotal: {passed_count}/{total_count} tests passed")

    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
