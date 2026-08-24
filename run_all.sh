#!/bin/bash

# SwarmOS Complete Startup Script (No Docker)
# Starts all components in separate terminal windows or processes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_DIR="/opt/swarmos"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="/tmp/swarmos_logs"

# Create log directory
mkdir -p "$LOG_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}SwarmOS - Complete Startup${NC}"
echo -e "${BLUE}========================================${NC}"

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗ Python 3 not found${NC}"
        exit 1
    fi

    if ! command -v ros2 &> /dev/null; then
        echo -e "${RED}✗ ROS 2 not found. Please install ROS 2 Jazzy.${NC}"
        exit 1
    fi

    if ! command -v zenohd &> /dev/null; then
        echo -e "${YELLOW}! Zenoh not installed. Installing...${NC}"
        install_zenoh
    fi

    echo -e "${GREEN}✓ Prerequisites OK${NC}"
}

# Install Zenoh if needed
install_zenoh() {
    echo -e "${YELLOW}Installing Zenoh (Rust required)...${NC}"

    if ! command -v cargo &> /dev/null; then
        echo -e "${YELLOW}Installing Rust...${NC}"
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
    fi

    cargo install zenoh-cli
    echo -e "${GREEN}✓ Zenoh installed${NC}"
}

# Setup environment
setup_environment() {
    echo -e "${YELLOW}Setting up environment...${NC}"

    # Create venv if it doesn't exist
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi

    # Install Python dependencies
    source "$VENV_DIR/bin/activate"
    pip install -q --upgrade pip setuptools wheel
    pip install -q \
        python-zenoh==0.10.* \
        numpy scipy pyyaml click \
        python-socketio aiohttp \
        fastapi==0.104.1 uvicorn[standard]==0.24.0 \
        pydantic==2.5.0 pydantic-settings==2.1.0 \
        python-multipart==0.0.6 aiofiles==23.2.1 \
        pytest==7.4.3 httpx==0.25.2

    echo -e "${GREEN}✓ Environment ready${NC}"
}

# Function to run a command in background with logging
run_component() {
    local name=$1
    local cmd=$2
    local log_file="$LOG_DIR/${name}.log"

    echo -e "${BLUE}Starting $name...${NC}"
    nohup bash -c "
        source ~/.bashrc
        source $VENV_DIR/bin/activate
        export ROS_DOMAIN_ID=42
        export GAZEBO_MODEL_PATH=/opt/swarmos/simulation/models:/opt/ros/jazzy/share/gazebo_ros/models
        export GAZEBO_RESOURCE_PATH=/opt/swarmos/simulation
        export ZENOH_ENDPOINT='tcp/127.0.0.1:7447'
        $cmd
    " > "$log_file" 2>&1 &

    local pid=$!
    echo "$(date '+%Y-%m-%d %H:%M:%S'): Started $name (PID: $pid)" >> "$log_file"
    echo -e "${GREEN}✓ $name started (PID: $pid)${NC}"
}

# Cleanup on exit
cleanup() {
    echo -e "${YELLOW}Shutting down...${NC}"
    pkill -f "zenohd" 2>/dev/null || true
    pkill -f "agent.py" 2>/dev/null || true
    pkill -f "task_dispatcher.py" 2>/dev/null || true
    pkill -f "gazebo" 2>/dev/null || true
    pkill -f "ros2" 2>/dev/null || true
    pkill -f "Xvfb" 2>/dev/null || true
    echo -e "${GREEN}✓ All services stopped${NC}"
}

trap cleanup EXIT

# Main startup sequence
echo -e "${BLUE}Starting SwarmOS components...${NC}"

# 1. Setup virtual display
echo -e "${YELLOW}Setting up virtual display...${NC}"
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 2>/dev/null &
sleep 1
echo -e "${GREEN}✓ Virtual display ready (DISPLAY=:99)${NC}"

# 2. Start Zenoh Router
run_component "Zenoh Router" "zenohd --conf \"{ listeners: [ { protocol: 'tcp', address: '0.0.0.0:7447' } ] }\""
sleep 3

# Verify Zenoh
if curl -s http://localhost:7447/info > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Zenoh verified${NC}"
else
    echo -e "${RED}✗ Zenoh verification failed${NC}"
    exit 1
fi

# 3. Start Gazebo + Nav2
run_component "Gazebo Simulation" "ros2 launch simulation warehouse.launch.py spawn_amrs:=3"
sleep 30

# 4. Start Agents
for i in 0 1 2; do
    run_component "Agent AMR_$i" "cd /opt/swarmos/amr_agents && python3 agent.py --robot_id amr_$i"
    sleep 5
done

# 5. Start Task Dispatcher
run_component "Task Dispatcher" "cd /opt/swarmos/amr_agents && python3 task_dispatcher.py"
sleep 2

# 6. Optional: Start Backend
if [ "$ENABLE_BACKEND" = "true" ]; then
    run_component "Backend API" "cd /opt/swarmos/web_backend && uvicorn main:app --host 0.0.0.0 --port 8000"
    sleep 2
fi

# 7. Optional: Start Frontend
if [ "$ENABLE_FRONTEND" = "true" ]; then
    run_component "Frontend" "cd /opt/swarmos/web_frontend && npm run dev"
    sleep 2
fi

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All components started successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Service Status:${NC}"
echo "  Zenoh Router:    http://localhost:7447"
echo "  Backend API:     http://localhost:8000 (if enabled)"
echo "  Frontend:        http://localhost:3000 (if enabled)"
echo "  Gazebo:          Virtual display :99"
echo ""
echo -e "${BLUE}View Logs:${NC}"
echo "  tail -f $LOG_DIR/Zenoh*.log"
echo "  tail -f $LOG_DIR/Gazebo*.log"
echo "  tail -f $LOG_DIR/Agent*.log"
echo ""
echo -e "${BLUE}To monitor topics:${NC}"
echo "  ros2 topic list"
echo "  ros2 topic echo /swarm/agent/amr_0/status"
echo ""
echo -e "${BLUE}To stop all services, press Ctrl+C${NC}"
echo ""

# Keep script running
wait

