#!/bin/bash

# SwarmOS Manual Setup Verification Script

echo "========================================="
echo "SwarmOS Manual Setup Verification"
echo "========================================="
echo ""

PASS_COUNT=0
FAIL_COUNT=0

# Helper functions
pass() {
    echo -e "\033[0;32m✓\033[0m $1"
    ((PASS_COUNT++))
}

fail() {
    echo -e "\033[0;31m✗\033[0m $1"
    ((FAIL_COUNT++))
}

warn() {
    echo -e "\033[1;33m!\033[0m $1"
}

# 1. Check OS
echo "Checking OS..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if grep -q "Ubuntu" /etc/os-release; then
        pass "Ubuntu detected"
    else
        warn "Not Ubuntu, but Linux found"
    fi
else
    fail "Not on Linux (required: Ubuntu 24.04)"
fi

# 2. Check Python
echo ""
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    pass "Python 3 found ($PYTHON_VERSION)"
else
    fail "Python 3 not found"
fi

# 3. Check ROS 2
echo ""
echo "Checking ROS 2..."
if [ -f /opt/ros/jazzy/setup.bash ]; then
    pass "ROS 2 Jazzy setup found"
else
    fail "ROS 2 Jazzy not installed"
fi

# 4. Check virtual environment
echo ""
echo "Checking Python virtual environment..."
if [ -d /opt/swarmos/venv ]; then
    pass "Virtual environment exists"

    if [ -f /opt/swarmos/venv/bin/activate ]; then
        pass "Activation script found"
    else
        fail "Activation script not found"
    fi
else
    warn "Virtual environment not created yet (run: python3 -m venv /opt/swarmos/venv)"
fi

# 5. Check required Python packages
echo ""
echo "Checking Python dependencies..."
if [ -f /opt/swarmos/venv/bin/activate ]; then
    source /opt/swarmos/venv/bin/activate

    packages=("zenoh" "numpy" "scipy" "fastapi" "uvicorn")
    for pkg in "${packages[@]}"; do
        if python3 -c "import ${pkg}" 2>/dev/null; then
            pass "Python package: $pkg"
        else
            warn "Python package missing: $pkg (install with pip)"
        fi
    done

    deactivate
else
    warn "Cannot check Python packages (venv not found)"
fi

# 6. Check Zenoh
echo ""
echo "Checking Zenoh..."
if command -v zenohd &> /dev/null; then
    ZENOH_VERSION=$(zenohd --version 2>&1 | head -1)
    pass "Zenoh router found"
else
    warn "Zenoh not installed (run: cargo install zenoh-cli)"
fi

# 7. Check Node.js (for frontend)
echo ""
echo "Checking Node.js (for frontend)..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    pass "Node.js found ($NODE_VERSION)"
else
    warn "Node.js not found (optional, needed for web frontend)"
fi

if command -v npm &> /dev/null; then
    pass "npm found"
else
    warn "npm not found (optional, needed for web frontend)"
fi

# 8. Check project structure
echo ""
echo "Checking project structure..."
required_dirs=(
    "amr_agents"
    "comms"
    "simulation"
    "tests"
    "docs"
    "web_backend"
    "web_frontend"
)

for dir in "${required_dirs[@]}"; do
    if [ -d "/opt/swarmos/$dir" ]; then
        pass "Directory: $dir"
    else
        fail "Directory missing: $dir"
    fi
done

# 9. Check documentation
echo ""
echo "Checking documentation..."
docs=(
    "MANUAL_SETUP.md"
    "QUICK_REFERENCE.md"
    "REMOVE_DOCKER.md"
    "CLAUDE.md"
)

for doc in "${docs[@]}"; do
    if [ -f "/opt/swarmos/$doc" ]; then
        pass "Documentation: $doc"
    else
        warn "Documentation missing: $doc"
    fi
done

# 10. Check Docker removal
echo ""
echo "Checking Docker cleanup..."
if docker images 2>/dev/null | grep -q "swarmos"; then
    fail "Docker image 'swarmos' still exists (should be removed)"
else
    pass "Docker image 'swarmos' removed"
fi

if docker images 2>/dev/null | grep -q "zenoh"; then
    fail "Docker image 'zenoh' still exists (should be removed)"
else
    pass "Docker image 'zenoh' removed"
fi

# Summary
echo ""
echo "========================================="
echo "Verification Summary"
echo "========================================="
echo -e "Passed: \033[0;32m$PASS_COUNT\033[0m"
echo -e "Failed: \033[0;31m$FAIL_COUNT\033[0m"

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "\033[0;32m✓ All checks passed!\033[0m"
    echo ""
    echo "Next steps:"
    echo "  1. Read QUICK_REFERENCE.md for TL;DR"
    echo "  2. Read MANUAL_SETUP.md for detailed instructions"
    echo "  3. Run: /opt/swarmos/run_all.sh (automated) or"
    echo "     Follow manual terminal instructions in QUICK_REFERENCE.md"
    exit 0
else
    echo -e "\033[0;31m✗ Some checks failed. Please fix issues above.${NC}"
    exit 1
fi
