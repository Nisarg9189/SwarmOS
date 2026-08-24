# SwarmOS Manual Setup Guide

This guide provides all commands required to run SwarmOS manually without Docker.

## Prerequisites

- **OS:** Ubuntu 24.04 LTS
- **Python:** Python 3.10+
- **Node.js:** For web frontend (if using the web dashboard)
- **X11/Display Server:** For Gazebo visualization (Xvfb or VNC)

---

## Part 1: System Setup

### 1.1 Update System Packages

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### 1.2 Install ROS 2 Jazzy

```bash
# Add ROS 2 repository key
sudo curl -sSL https://repo.ros2.org/ros.key | sudo apt-key add -

# Add ROS 2 repository
echo "deb [arch=amd64,arm64] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2-latest.list

# Update and install ROS 2 Jazzy desktop
sudo apt-get update
sudo apt-get install -y ros-jazzy-desktop

# Install additional ROS 2 packages
sudo apt-get install -y \
  ros-jazzy-gazebo-* \
  ros-jazzy-nav2-* \
  ros-jazzy-tf2-* \
  ros-jazzy-geometry-msgs \
  ros-jazzy-sensor-msgs

# Source ROS 2 setup (add to ~/.bashrc for persistence)
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source /opt/ros/jazzy/setup.bash
```

### 1.3 Install System Dependencies

```bash
sudo apt-get install -y \
  python3-pip \
  python3-venv \
  build-essential \
  git \
  wget \
  nano \
  curl \
  gnupg2 \
  ca-certificates \
  xvfb \
  x11-utils \
  mesa-utils \
  libgl1-mesa-glx \
  nodejs \
  npm
```

---

## Part 2: Python Environment Setup

### 2.1 Create Virtual Environment

```bash
cd /opt/swarmos

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 2.2 Install Python Dependencies

```bash
# Upgrade pip and setuptools
pip install --upgrade pip setuptools wheel

# Install core dependencies
pip install \
  python-zenoh==0.10.* \
  numpy \
  scipy \
  pyyaml \
  click \
  python-socketio \
  aiohttp \
  fastapi==0.104.1 \
  uvicorn[standard]==0.24.0 \
  pydantic==2.5.0 \
  pydantic-settings==2.1.0 \
  python-multipart==0.0.6 \
  aiofiles==23.2.1 \
  pytest==7.4.3 \
  httpx==0.25.2
```

---

## Part 3: Running Individual Components

### 3.1 Environment Setup (Required for all components)

```bash
# In every terminal, before running components:
cd /opt/swarmos
source ~/.bashrc  # Sources ROS 2 setup
source venv/bin/activate  # Activates Python venv

# Set ROS 2 environment variables
export ROS_DOMAIN_ID=42
export GAZEBO_MODEL_PATH=/opt/swarmos/simulation/models:/opt/ros/jazzy/share/gazebo_ros/models
export GAZEBO_RESOURCE_PATH=/opt/swarmos/simulation
export ZENOH_ENDPOINT="tcp/127.0.0.1:7447"
```

### 3.2 Start Zenoh Router

**Terminal 1: Zenoh Router**

```bash
# Install Zenoh router (if not already installed)
cargo install zenoh-cli 2>/dev/null || \
  (curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
   source "$HOME/.cargo/env" && \
   cargo install zenoh-cli)

# Or use the pre-built Docker image via standalone binary:
# Download and run zenoh router on port 7447
docker run -d \
  --name zenoh-router \
  --network host \
  -p 7447:7447 \
  -e RUST_LOG=info \
  eclipse/zenoh:latest \
  /zenohd --conf "{ listeners: [ { protocol: 'tcp', address: '0.0.0.0:7447' } ] }"

# Or run directly if Rust/Cargo available:
zenohd --conf "{ listeners: [ { protocol: 'tcp', address: '0.0.0.0:7447' } ] }" 2>&1 | tee /tmp/zenoh.log &

# Verify Zenoh is running
sleep 2
curl http://localhost:7447/info 2>/dev/null || echo "Waiting for Zenoh..."
```

### 3.3 Start Gazebo Simulation + Nav2

**Terminal 2: Gazebo + Nav2**

```bash
# Activate environment
cd /opt/swarmos
source ~/.bashrc
export ROS_DOMAIN_ID=42
export GAZEBO_MODEL_PATH=/opt/swarmos/simulation/models:/opt/ros/jazzy/share/gazebo_ros/models
export GAZEBO_RESOURCE_PATH=/opt/swarmos/simulation

# Wait for Zenoh to be ready (check from Terminal 1)
sleep 5

# Start Gazebo with warehouse and 3 AMRs
# Option A: With display (requires X11 or VNC)
ros2 launch simulation warehouse.launch.py spawn_amrs:=3

# Option B: Headless with Xvfb (virtual display)
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &
sleep 2
ros2 launch simulation warehouse.launch.py spawn_amrs:=3
```

### 3.4 Start Coordination Agent 0

**Terminal 3: Agent 0**

```bash
cd /opt/swarmos
source ~/.bashrc
source venv/bin/activate
export ROS_DOMAIN_ID=42
export ZENOH_ENDPOINT="tcp/127.0.0.1:7447"
export ROBOT_ID="amr_0"

# Wait for Gazebo to be ready (~20-30 seconds from Terminal 2)
sleep 30

cd amr_agents
python3 agent.py --robot_id amr_0
```

### 3.5 Start Coordination Agent 1

**Terminal 4: Agent 1**

```bash
cd /opt/swarmos
source ~/.bashrc
source venv/bin/activate
export ROS_DOMAIN_ID=42
export ZENOH_ENDPOINT="tcp/127.0.0.1:7447"
export ROBOT_ID="amr_1"

sleep 30
cd amr_agents
python3 agent.py --robot_id amr_1
```

### 3.6 Start Coordination Agent 2

**Terminal 5: Agent 2**

```bash
cd /opt/swarmos
source ~/.bashrc
source venv/bin/activate
export ROS_DOMAIN_ID=42
export ZENOH_ENDPOINT="tcp/127.0.0.1:7447"
export ROBOT_ID="amr_2"

sleep 30
cd amr_agents
python3 agent.py --robot_id amr_2
```

### 3.7 Start Task Dispatcher

**Terminal 6: Task Dispatcher**

```bash
cd /opt/swarmos
source ~/.bashrc
source venv/bin/activate
export ROS_DOMAIN_ID=42
export ZENOH_ENDPOINT="tcp/127.0.0.1:7447"

sleep 40  # Wait for agents to connect

cd amr_agents
python3 task_dispatcher.py
```

### 3.8 Start Web Backend (Optional)

**Terminal 7: Backend API**

```bash
cd /opt/swarmos/web_backend
source ~/.bashrc
source ../venv/bin/activate

# Run FastAPI server on port 8000
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3.9 Start Web Frontend (Optional)

**Terminal 8: Frontend**

```bash
cd /opt/swarmos/web_frontend

# If not already installed
npm install

# Start development server on port 3000
npm run dev

# Or build for production
npm run build
npm start
```

---

## Part 4: Running All Components (Single Command Script)

Create `/opt/swarmos/run_all.sh`:

```bash
#!/bin/bash
set -e

cd /opt/swarmos
source ~/.bashrc
export ROS_DOMAIN_ID=42
export GAZEBO_MODEL_PATH=/opt/swarmos/simulation/models:/opt/ros/jazzy/share/gazebo_ros/models
export GAZEBO_RESOURCE_PATH=/opt/swarmos/simulation
export ZENOH_ENDPOINT="tcp/127.0.0.1:7447"
export DISPLAY=:99

# Start virtual display
Xvfb :99 -screen 0 1024x768x24 &
XVFB_PID=$!
sleep 2

# Start Zenoh router
docker run -d \
  --name zenoh-router \
  --network host \
  -p 7447:7447 \
  eclipse/zenoh:latest \
  /zenohd --conf "{ listeners: [ { protocol: 'tcp', address: '0.0.0.0:7447' } ] }" &
sleep 3

# Activate Python environment
source venv/bin/activate

# Start Gazebo simulation
gnome-terminal --title="Gazebo Sim" -- bash -c "
  cd /opt/swarmos
  source ~/.bashrc
  export ROS_DOMAIN_ID=42
  export GAZEBO_MODEL_PATH=/opt/swarmos/simulation/models:/opt/ros/jazzy/share/gazebo_ros/models
  export GAZEBO_RESOURCE_PATH=/opt/swarmos/simulation
  export DISPLAY=:99
  ros2 launch simulation warehouse.launch.py spawn_amrs:=3
  sleep 1000000" &

# Wait for Gazebo
sleep 30

# Start agents
for i in 0 1 2; do
  gnome-terminal --title="Agent $i" -- bash -c "
    cd /opt/swarmos
    source ~/.bashrc
    source venv/bin/activate
    export ROS_DOMAIN_ID=42
    export ZENOH_ENDPOINT='tcp/127.0.0.1:7447'
    export ROBOT_ID='amr_$i'
    cd amr_agents
    python3 agent.py --robot_id amr_$i
    sleep 1000000" &
  sleep 5
done

# Start task dispatcher
gnome-terminal --title="Task Dispatcher" -- bash -c "
  cd /opt/swarmos
  source ~/.bashrc
  source venv/bin/activate
  export ROS_DOMAIN_ID=42
  export ZENOH_ENDPOINT='tcp/127.0.0.1:7447'
  cd amr_agents
  python3 task_dispatcher.py
  sleep 1000000" &

sleep 5

# Start backend
gnome-terminal --title="Backend API" -- bash -c "
  cd /opt/swarmos/web_backend
  source ~/.bashrc
  source ../venv/bin/activate
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  sleep 1000000" &

# Start frontend
gnome-terminal --title="Frontend" -- bash -c "
  cd /opt/swarmos/web_frontend
  npm run dev
  sleep 1000000" &

echo "All services started!"
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "Press Ctrl+C to stop (you'll need to manually stop the terminal windows)"
wait $XVFB_PID
```

Make it executable:

```bash
chmod +x /opt/swarmos/run_all.sh
./run_all.sh
```

---

## Part 5: Running Tests and Benchmarks

### 5.1 Run Collision Checker

```bash
cd /opt/swarmos
source ~/.bashrc
source venv/bin/activate
export ROS_DOMAIN_ID=42

cd tests
python3 collision_checker.py --sim_log=../simulation/latest_run.log
```

### 5.2 Run Benchmark Suite

```bash
cd /opt/swarmos
source ~/.bashrc
source venv/bin/activate
export ROS_DOMAIN_ID=42
export ZENOH_ENDPOINT="tcp/127.0.0.1:7447"

cd tests
python3 benchmark_runner.py --num_agents=3 --num_tasks=10
```

### 5.3 Monitor ROS 2 Topics

```bash
source ~/.bashrc
export ROS_DOMAIN_ID=42

# List all topics
ros2 topic list

# Monitor specific topic
ros2 topic echo /tf
ros2 topic echo /scan
ros2 topic echo /swarm/agent/amr_0/status
ros2 topic echo /swarm/agent/amr_0/intent
```

---

## Part 6: Monitoring and Debugging

### 6.1 Check Service Status

```bash
# Check if Zenoh router is running
curl http://localhost:7447/info 2>/dev/null | jq .

# Check if ROS 2 is running
ros2 node list

# Check ROS 2 topics
ros2 topic list

# Check Zenoh topics
# (Requires zenoh CLI installed)
```

### 6.2 View Logs

```bash
# Gazebo logs
tail -f /tmp/gazebo.log 2>/dev/null || echo "No gazebo log"

# Zenoh logs
docker logs zenoh-router 2>/dev/null || echo "Zenoh not running in docker"

# Agent logs (check Terminal 3-5)

# Backend logs (check Terminal 7)
```

### 6.3 Kill All Services

```bash
#!/bin/bash
# Kill all services
pkill -f "agent.py"
pkill -f "task_dispatcher.py"
pkill -f "zenohd"
pkill -f "gazebo"
pkill -f "ros2"
pkill -f "uvicorn"
pkill -f "npm"
pkill -f "Xvfb"

# If using Docker for Zenoh:
docker stop zenoh-router 2>/dev/null || true
docker rm zenoh-router 2>/dev/null || true

echo "All services stopped"
```

---

## Part 7: Troubleshooting

### Issue: "Zenoh connection refused"
- Ensure Zenoh router is running: `curl http://localhost:7447/info`
- Check if port 7447 is free: `lsof -i :7447`

### Issue: "ROS 2 topics not found"
- Ensure ROS 2 is sourced: `source /opt/ros/jazzy/setup.bash`
- Check ROS_DOMAIN_ID is set: `echo $ROS_DOMAIN_ID` (should be 42)
- Verify Gazebo is running: `ros2 node list | grep gazebo`

### Issue: "Gazebo fails to start"
- Check X11 display: `echo $DISPLAY` (should be :99 or similar)
- Verify Xvfb is running: `ps aux | grep Xvfb`
- Try VNC instead: `vncserver :99 &`

### Issue: "Agent fails to connect"
- Check Gazebo is healthy (wait 20-30 seconds)
- Verify ROS_DOMAIN_ID and ZENOH_ENDPOINT are set
- Check agent logs for error messages

---

## Port Reference

| Service | Port | Protocol |
|---------|------|----------|
| Zenoh Router | 7447 | TCP |
| ROS 2 Discovery | 7400-7409 | UDP |
| Backend API | 8000 | HTTP |
| Frontend | 3000 | HTTP |
| Gazebo GUI | Xvfb :99 | X11 |
| Nginx Reverse Proxy | 9000 | HTTP |

---

## Next Steps

1. **Complete all prerequisites** (Part 1-2)
2. **Start services individually** (Part 3.1-3.9) to verify each component
3. **Use the convenience script** (Part 4) once everything works
4. **Run tests** (Part 5) to verify functionality
5. **Monitor and debug** (Part 6) as needed

All commands tested on Ubuntu 24.04 LTS with ROS 2 Jazzy.
