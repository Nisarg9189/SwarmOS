"""Data models for simulation state and API responses."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime


class RobotStatus(str, Enum):
    """Robot coordination status."""
    IDLE = "idle"
    NAVIGATING = "navigating"
    WAITING = "waiting"
    REROUTING = "rerouting"
    GOAL_REACHED = "goal_reached"
    ERROR = "error"
    OFFLINE = "offline"


class CoordinationStatus(str, Enum):
    """Coordination protocol status."""
    ACTIVE = "ACTIVE"
    YIELDING = "YIELDING"
    HOLDING = "HOLDING"
    FAILED = "FAILED"


@dataclass
class Pose:
    """Robot 3D position."""
    x: float
    y: float
    theta: float = 0.0


@dataclass
class Velocity:
    """Robot velocity."""
    vx: float = 0.0
    vy: float = 0.0
    omega: float = 0.0


@dataclass
class Waypoint:
    """Navigation waypoint with timing."""
    x: float
    y: float
    eta: float  # estimated time of arrival (unix epoch)
    etd: float  # estimated time of departure
    cell_id: Optional[str] = None


@dataclass
class RobotState:
    """Complete robot state snapshot."""
    id: str
    namespace: str
    pose: Pose
    velocity: Velocity
    status: RobotStatus
    coordination_status: CoordinationStatus
    blocked_by: Optional[str] = None
    current_goal: Optional[Pose] = None
    planned_route: List[Waypoint] = field(default_factory=list)
    last_update_time: float = 0.0
    is_online: bool = True


@dataclass
class SimulationStatus:
    """Overall simulation state."""
    status: str  # "stopped", "running", "starting", "error"
    sim_time: float  # seconds
    wall_time: datetime
    active_scenario: Optional[str] = None
    num_active_robots: int = 0
    num_navigating_robots: int = 0
    num_completed_goals: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class CoordinationEvent:
    """Coordination state change event."""
    timestamp: float
    robot_id: str
    event_type: str  # "route_planned", "conflict_detected", "reroute", "waiting", etc.
    details: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # "info", "warning", "error"


@dataclass
class NavigationEvent:
    """Navigation state change event."""
    timestamp: float
    robot_id: str
    event_type: str  # "goal_sent", "goal_reached", "goal_failed", "route_update", etc.
    details: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"


@dataclass
class SimulationEvent:
    """Simulation-level event."""
    timestamp: float
    event_type: str  # "sim_started", "sim_stopped", "scenario_changed", etc.
    details: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"


@dataclass
class SystemEvent:
    """System-level event (errors, warnings)."""
    timestamp: float
    event_type: str
    message: str
    severity: str  # "info", "warning", "error"
    component: str  # "ros", "zenoh", "backend", etc.


# Union type for all events
Event = CoordinationEvent | NavigationEvent | SimulationEvent | SystemEvent


@dataclass
class WarehouseNode:
    """Graph node in warehouse topology."""
    id: str
    x: float
    y: float


@dataclass
class WarehouseEdge:
    """Graph edge (navigable segment)."""
    from_node: str
    to_node: str
    segment_id: str


@dataclass
class WarehouseGraph:
    """Warehouse topology."""
    nodes: List[WarehouseNode]
    edges: List[WarehouseEdge]


@dataclass
class Scenario:
    """Scenario configuration."""
    name: str
    description: str
    robots: List[Dict[str, Any]]
    obstacles: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
