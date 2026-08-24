# AMR Coordination Agents

Coordination engine for decentralized multi-robot task assignment and collision avoidance.

## Structure

- `agent.py` — Main agent entry point (to be implemented by Coordination Engineer)
- `algorithms/` — Pathfinding, deadlock detection, task assignment
- `task_dispatcher.py` — Central task dispatcher (listens for new tasks, broadcasts to agents)

## Quick Start

```bash
cd amr_agents
python3 agent.py --robot_id amr_0 --zenoh_endpoint tcp/127.0.0.1:7447
```

See `docs/AGENT_INTERFACE.md` for required methods.

## Dependencies

- `python-zenoh` (installed via docker-compose)
- `rclpy` (ROS 2)
- `numpy`, `scipy`

## Testing

```bash
cd ../tests
python3 test_collision_avoidance.py
```
