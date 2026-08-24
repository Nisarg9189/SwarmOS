# SwarmOS Architecture

## System Overview

SwarmOS is a **decentralized multi-robot coordination system** where each AMR runs an independent agent that communicates peer-to-peer via Zenoh. There is no central server or planner.

```
┌─────────────────────────────────────────────────────┐
│ Gazebo Simulation (Warehouse + 3 AMRs)              │
│  • Physics engine                                    │
│  • LiDAR + collision sensors                        │
│  • Nav2 cost maps                                   │
└─────────────────────────────────────────────────────┘
              ↕ (ROS 2 topics)
┌─────────┬─────────┬─────────┐
│ Agent 0 │ Agent 1 │ Agent 2 │  (Python coordination engines)
│         │         │         │  • Path planning
│         │         │         │  • Deadlock detection
│         │         │         │  • Task assignment
└────┬────┴────┬────┴────┬────┘
     │         │         │
     └────┬────┴────┬────┘
          ↕ (Zenoh pub/sub)
     ┌─────────────────┐
     │ Zenoh Router    │  (Peer discovery, topic routing)
     └─────────────────┘
```

## Layer Definitions

### 1. Simulation Layer (Gazebo + Nav2)
**Owns:** Physics, warehouse geometry, sensor simulation, navigation cost maps.

**Provides to agents (ROS 2):**
- `/tf` — Transforms (odometry, map frame)
- `/scan` — LiDAR point cloud
- `/amr_N/local_costmap/costmap` — Occupancy grid
- `/amr_N/global_costmap/costmap` — Global environment map

**Consumes from agents (ROS 2):**
- `/cmd_vel` — Velocity commands
- `/move_base_simple/goal` — Nav2 goal targets

### 2. Comms Layer (Zenoh Bridge + ROS 2 Integration)
**Owns:** Peer discovery, inter-agent message routing, latency budgets.

**Responsibility:**
- Bridge between ROS 2 local topics and Zenoh global topics
- Publish peer state updates to Zenoh
- Subscribe to peer intents and route them to coordinator

**Zenoh Topics Published:**
```
/swarm/agent/{agent_id}/status          [10 Hz, 100ms budget]
  { position: [x, y, θ],
    velocity: [vx, vy, ωz],
    goal: [gx, gy],
    state: idle | moving | blocked,
    timestamp: uint64_ms }

/swarm/agent/{agent_id}/occupancy       [1 Hz, async]
  { agent_id, local_cells: [(x,y,cost), ...] }
```

**Zenoh Topics Subscribed:**
```
/swarm/agent/+/status                   (all peers' positions)
/swarm/agent/+/intent                   (all peers' movement intents)
/swarm/task/events                      (global task queue updates)
```

**SLA:** Peer status updates arrive within 100ms of publication; lost messages are acceptable if < 10% loss rate.

### 3. Agent Layer (Coordination Engine)
**Owns:** Decision-making, task assignment, deadlock detection, dynamic rerouting.

**Consumes (ROS 2 local):**
- Own position from `/tf`
- Environment from `/scan` and `/costmap`
- Nav2 status from `/amr_N/nav_to_pose/_feedback`

**Publishes (ROS 2 local):**
- `/move_base_simple/goal` → Nav2 planner

**Consumes (Zenoh global):**
- Peer positions and velocities from `/swarm/agent/+/status`
- Peer intents from `/swarm/agent/+/intent`
- Task events from `/swarm/task/events`

**Publishes (Zenoh global):**
```
/swarm/agent/{agent_id}/intent
  { next_waypoint: [x, y],
    desired_velocity: [vx, vy],
    priority: 0-100,
    reason: moving_to_task | avoiding_deadlock | yielding,
    timestamp: uint64_ms }

/swarm/agent/{agent_id}/task_status
  { task_id, status: claimed | in_progress | completed | failed }
```

**Latency Budget:** Agent decision cycle ≤ 50ms (target: 10-20ms for real-time collision avoidance).

### 4. Benchmark Layer
**Owns:** Metrics collection, baseline comparison, reproducibility.

**Inputs (recorded from sim):**
- Collision events (from sim sensors)
- Task completion times
- Path lengths
- Communication latency

**Outputs:**
- JSON benchmark report (collisions, task time, improvement %, latency p50/p99)
- Flamegraph of agent CPU (if profiling enabled)
- Video of sim run (if recording enabled)

## Message Format Contracts

All Zenoh messages are **newline-delimited JSON** for simplicity and debugging.

### Agent Status (10 Hz)
```json
{
  "agent_id": "amr_0",
  "timestamp_ms": 1724435847123,
  "position": {"x": 5.2, "y": 3.1, "theta": 1.57},
  "velocity": {"vx": 0.5, "vy": 0.0, "omega": 0.1},
  "goal": {"x": 10.0, "y": 8.0},
  "state": "moving",
  "battery_pct": 85
}
```

### Agent Intent (5 Hz or event-driven)
```json
{
  "agent_id": "amr_0",
  "timestamp_ms": 1724435847130,
  "next_waypoint": {"x": 6.0, "y": 3.5},
  "desired_velocity": {"vx": 0.8, "vy": 0.1},
  "priority": 50,
  "reason": "moving_to_task",
  "task_id": "task_5"
}
```

### Collision Definition
**Hard collision:** Bounding boxes overlap (end-to-end distance < 0.5m for 0.3m-radius AMRs).

**Soft collision:** Separation < 1.0m while both moving (indicates poor coordination).

## Isolation & Failure Modes

### Normal Operation
1. Agents start, discover Zenoh router
2. Agents subscribe to peer status
3. Every 100ms, agents compute new waypoint given peer positions
4. Agents publish intent and set Nav2 goal
5. If peer blocks path, agent detects deadlock (position unchanged for 5+ seconds) and reroutes

### Peer Down
- If peer status missing for 2 cycles (200ms), assume peer is offline
- Ignore its position in collision checks (conservative: treat it as yielded)

### Zenoh Partition
- Single Zenoh router → no partition handling (acceptable for MVP)
- Future: multi-router mesh with quorum-based conflict resolution

### Network Latency Spike
- Accept: Status updates delayed up to 1 second
- Fallback: Use last-known position + velocity extrapolation

## Data Flow Example: Collision Avoidance

```
t=0ms:    Agent-0 publishes: pos=[5.0, 3.0]
          Agent-1 publishes: pos=[6.0, 3.0]  (1m away, converging)

t=10ms:   Agent-0 receives Agent-1's pos=[6.0, 3.0]
          Agent-0 computes: distance=1.0m, velocity vectors collision likely
          Agent-0 publishes intent: waypoint=[4.5, 3.0] (yield left)

t=20ms:   Agent-1 receives Agent-0's intent=[4.5, 3.0]
          Agent-1 sees: Agent-0 yielding, can continue

t=30ms:   Nav2 steers Agent-0 left, separation increases to 1.5m
```

## Timing Budgets

| Component | Cycle | Budget | Notes |
|-----------|-------|--------|-------|
| Sim physics | 20ms | Hard | Gazebo default |
| Sim LiDAR scan | 33ms | Hard | 30 Hz scans |
| Agent sense | 100ms | Soft | Read own state from ROS 2 |
| Agent decision | 50ms | Hard | Compute next waypoint |
| Agent publish (Zenoh) | 100ms | Soft | Broadcast intent |
| Peer state latency | 100ms | SLA | Max delay for status |

**Path:** Agent senses (100ms) → decides (50ms) → publishes (100ms) → peers receive (100ms) = 350ms end-to-end.

This is acceptable if we pre-emptively avoid (i.e., don't wait for peer state to react, but extrapolate).

## Deployment & Configuration

### Per-Agent Config (in docker-compose.yml)
```yaml
services:
  amr_0:
    environment:
      ROBOT_ID: amr_0
      ZENOH_ENDPOINT: zenoh-router:7447
      TASK_DISPATCH_MODE: decentralized
      DEADLOCK_TIMEOUT_MS: 5000
```

### Sim Config (warehouse.launch.py)
```python
DeclareLaunchArgument("spawn_amrs", default_value="3")
DeclareLaunchArgument("world_file", default_value="warehouse.world")
```

## Known Limitations (MVP)

1. **Single Zenoh router:** No mesh redundancy; router failure = system failure
2. **No authentication:** Zenoh open to any peer on network
3. **No persistent storage:** Task history lost on shutdown
4. **Sim-only:** No real hardware integration yet
5. **Uniform agent code:** All agents run same algorithm; no heterogeneous robots

## Future Work (Post-MVP)

- Zenoh router redundancy + leader election
- Multi-router mesh with time-sync
- ROS 2 middleware encryption (OSRF guidelines)
- Hardware-in-the-loop: real robot agent connecting to sim
- Heterogeneous agents (different sizes, speeds, capabilities)
- Persistent task queue (Redis)
