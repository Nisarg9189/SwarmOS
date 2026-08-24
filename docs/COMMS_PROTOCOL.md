# SwarmOS Communication Protocol

This document defines all Zenoh topics, message formats, and latency contracts between agents.

## Overview

SwarmOS uses **Zenoh pub/sub** for decentralized inter-agent communication. All messages are **newline-delimited JSON** (NDJSON) for debuggability and language agnostic parsing.

**Zenoh Router:** Single TCP endpoint (e.g., `tcp/zenoh-router:7447`) discovers and routes all messages. No central planner; purely pub/sub.

## Topic Hierarchy

```
/swarm/
  agent/
    {agent_id}/
      status                    # Position, velocity, goal, state
      intent                    # Next waypoint, desired motion
      task_status               # Task claim/completion events
  grid/
    occupancy                   # Merged costmaps from all agents
  task/
    events                      # Task dispatched/claimed/completed
  debug/
    collision_warnings          # Optional: near-miss alerts
    latency_histogram           # Optional: message delay stats
```

## Topic Specifications

### 1. `/swarm/agent/{agent_id}/status`

**Frequency:** 10 Hz (100ms period)

**Latency SLA:** Peer receives within 100ms of publication (95th percentile).

**Payload (JSON):**
```json
{
  "agent_id": "amr_0",
  "timestamp_ms": 1724435847123,
  "position": {
    "x": 5.234,
    "y": 3.567,
    "theta": 1.571
  },
  "velocity": {
    "vx": 0.523,
    "vy": -0.012,
    "omega": 0.032
  },
  "goal": {
    "x": 10.0,
    "y": 8.0
  },
  "state": "moving",
  "battery_pct": 85,
  "max_speed_ms": 1.2
}
```

**Field Details:**
- `timestamp_ms`: Unix milliseconds (for lag calculation)
- `state`: One of `idle`, `moving`, `blocked`, `charging`, `failed`
- `theta`: Heading in radians (-π to π)
- `max_speed_ms`: Max velocity this agent can achieve (for collision prediction)

**Use Case:** Other agents extrapolate position at time t as:
```
x(t) = x_reported + vx * (t - timestamp) / 1000
y(t) = y_reported + vy * (t - timestamp) / 1000
```

**Failure Handling:** If status missing for 2 cycles (200ms), treat agent as offline (unknown position). Reactivate when status resumes.

---

### 2. `/swarm/agent/{agent_id}/intent`

**Frequency:** 5 Hz (200ms period) OR event-driven (when intent changes).

**Latency SLA:** Peer receives within 150ms of publication.

**Payload (JSON):**
```json
{
  "agent_id": "amr_0",
  "timestamp_ms": 1724435847200,
  "next_waypoint": {
    "x": 6.0,
    "y": 3.5
  },
  "desired_velocity": {
    "vx": 0.8,
    "vy": 0.1
  },
  "priority": 50,
  "reason": "moving_to_task",
  "task_id": "task_5",
  "confidence": 0.9
}
```

**Field Details:**
- `priority`: 0-100; higher = agent more "stubborn" (less likely to yield). Default 50.
- `reason`: One of `moving_to_task`, `avoiding_deadlock`, `yielding`, `idle`, `searching`
- `confidence`: 0.0-1.0; how certain agent is about this path (low = might re-plan soon)
- `desired_velocity`: Unit vector or achievable velocity; used for collision checking

**Use Case:** Peer reads intent to:
1. Predict where this agent is moving
2. Adjust own priority if collision likely (see deadlock detection spec below)

**Failure Handling:** If intent missing for 5 cycles, assume agent is idle (no motion expected).

---

### 3. `/swarm/agent/{agent_id}/task_status`

**Frequency:** Event-driven (sent only on state change).

**Latency SLA:** Delivered within 200ms.

**Payload (JSON):**
```json
{
  "agent_id": "amr_0",
  "timestamp_ms": 1724435847300,
  "task_id": "task_5",
  "status": "claimed",
  "estimated_completion_ms": 15000,
  "reason": "moving_to_pickup_at_(8.0,2.0)"
}
```

**Status Values:**
- `claimed` — Agent has accepted the task
- `in_progress` — Agent is executing (optional; can skip if claim → completion)
- `completed` — Task finished successfully
- `failed` — Task abandoned (unreachable, blocked, etc.)
- `released` — Task was claimed but now released back to queue

**Use Case:** Task dispatcher aggregates to monitor progress and reassign failed tasks.

---

### 4. `/swarm/grid/occupancy`

**Frequency:** 1 Hz (optional; can be disabled for bandwidth).

**Latency SLA:** Delivered within 500ms.

**Payload (JSON):**
```json
{
  "agent_id": "amr_1",
  "timestamp_ms": 1724435847400,
  "grid_origin": {"x": 0.0, "y": 0.0},
  "grid_resolution": 0.1,
  "cells": [
    [0, 0, 0, 10, 50, 100],
    [0, 5, 10, 20, 100, 100],
    [0, 0, 0, 10, 50, 100]
  ]
}
```

**Field Details:**
- `grid_resolution`: Meters per cell
- `cells`: 2D array; 0 = free, 1-99 = cost (inflation), 100 = occupied
- This is a **local** snippet of the costmap around the agent (e.g., 6x3 cells = 0.6m x 0.3m)

**Note:** Full global costmap unnecessary for MVP; local costmaps sufficient for collision prediction.

---

### 5. `/swarm/task/events`

**Frequency:** Event-driven.

**Latency SLA:** Delivered within 200ms.

**Payload (JSON):**
```json
{
  "timestamp_ms": 1724435847500,
  "event": "task_dispatched",
  "task_id": "task_7",
  "task": {
    "goal": {"x": 12.0, "y": 5.0},
    "priority": 10,
    "deadline_ms": 30000
  }
}
```

**Event Types:**

**`task_dispatched`**
```json
{ "event": "task_dispatched", "task_id": "task_7", "task": {...} }
```

**`task_completed`**
```json
{ "event": "task_completed", "task_id": "task_7", "agent_id": "amr_0", "duration_ms": 12345 }
```

**`task_failed`**
```json
{ "event": "task_failed", "task_id": "task_7", "reason": "unreachable" }
```

**Use Case:** Dispatcher publishes new tasks; agents subscribe to claim them.

---

## Deadlock & Priority Resolution

**Scenario:** Two agents on collision course, both moving toward each other.

**Resolution Algorithm (runs on each agent independently):**

1. Agent A publishes intent with `priority=50`
2. Agent A sees Agent B with intent also `priority=50`
3. Agent A detects collision likely (distance decreasing, paths intersect)
4. **Tiebreaker rule:** Agent with lower `agent_id` yields (lexicographic sort)
   - e.g., `amr_0` yields to `amr_2`
5. Yielding agent adjusts intent: `priority=10`, `reason=yielding`
6. Non-yielding agent continues at `priority=90`

**Expected Outcome:** Within 100ms, both agents have seen each other's updated intents and plan non-colliding paths.

**Failure Mode:** If both agents yield simultaneously (race condition), both move away. Acceptable but suboptimal.

---

## Collision Detection & Reporting (Optional)

**Topic:** `/swarm/debug/collision_warnings` (only if enabled)

**Payload:**
```json
{
  "timestamp_ms": 1724435847600,
  "agent_1": "amr_0",
  "agent_2": "amr_1",
  "distance_m": 0.8,
  "severity": "soft_collision",
  "predicted_impact_ms": 500
}
```

**Severity:**
- `soft_collision` — Distance 0.5m–1.0m, both moving
- `hard_collision` — Distance < 0.5m (collision has or will occur)

**Use Case:** For telemetry and debugging; agents do NOT react to this topic (it's one-way logging).

---

## Latency Budget & Tuning

| Hop | Budget | Example |
|-----|--------|---------|
| Agent publishes status | 0ms | -baseline- |
| Zenoh router propagates | 20ms | TCP latency in container network |
| Peer receives | ~100ms | Peer polls Zenoh every 100ms OR notification latency |
| Peer reacts (computes evasion) | 50ms | Local computation, no network |
| Peer publishes new intent | 0ms | -baseline- |
| **Total end-to-end reaction** | **170ms** | Peer sees status → changes course |

**Conservative assumption for collision prediction:** Use 200ms latency for all peer data.

---

## JSON Encoding Rules

**Timestamps:**
- All times in **Unix milliseconds** (since 1970-01-01 UTC)
- Agents use `int(time.time() * 1000)` or equivalent
- Receivers compute lag as `now_ms - timestamp_ms`

**Floats:**
- Use 3 decimal places (e.g., `5.234` not `5.2341234`)
- Reduce payload size; precision loss is < 1mm

**Nullability:**
- Omit optional fields rather than setting to `null`
- Example: if no task, omit `task_id` key

---

## Zenoh Configuration

**Example zenohd config for router:**
```toml
[general]
mode = "router"

[listeners]
[[listeners.unspecified]]
protocol = "tcp"
address = "0.0.0.0:7447"

[access_control]
default_permission = "allow"  # MVP: no auth
```

**Example client (agent) connection:**
```python
import zenoh

session = zenoh.open(zenoh.Config.from_file("/etc/zenoh/client.conf"))
# OR
session = zenoh.open(f"tcp/zenoh-router:7447")
sub = session.declare_subscriber("/swarm/agent/+/status")
pub = session.declare_publisher(f"/swarm/agent/{agent_id}/status")
```

---

## Backwards Compatibility & Versioning

**MVP Approach:** No versioning. If message format must change:
1. Update `COMMS_PROTOCOL.md` with new schema
2. All agents redeployed atomically (docker-compose up --pull)
3. Brief downtime acceptable

**Post-MVP:** Add version field to payload:
```json
{ "schema_version": 1, "agent_id": "...", ... }
```

---

## Testing & Validation

**Unit Test (per agent):**
```bash
python3 -c "
import zenoh
import json
import time

session = zenoh.open('tcp/127.0.0.1:7447')
pub = session.declare_publisher('/swarm/agent/test/status')
pub.put(json.dumps({'agent_id': 'test', 'timestamp_ms': int(time.time()*1000), ...}))
```

**Integration Test (multi-agent):**
```bash
docker-compose up -d
sleep 10
docker exec agent-0 python3 /workspace/tests/validate_zenoh_topics.py
```

---

## Appendix: ROS 2 ↔ Zenoh Bridge

**Why separate?**
- ROS 2 local topics (tf, scan, costmap) have low latency but high bandwidth
- Zenoh is designed for sparse, critical inter-agent updates
- Bridge decouples local real-time control from global coordination

**Bridge Process (runs on each agent):**

```
Zenoh subscriber: /swarm/agent/+/status
        ↓
Parse JSON → extract position, velocity
        ↓
Publish to ROS 2 topic: /tf (transform)
        ↓
Local Nav2 stack uses TF for collision checking
```

**Reverse:**
```
Read ROS 2: /amr_0/local_costmap/costmap
        ↓
Downsample & extract local cells
        ↓
Publish to Zenoh: /swarm/grid/occupancy
```

**Reference Implementation:** See `comms/zenoh_bridge.py`
