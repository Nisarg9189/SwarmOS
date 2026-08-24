# SwarmOS Agent Interface

This document defines the contract that each coordination agent must implement.

## Agent Lifecycle

Every agent runs as a standalone Python process with this lifecycle:

```
1. __init__()              → Load config, connect to Zenoh & ROS 2
2. discover_peers()        → Subscribe to /swarm/agent/+/status
3. claim_task()            → Listen for /swarm/task/events, claim when ready
4. run_control_loop()      → Every 50-100ms:
   a. sense()              → Read own position, goal, obstacles
   b. plan()               → Compute next waypoint
   c. publish_state()      → Broadcast status & intent
   d. execute()            → Publish Nav2 goal
5. on_shutdown()           → Graceful teardown
```

## Minimal Agent API

### Class: `CoordinationAgent`

**Constructor:**
```python
class CoordinationAgent:
    def __init__(self, robot_id: str, zenoh_endpoint: str):
        """
        Initialize agent.
        
        Args:
            robot_id: e.g., "amr_0", "amr_1" (must be unique in swarm)
            zenoh_endpoint: e.g., "tcp/zenoh-router:7447"
        
        Raises:
            RuntimeError: If Zenoh or ROS 2 connection fails
        """
```

### Core Methods

**`sense() → SensorData`**
```python
@dataclass
class SensorData:
    timestamp_ms: int
    position: np.ndarray              # [x, y, theta] in meters/radians
    velocity: np.ndarray              # [vx, vy, omega]
    goal: Optional[np.ndarray]        # [x, y] or None if no goal
    obstacles: List[np.ndarray]       # Detected obstacles as [x, y, radius]
    battery_pct: float                # 0-100
    peer_states: Dict[str, PeerState] # {agent_id: {pos, vel, intent, ...}}

@dataclass
class PeerState:
    position: np.ndarray        # [x, y, theta]
    velocity: np.ndarray        # [vx, vy, omega]
    goal: Optional[np.ndarray]  # [x, y]
    intent: Optional[np.ndarray] # [next_wp_x, next_wp_y]
    priority: int               # 0-100
    last_update_ms: int         # Timestamp of last status received
    confidence: float           # 0-100 (how fresh this data is)

def sense(self) -> SensorData:
    """
    Read current state from ROS 2 topics and Zenoh subscriptions.
    
    Blocks until data available; returns immediately if fresh.
    """
```

**`plan(sensor_data: SensorData) → Plan`**
```python
@dataclass
class Plan:
    next_waypoint: np.ndarray          # [x, y]
    desired_velocity: np.ndarray       # [vx, vy] (m/s)
    priority: int                      # 0-100
    reason: str                        # "moving_to_task" | "avoiding_deadlock" | ...
    task_id: Optional[str]             # Current task, if any
    confidence: float                  # 0.0-1.0 (replan soon if low)
    
def plan(self, sensor_data: SensorData) -> Plan:
    """
    Compute next waypoint given sensed state.
    
    Algorithm must:
    - Check for collisions with peers (use extrapolation for latency)
    - Detect deadlock (same position for 5+ seconds)
    - Assign priority (yield if higher-priority peer incoming)
    - Return waypoint reachable by Nav2
    
    Returns immediately; does not block.
    """
```

**`execute(plan: Plan) → bool`**
```python
def execute(self, plan: Plan) -> bool:
    """
    Command Nav2 to move to next waypoint.
    
    Publishes to ROS 2 /move_base_simple/goal and Zenoh intent topic.
    
    Returns:
        True if Nav2 accepted goal
        False if goal unreachable or navigation failed
    """
```

**`publish_state(sensor_data: SensorData) → None`**
```python
def publish_state(self, sensor_data: SensorData) -> None:
    """
    Publish own status to Zenoh /swarm/agent/{agent_id}/status.
    
    Called every control cycle (50-100ms).
    """
```

**`claim_task(task_event: Dict) → bool`**
```python
def claim_task(self, task_event: Dict) -> bool:
    """
    Claim a task from /swarm/task/events.
    
    Called when task dispatcher announces new task.
    
    Returns:
        True if agent can and wants to claim this task
        False if task is unreachable or agent busy
    """
```

**`run_control_loop() → None`**
```python
def run_control_loop(self) -> None:
    """
    Main loop. Runs indefinitely until shutdown.
    
    Pseudocode:
        while not shutdown:
            sensor_data = sense()
            plan = plan(sensor_data)
            execute(plan)
            publish_state(sensor_data)
            sleep(50ms)  # Maintain 20 Hz control rate
    """
```

### State Management Methods

**`is_blocked() → bool`**
```python
def is_blocked(self, timeout_ms: int = 5000) -> bool:
    """
    Check if agent is stationary despite having a goal.
    
    Returns True if position hasn't changed more than 0.1m in timeout_ms.
    """
```

**`deadlock_resolution(peer_id: str) -> float`**
```python
def deadlock_resolution(self, peer_id: str) -> float:
    """
    Compute priority adjustment when colliding with peer.
    
    Tiebreaker: agent with lower agent_id gets higher priority.
    
    Returns:
        Priority delta to apply (-50 to +50)
    """
```

### Lifecycle Methods

**`start() → None`**
```python
def start(self) -> None:
    """
    Connect to Zenoh and ROS 2, subscribe to topics, start control loop.
    
    Blocking; spawns background thread for control_loop.
    """
```

**`shutdown() → None`**
```python
def shutdown(self) -> None:
    """
    Stop control loop, publish final status, close Zenoh session.
    
    Clean: agent should not re-publish after this.
    """
```

---

## Integration Points

### 1. Zenoh Topics (via `publish_state()` and subscriptions in `sense()`)

**Publishes:**
- `/swarm/agent/{robot_id}/status` (10 Hz)
- `/swarm/agent/{robot_id}/intent` (5 Hz)
- `/swarm/agent/{robot_id}/task_status` (event-driven)

**Subscribes:**
- `/swarm/agent/+/status` → populates `sensor_data.peer_states`
- `/swarm/agent/+/intent` → used for collision prediction
- `/swarm/task/events` → triggers `claim_task()`

### 2. ROS 2 Topics (via comms bridge)

**Reads (via TF lookups or subscribers):**
- `/tf` → Agent's own pose via `lookup_transform("map", f"base_link_{robot_id}")`
- `/scan` or `/amr_N/lidar/scan` → LiDAR obstacle detection
- `/amr_N/local_costmap/costmap` → Occupancy grid from Nav2

**Writes:**
- `/move_base_simple/goal` → Send goal to Nav2
- `/amr_N/cmd_vel` → Direct velocity command (optional; prefer Nav2 goal)

### 3. Task Dispatcher (via Zenoh)

**Agent role:**
1. Subscribe to `/swarm/task/events`
2. When `task_dispatched` event arrives, decide to claim or skip
3. Publish `/swarm/agent/{robot_id}/task_status` with `claimed` when accepted
4. Publish `completed` or `failed` when done

---

## Minimal Viable Implementation (MVP)

```python
import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, List
import zenoh
import rclpy
from nav_msgs.msg import OccupancyGrid
from tf2_ros import TransformListener, Buffer

class CoordinationAgent:
    def __init__(self, robot_id: str, zenoh_endpoint: str):
        self.robot_id = robot_id
        self.zenoh_session = zenoh.open(zenoh_endpoint)
        rclpy.init()
        self.node = rclpy.create_node(f"agent_{robot_id}")
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self.node)
        
    def sense(self) -> SensorData:
        # Read own position from TF
        try:
            tf = self.tf_buffer.lookup_transform("map", f"base_link_{self.robot_id}", rclpy.time.Time())
            x, y = tf.transform.translation.x, tf.transform.translation.y
            # Extract theta from quaternion (simplified)
            theta = 0.0
        except:
            x, y, theta = 0.0, 0.0, 0.0
        
        # Subscribe to peer status (from Zenoh)
        peer_states = {}
        sub = self.zenoh_session.declare_subscriber("/swarm/agent/+/status")
        for sample in sub.recv():
            # Parse JSON from sample.payload
            pass
        
        return SensorData(
            timestamp_ms=int(time.time() * 1000),
            position=np.array([x, y, theta]),
            velocity=np.array([0, 0, 0]),
            goal=None,
            obstacles=[],
            battery_pct=100,
            peer_states=peer_states
        )
    
    def plan(self, sensor_data: SensorData) -> Plan:
        # Dummy: move forward
        next_wp = sensor_data.position[:2] + np.array([1, 0])
        return Plan(
            next_waypoint=next_wp,
            desired_velocity=np.array([0.5, 0]),
            priority=50,
            reason="moving_to_task",
            task_id=None,
            confidence=0.8
        )
    
    def execute(self, plan: Plan) -> bool:
        # Publish Nav2 goal
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = "map"
        goal_pose.pose.position.x = plan.next_waypoint[0]
        goal_pose.pose.position.y = plan.next_waypoint[1]
        # Publish to /move_base_simple/goal
        return True
    
    def run_control_loop(self) -> None:
        while True:
            sensor_data = self.sense()
            plan = self.plan(sensor_data)
            self.execute(plan)
            self.publish_state(sensor_data)
            time.sleep(0.1)  # 10 Hz
```

---

## Testing Checklist

When implementing an agent, verify:

- [ ] Agent connects to Zenoh (prints "Zenoh session OK")
- [ ] Agent reads own position via ROS 2 TF
- [ ] Agent publishes status to Zenoh every 100ms
- [ ] Agent receives peer status updates within 200ms
- [ ] Collision detection works (agents pass test_collision_avoidance.py)
- [ ] Deadlock detection triggers when stuck (test_deadlock_recovery.py)
- [ ] Task claiming works (test_task_assignment.py)
- [ ] No crashes on network delay or missing peer data

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Sense latency (TF lookup + Zenoh read) | < 50ms |
| Plan latency (decision algorithm) | < 50ms |
| Control loop frequency | 10-20 Hz |
| Peer state staleness | < 200ms |
| Startup time | < 5s |

---

## Future Enhancements (Post-MVP)

- Heterogeneous agents (different sizes, speeds)
- Task preemption (higher-priority task interrupts current)
- Machine learning for priority/confidence prediction
- Distributed consensus (majority vote to break ties)
