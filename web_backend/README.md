# SwarmOS Web Backend

FastAPI backend for the Simulation Control Center. Bridges ROS 2, Zenoh coordination protocol, and Gazebo simulation to a web frontend.

## Architecture

```
FastAPI Backend (8000)
├── ROS 2 Bridge (rclpy)
│   ├── Subscribe: /clock, /<robot_id>/odom, /map
│   ├── Publish: /<robot_id>/goal_pose
│   └── Track navigation safety (SWA-11 fix)
│
├── Zenoh Monitor
│   ├── Subscribe: swarmos/*/robot/*/state
│   ├── Subscribe: swarmos/*/robot/*/intent
│   ├── Subscribe: swarmos/*/robot/*/task
│   └── Subscribe: swarmos/*/robot/*/negotiate
│
├── REST API
│   └── /api/simulation/*
│   └── /api/robots/*
│   └── /api/scenarios/*
│   └── /api/warehouse/*
│
└── WebSocket
    └── /ws (live state updates)
```

## Installation

### Phase 2 Setup (Current)

1. **Install dependencies** (in ROS environment):
```bash
cd web_backend
pip install -r requirements.txt
```

2. **Run the backend**:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Integration

Add to `docker-compose.yml`:
```yaml
services:
  web-backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ROS_DOMAIN_ID=0
      - PYTHONUNBUFFERED=1
    command: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    depends_on:
      - simulation
```

## API Reference

### Simulation Control
- `GET /api/simulation/status` — Get current simulation state
- `POST /api/simulation/start` — Start simulation
- `POST /api/simulation/stop` — Stop simulation
- `POST /api/simulation/restart` — Restart simulation

### Robot State
- `GET /api/robots` — List all robots
- `GET /api/robots/{robot_id}` — Get detailed state for a robot
- `POST /api/robots/{robot_id}/goal` — Send goal to robot (safe)
- `POST /api/robots/{robot_id}/cancel` — Cancel current goal

### Scenarios
- `GET /api/scenarios` — List available scenarios
- `POST /api/scenarios/{name}/start` — Start a scenario

### Warehouse Info
- `GET /api/warehouse/graph` — Get warehouse topology (nodes, edges)

### Events
- `GET /api/events?limit=100` — Get recent events

### Health
- `GET /health` — Health check

### WebSocket
- `WS /ws` — Live updates stream

## Implementation Phases

### Phase 2: Minimal ROS/Web Bridge (Current)
- [x] FastAPI skeleton with rclpy integration
- [x] Basic REST API endpoints
- [x] WebSocket setup for live updates
- [x] Zenoh coordination monitoring
- [ ] Test robot discovery
- [ ] Verify goal dispatch safety
- [ ] Test without frontend (curl/postman)

### Phase 3: Dashboard Frontend
- [ ] Warehouse visualization
- [ ] Robot list and details
- [ ] Real-time position updates
- [ ] Scenario selector

### Phase 4: Scenario Controls
- [ ] Scenario startup (initial poses + goals)
- [ ] Stop/Restart
- [ ] Test all 5 scenarios

### Phase 5: Safe Manual Control
- [ ] Click-on-map goal selection
- [ ] Goal validation
- [ ] Cancel functionality

### Phase 6: Coordination Visualization
- [ ] Display planned routes
- [ ] Show conflicts and reservations
- [ ] Highlight waiting robots
- [ ] Event log with filtering

## Safety Guarantees

### SWA-11 Navigation Fix Preserved

The backend implements the **safe goal dispatch pattern**:

```python
# SAFE: Goes through CoordinationAgent
await ros_bridge.send_goal(robot_id, x, y)
  → publishes to /<robot_id>/goal_pose topic
  → CoordinationAgent listens and plans route
  → CoordinationAgent.tick() dispatches with _nav_active guard
  → guard prevents concurrent dispatch (SWA-11 fix)

# UNSAFE (NOT USED):
# ❌ DO NOT publish directly to Nav2 action
# ❌ DO NOT bypass CoordinationAgent
# ❌ DO NOT send multiple goals concurrently
```

### Testing Safety

Run Phase 2 verification:
```bash
# Start simulation
ros2 launch warehouse_sim warehouse_world.launch.py scenario:=normal_ops

# In another terminal, start backend
cd web_backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, test with curl
curl -X GET http://localhost:8000/api/robots
curl -X POST http://localhost:8000/api/robots/robot_1/goal \
  -H "Content-Type: application/json" \
  -d '{"x": -8.0, "y": 6.0}'

# Check that robots move and no "another navigator is processing" errors
```

## Graceful Degradation

The backend is designed to work even without ROS 2 or Zenoh:

- **No ROS 2**: Backend runs in simulation-only mode; REST endpoints return dummy data
- **No Zenoh**: Coordination monitoring disabled; only ROS topics work
- **Mixed mode**: Works with partial connectivity

This enables development/testing outside the full ROS environment.

## Logging

Set `PYTHONPATH` and run with logging:

```bash
PYTHONUNBUFFERED=1 python -m uvicorn app.main:app --log-level debug
```

Check for:
- `ROS 2 initialized successfully` — ROS connectivity OK
- `Connected to Zenoh router` — Zenoh connectivity OK
- `Robot discovered: robot_1` — Robot detection working
- `Goal sent to robot_1` — Goal dispatch working
- `WebSocket client connected` — Frontend can connect

## Troubleshooting

### "ROS 2 not available"
- Check you're running inside the Docker container
- Verify `source /opt/ros/jazzy/setup.bash` has been run
- Check `ros2 node list` to verify ROS is up

### "Cannot connect to Zenoh router"
- Start the simulation first: `ros2 launch warehouse_sim warehouse_world.launch.py`
- Zenoh router (rmw_zenohd) should start automatically
- Check with: `netstat -an | grep 7447` (should show listener on localhost:7447)

### "Robot not subscribed"
- Backend auto-subscribes when it sees odometry data
- Ensure robots are spawned in the simulation
- Check logs for "Robot discovered" messages

### WebSocket not connecting
- Check frontend is using correct URL: `ws://localhost:8000/ws`
- Ensure CORS is enabled (it is, in main.py)
- Check browser console for errors

## Next Steps

1. **Test Phase 2**: Start sim, run backend, test API endpoints with curl
2. **Implement Phase 3**: Build React frontend with warehouse visualization
3. **Connect**: Wire WebSocket to push live updates to frontend
4. **Iterate**: Add scenario controls, manual goals, coordination visualization

## Files

- `app/main.py` — FastAPI app and REST endpoints
- `app/ros_bridge.py` — ROS 2 connection and robot state
- `app/zenoh_monitor.py` — Zenoh coordination protocol monitoring
- `app/models.py` — Data models (RobotState, SimulationStatus, etc.)
- `requirements.txt` — Python dependencies
- `README.md` — This file

## Architecture Notes

### Why Separate Bridge & Monitor?

- **RoSBridge**: Manages ROS 2 connections, robot state, goal dispatch
- **ZenohMonitor**: Passive observer of coordination protocol

This separation allows:
- Testing without full coordination (use ROS bridge only)
- Monitoring without control (subscribe to Zenoh, don't publish)
- Clean layering (backend can be swapped with different ROS implementations)

### Thread Safety

- ROS callbacks (odometry) run in rclpy executor
- Zenoh callbacks are inline subscriptions
- WebSocket sending is async-safe via `broadcast_event()`
- Background task uses asyncio and awaits properly

### Event Loop Integration

- FastAPI runs on Uvicorn (asyncio)
- ROS spins in background task with non-blocking `spin_once()`
- Zenoh subscriptions are async-friendly (JSON payloads)
- WebSocket broadcasts use `asyncio.create_task()`

This keeps everything responsive.
