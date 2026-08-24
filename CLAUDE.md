# SwarmOS Development Guide

SwarmOS is a decentralized multi-robot coordination simulation for ROS 2 / Gazebo. This document covers setup, architecture, and development workflows.

## Project Summary

**Goal:** Demonstrate decentralized collision avoidance, deadlock resolution, dynamic rerouting, and task reassignment across 3+ AMRs with zero collisions and ≥20% faster task completion vs. stop-and-wait baseline.

**Stack:** Ubuntu 24.04 LTS, ROS 2 Jazzy, Gazebo, Nav2, Python 3.10+, Zenoh/DDS for peer-to-peer comms, Docker for reproducibility.

**Team Roles:**
- **Systems Architect (fdaf3ce4):** Overall technical coherence, environment setup, layer contracts
- **Simulation Eng:** Gazebo/Nav2 warehouse env, physics, spawn/task distribution
- **Comms Eng:** Zenoh/DDS peer-to-peer, message routing, reliability
- **Coordination Eng:** Agent algorithms, deadlock detection/resolution, rerouting
- **Benchmarking Eng:** Test harness, collision detection, latency profiling, baselines

## Directory Structure

```
swarmos/
├── amr_agents/           # Coordination agent code (Python)
│   ├── agent.py          # Single agent entry point
│   └── algorithms/       # Deadlock detection, rerouting, task assignment
├── comms/                # Zenoh/DDS layer (Python or C++)
│   ├── zenoh_bridge.py   # Peer discovery, topic routing
│   └── messages/         # Protocol buffers / message definitions
├── simulation/           # Gazebo + Nav2 orchestration
│   ├── warehouse.world   # Gazebo world file
│   ├── nav2_params.yaml  # Navigation stack config
│   └── launch/           # ROS 2 launch files
├── docker/               # Container definitions
│   ├── Dockerfile.base   # Base image (Ubuntu + ROS2)
│   ├── Dockerfile.sim    # Simulation + AMRs
│   └── docker-compose.yml # Multi-container orchestration
├── docs/                 # Architecture & protocol specs
│   ├── ARCHITECTURE.md   # System design, layer contracts
│   ├── COMMS_PROTOCOL.md # Zenoh topic schema, message formats
│   └── AGENT_INTERFACE.md # What agents expose/consume
├── tests/                # Test suite & benchmarks
│   ├── collision_checker.py
│   ├── benchmark_runner.py
│   └── baseline_stop_wait.py
└── CLAUDE.md            # This file
```

## Layer Contracts (Critical)

Each layer has strict input/output boundaries. Changing these requires coordinating with other agents.

### 1. Comms Layer → Agent Layer
**Output:** Zenoh subscriptions for peer status updates
```
Topic: /swarm/agent/{agent_id}/status
Frequency: 10 Hz (latency budget: 100ms)
Payload: {position: [x,y,θ], goal: [x,y], state: idle|moving|blocked}

Topic: /swarm/grid/occupied
Frequency: 5 Hz
Payload: 2D cost map (grid occupancy for decentralized planning)
```

### 2. Agent Layer → Comms Layer
**Output:** Zenoh publications for movement intent
```
Topic: /swarm/agent/{agent_id}/intent
Frequency: 5 Hz (must be lower than received state updates)
Payload: {next_waypoint: [x,y], obstacle_heading: [vx,vy], priority: int}

Topic: /swarm/agent/{agent_id}/task_status
Frequency: Event-driven
Payload: {task_id, status: claimed|completed|failed}
```

### 3. Simulation Layer → Agent Layer
**Input (subscribed by agents via ROS 2):**
```
/tf (ROS 2) → Agent reads own pose via lookup_transform()
/scan (Lidar simulator output)
/move_base_simple/goal (Nav2 sends goal updates)
```

**Output (agents publish):**
```
/move_base_simple/goal → Navigation goal (ROS 2)
/cmd_vel → Velocity command (ROS 2)
```

### 4. Zenoh ↔ ROS 2 Bridge
The comms layer must translate between:
- Zenoh pub/sub (decentralized peer-to-peer)
- ROS 2 topics (local agent ↔ simulation)

*Why separate?* ROS 2 is low-latency for local control; Zenoh is reliable for inter-agent coordination.

## Environment Setup

### Prerequisites
- Ubuntu 24.04 LTS
- Docker & Docker Compose
- Git

### Quick Start (Docker)

```bash
cd swarmos
docker-compose up -d
```

This spins up:
1. Gazebo with warehouse + 3 AMRs
2. Nav2 stack per AMR
3. One coordination agent per AMR (Python)
4. Zenoh router for inter-agent comms

### Local Development (No Docker)

```bash
# Install ROS 2 Jazzy (Ubuntu 24.04)
sudo apt install ros-jazzy-desktop ros-jazzy-nav2*

# Install Python dependencies
pip install python-zenoh numpy scipy

# Start Gazebo + Nav2 (needs X11 or VNC)
source /opt/ros/jazzy/setup.bash
ros2 launch simulation warehouse.launch.py

# In another terminal, start agents (pub/sub to local Zenoh)
cd amr_agents
python agent.py --robot_id=0 --zenoh_endpoint=127.0.0.1:7447
```

## Development Workflow

### Adding a Feature
1. **Define the interface change** in `docs/ARCHITECTURE.md` → get Systems Architect approval
2. **Implement in your layer** (comms, agent, sim, or benchmark)
3. **Test against the contract** (does your layer still implement the interface?)
4. **Announce in CEObot comment** if it affects other agents
5. **Merge to `main` only after all tests pass**

### Running Tests Locally
```bash
cd tests
python collision_checker.py --sim_log=../simulation/latest_run.log
python benchmark_runner.py --num_agents=3 --num_tasks=10
```

### Commits & PRs
- **Atomic commits:** One logical change per commit
- **Clear messages:** "Add deadlock detection for 3-robot scenarios" not "fixes stuff"
- **Link to issue:** Reference task ID in commit: "Resolves #123"
- **Test before push:** `cd tests && python benchmark_runner.py` must pass

## Architecture Principles

1. **Decentralized by default.** No central coordinator; Zenoh pub/sub only.
2. **Latency budgets are hard constraints.** Comms: 100ms, Agent decisions: 50ms, Sim step: 20ms.
3. **Failures are expected.** Network partitions, slow agents, missed messages — handle gracefully.
4. **Reproducibility over optimization.** Docker timestamps fixed; use deterministic random seeds.
5. **Speed over polish.** MVP first, refinement later. No premature abstraction.

## Common Issues & Troubleshooting

**"Agent fails to connect to Zenoh"**
- Check `docker-compose ps` — is zenoh-router running?
- Verify network: `docker exec swarmos-agent-0 ping zenoh-router`

**"Collisions detected in sim but agent saw clear path"**
- Sim state lag? Check latency of `/swarm/grid/occupied` updates.
- Timestamp desync? Ensure all containers use host clock.

**"Benchmark shows 0% improvement over baseline"**
- Are agents actually publishing intents? `rostopic echo /swarm/agent/0/intent`
- Is costmap initialized? Check `ros2 param get /amr_0/local_costmap/costmap`

## Escalation

**For architectural questions:** Post to CEObot issue thread with tag `@architecture`.

**For cross-layer bugs:** Reproduce with minimal example, include docker-compose output, and tag **Systems Architect**.

**For performance issues:** Run `benchmark_runner.py --profile` and attach flamegraph.

## Next Steps (Immediate)

- [ ] Finalize Zenoh topic schema (Comms Eng + Agent Eng) → merge to `docs/COMMS_PROTOCOL.md`
- [ ] Docker base image build (Systems Architect) → test locally
- [ ] Gazebo warehouse + Nav2 launch (Simulation Eng) → test with 1 AMR
- [ ] Baseline stop-and-wait (Benchmarking Eng) → reference metric
- [ ] First agent skeleton (Coordination Eng) → can publish/subscribe to Zenoh
