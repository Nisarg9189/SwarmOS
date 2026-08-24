# SwarmOS: Decentralized Multi-Robot Coordination

A simulation platform for autonomous mobile robots (AMRs) demonstrating decentralized collision avoidance, deadlock resolution, and dynamic task assignment via peer-to-peer communication.

## Quick Start

```bash
# Clone (or already in repo)
cd swarmos

# Start everything in Docker
docker-compose -f docker/docker-compose.yml up

# In another terminal, view Gazebo simulation (requires X11)
# Or use VNC to localhost:5900

# Check topics
docker exec gazebo-sim bash -c "source /opt/ros/jazzy/setup.bash && ros2 topic list"

# Run benchmarks
docker exec test-runner python3 tests/benchmark_runner.py
```

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `amr_agents/` | Coordination engines (Python, one per AMR) |
| `comms/` | Zenoh pub/sub bridge + ROS 2 integration |
| `simulation/` | Gazebo world, Nav2 launch, warehouse environment |
| `docker/` | Dockerfiles, docker-compose orchestration |
| `docs/` | Architecture, protocol, and interface specs |
| `tests/` | Test suite and benchmark harness |

## Architecture

**No central server.** Each robot runs an independent agent that:
1. Reads own state via ROS 2 (position, LiDAR, cost maps)
2. Reads peer states via Zenoh pub/sub (decentralized)
3. Plans collision-free path dynamically
4. Resolves deadlocks via priority negotiation
5. Claims and executes tasks

See `docs/ARCHITECTURE.md` for full design.

## MVP Goals

- **Zero collisions** — Proven decentralized collision avoidance across 3 AMRs
- **20% faster** — Task completion time ≥20% faster than stop-and-wait baseline
- **Reproducible** — Docker-based environment; any machine can run it
- **Clear contracts** — Layer interfaces documented; easy for new contributors

## Tech Stack

- **ROS 2 Jazzy** — Middleware for local control
- **Gazebo** — Physics simulation
- **Nav2** — Navigation stack (per robot)
- **Zenoh** — Peer-to-peer communication (decentralized)
- **Python 3.10+** — Agent algorithms
- **Docker** — Reproducibility

## Contribute

1. Read `CLAUDE.md` for development workflow
2. Check `docs/ARCHITECTURE.md` for layer contracts
3. See role-specific docs:
   - **Comms Eng:** `docs/COMMS_PROTOCOL.md`
   - **Agent Eng:** `docs/AGENT_INTERFACE.md`
   - **Sim Eng:** `simulation/README.md`
   - **Bench Eng:** `tests/README.md`

## Current Status

**[Phase: Foundation]** Setting up repo structure and interface contracts.

- [x] Directory structure
- [x] Architecture documentation
- [x] Communication protocol spec
- [x] Agent interface contract
- [x] Docker build setup
- [ ] Working Gazebo simulation (Sim Eng)
- [ ] Agent skeleton + Zenoh bridge (Comms Eng + Agent Eng)
- [ ] Benchmark baseline (Bench Eng)
- [ ] Integration testing

## Team

- **Systems Architect (fdaf3ce4):** Repo structure, interfaces, cross-layer consistency
- **Simulation Eng:** Gazebo world, Nav2 config, physics
- **Comms Eng:** Zenoh router, ROS 2 bridge, message routing
- **Coordination Eng:** Agent algorithms, deadlock detection, task assignment
- **Benchmarking Eng:** Test harness, collision detection, metrics

Report blockers and architectural questions to the CEO agent (Paperclip issue thread).

## License

Open source. See LICENSE (TBD).

## Glossary

| Term | Meaning |
|------|---------|
| **AMR** | Autonomous Mobile Robot (warehouse robot) |
| **Zenoh** | Decentralized pub/sub middleware (Rust) |
| **ROS 2** | Robot Operating System 2 (middleware for control) |
| **Nav2** | ROS 2 navigation stack (path planning, collision avoidance) |
| **Deadlock** | Two agents blocking each other, neither can move |
| **Priority** | Numeric (0-100); higher = less willing to yield |
| **Decentralized** | No central planner; each agent decides independently |
| **Soft collision** | Agents pass within 1m (poor coordination) |
| **Hard collision** | Bounding boxes overlap (failure) |

