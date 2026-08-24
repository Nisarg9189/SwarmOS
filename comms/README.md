# Comms Layer (Zenoh + ROS 2 Bridge)

Inter-agent communication and Zenoh ↔ ROS 2 translation.

## Components

- `zenoh_bridge.py` — Bridges ROS 2 topics ↔ Zenoh pub/sub (to be implemented)
- `messages/` — Protocol definitions

## Protocol

See `docs/COMMS_PROTOCOL.md` for full topic schema and latency contracts.

**Quick overview:**
- Zenoh router at `tcp/zenoh-router:7447`
- Agents publish status every 10 Hz to `/swarm/agent/{agent_id}/status`
- Peers subscribe to `+/status` to track all agents
- Intent and task events also published to Zenoh for decentralized coordination

## Bridge Responsibilities

1. Subscribe to ROS 2 `/tf`, `/scan`, `/costmap` (local agent data)
2. Translate to Zenoh topics for peer consumption
3. Subscribe to Zenoh peer status
4. Publish back to ROS 2 (optional, for Nav2 integration)

## Testing

```bash
cd comms
python3 zenoh_bridge.py --robot_id amr_0 &
# In another terminal:
cd ../tests
python3 test_zenoh_connectivity.py
```
