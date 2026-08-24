# SwarmOS Quick Reference - Manual Setup

## TL;DR - One-Time Setup

```bash
# 1. Install system packages
sudo apt-get update && sudo apt-get install -y \
  ros-jazzy-desktop ros-jazzy-gazebo-* ros-jazzy-nav2-* \
  python3-pip python3-venv build-essential nodejs npm xvfb

# 2. Setup Python venv
cd /opt/swarmos
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools
pip install python-zenoh==0.10.* numpy scipy pyyaml fastapi uvicorn[standard] \
  pydantic python-socketio aiohttp pytest httpx

# 3. Setup ROS 2
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

## TL;DR - Running Everything

**Method 1: Separate Terminals (Recommended for debugging)**

```bash
# Terminal 1: Virtual Display
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &

# Terminal 2: Zenoh Router
docker run -d --name zenoh-router --network host -p 7447:7447 eclipse/zenoh:latest

# Terminal 3: Gazebo Sim
source ~/.bashrc && export ROS_DOMAIN_ID=42 && \
  export GAZEBO_MODEL_PATH=/opt/swarmos/simulation/models:/opt/ros/jazzy/share/gazebo_ros/models && \
  export DISPLAY=:99 && \
  ros2 launch simulation warehouse.launch.py spawn_amrs:=3

# Terminal 4-6: Agents (3 terminals, one for each)
for AGENT_ID in 0 1 2; do
  # In separate terminal:
  source ~/.bashrc && source /opt/swarmos/venv/bin/activate && \
  export ROS_DOMAIN_ID=42 && export ZENOH_ENDPOINT="tcp/127.0.0.1:7447" && \
  cd /opt/swarmos/amr_agents && python3 agent.py --robot_id amr_$AGENT_ID
done

# Terminal 7: Task Dispatcher
source ~/.bashrc && source /opt/swarmos/venv/bin/activate && \
  export ROS_DOMAIN_ID=42 && export ZENOH_ENDPOINT="tcp/127.0.0.1:7447" && \
  cd /opt/swarmos/amr_agents && python3 task_dispatcher.py

# Terminal 8: Backend API (optional)
cd /opt/swarmos/web_backend && source ~/.bashrc && source ../venv/bin/activate && \
  uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 9: Frontend (optional)
cd /opt/swarmos/web_frontend && npm run dev
```

**Method 2: Automated Script**

```bash
chmod +x /opt/swarmos/run_all.sh
/opt/swarmos/run_all.sh
```

## Environment Variables (Set in every terminal)

```bash
export ROS_DOMAIN_ID=42
export GAZEBO_MODEL_PATH=/opt/swarmos/simulation/models:/opt/ros/jazzy/share/gazebo_ros/models
export GAZEBO_RESOURCE_PATH=/opt/swarmos/simulation
export ZENOH_ENDPOINT="tcp/127.0.0.1:7447"
export DISPLAY=:99
```

## Essential Commands

| Task | Command |
|------|---------|
| **Activate venv** | `source /opt/swarmos/venv/bin/activate` |
| **Source ROS 2** | `source ~/.bashrc` |
| **List ROS 2 topics** | `ros2 topic list` |
| **Monitor topic** | `ros2 topic echo /swarm/agent/amr_0/status` |
| **List ROS 2 nodes** | `ros2 node list` |
| **Check Zenoh** | `curl http://localhost:7447/info` |
| **Run tests** | `cd /opt/swarmos/tests && python3 benchmark_runner.py --num_agents=3 --num_tasks=10` |
| **Stop all services** | See "Cleanup" below |

## Service Ports

| Service | Port |
|---------|------|
| Zenoh Router | 7447 |
| Backend API | 8000 |
| Frontend | 3000 |
| Nginx Proxy | 9000 |

## Cleanup (Stop All Services)

```bash
#!/bin/bash
pkill -f "agent.py"
pkill -f "task_dispatcher.py"
pkill -f "gazebo"
pkill -f "ros2"
pkill -f "uvicorn"
pkill -f "npm"
pkill -f "Xvfb"
docker stop zenoh-router 2>/dev/null || true
docker rm zenoh-router 2>/dev/null || true
echo "All services stopped"
```

## Remove Docker Images

```bash
docker-compose -f /opt/swarmos/docker/docker-compose.yml down --volumes 2>/dev/null
docker rmi swarmos:dev swarmos:sim swarmos-qa-test:latest swarmos:base eclipse/zenoh:latest -f 2>/dev/null
docker image prune -f
echo "✓ Docker images removed"
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Zenoh connection refused | Ensure router is running: `curl http://localhost:7447/info` |
| ROS 2 topics not found | Source setup: `source ~/.bashrc` and check `ROS_DOMAIN_ID=42` |
| Gazebo fails to start | Check X11: `echo $DISPLAY` (should be `:99`). Try VNC: `vncserver :99` |
| Agent won't connect | Wait 20-30 seconds for Gazebo to initialize fully |
| Port already in use | Kill existing process: `lsof -i :PORT` then `kill -9 PID` |

## Detailed Guides

- **Full Setup:** See `MANUAL_SETUP.md`
- **Remove Docker:** See `REMOVE_DOCKER.md`
- **Architecture:** See `docs/ARCHITECTURE.md`
- **Development:** See `CLAUDE.md`

## Next Steps

1. ✓ Install prerequisites (System packages + ROS 2)
2. ✓ Setup Python environment (venv + dependencies)
3. → Start components (use Terminal method or run_all.sh)
4. → Run tests to verify everything works
5. → Check logs if any issues

**All components must be started; don't skip any step.**
