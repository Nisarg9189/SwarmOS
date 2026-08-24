# Remove Docker Images - SwarmOS

This document provides commands to remove all Docker images and containers related to SwarmOS and Zenoh.

## Quick Command

```bash
#!/bin/bash
# Stop and remove all running containers
docker-compose -f docker/docker-compose.yml down --volumes

# Remove all SwarmOS images
docker rmi swarmos:dev swarmos:sim swarmos-qa-test:latest -f 2>/dev/null || true
docker rmi swarmos:base -f 2>/dev/null || true

# Remove Zenoh image
docker rmi eclipse/zenoh:latest -f 2>/dev/null || true

# Remove dangling images
docker image prune -f

# Verify
docker images | grep -E "swarmos|zenoh" && echo "Some images still exist" || echo "All images removed successfully"
```

---

## Step-by-Step Commands

### Step 1: Stop Running Containers

```bash
# Stop Docker Compose services
cd /opt/swarmos
docker-compose -f docker/docker-compose.yml down --volumes

# Verify no swarmos containers are running
docker ps | grep -E "swarmos|zenoh|gazebo|agent" && echo "Some containers still running" || echo "All containers stopped"
```

### Step 2: Remove Docker Images

```bash
# Remove SwarmOS development image
docker rmi swarmos:dev -f 2>/dev/null || echo "swarmos:dev not found"

# Remove SwarmOS simulation image
docker rmi swarmos:sim -f 2>/dev/null || echo "swarmos:sim not found"

# Remove SwarmOS QA test image
docker rmi swarmos-qa-test:latest -f 2>/dev/null || echo "swarmos-qa-test:latest not found"

# Remove SwarmOS base image (if built separately)
docker rmi swarmos:base -f 2>/dev/null || echo "swarmos:base not found"

# Remove Zenoh router image
docker rmi eclipse/zenoh:latest -f 2>/dev/null || echo "eclipse/zenoh:latest not found"
```

### Step 3: Clean Up Dangling Images and Build Cache

```bash
# Remove all dangling images (orphaned layers)
docker image prune -f

# Optional: Remove all unused images (not just dangling)
docker image prune -a -f

# Optional: Remove Docker build cache
docker builder prune -f
```

### Step 4: Verify Removal

```bash
# List remaining Docker images
docker images | grep -E "swarmos|zenoh"

# If output is empty, all images have been removed successfully
# Expected output: (no matching rows)
```

---

## Alternative: One-Liner Script

```bash
docker-compose -f /opt/swarmos/docker/docker-compose.yml down --volumes 2>/dev/null; \
docker rmi swarmos:dev swarmos:sim swarmos-qa-test:latest swarmos:base eclipse/zenoh:latest -f 2>/dev/null; \
docker image prune -f; \
docker images | grep -E "swarmos|zenoh" || echo "✓ All SwarmOS and Zenoh images removed"
```

---

## Storage Recovered

Expected disk space freed (approximate):

- `swarmos:dev` — ~6.87 GB
- `swarmos:sim` — ~6.87 GB (often same as :dev)
- `swarmos-qa-test:latest` — ~6.87 GB (often same as :dev)
- `eclipse/zenoh:latest` — ~51.9 MB
- **Total (with deduplication):** ~7-8 GB

---

## Automation Script

Create `/opt/swarmos/cleanup.sh`:

```bash
#!/bin/bash
set -e

echo "=== SwarmOS Docker Cleanup ==="
echo ""

# Stop containers
echo "1. Stopping Docker Compose services..."
cd /opt/swarmos
docker-compose -f docker/docker-compose.yml down --volumes 2>/dev/null || echo "   (No running services)"
echo "   ✓ Services stopped"
echo ""

# Remove images
echo "2. Removing Docker images..."
docker rmi swarmos:dev -f 2>/dev/null && echo "   ✓ Removed swarmos:dev" || echo "   ✗ swarmos:dev not found"
docker rmi swarmos:sim -f 2>/dev/null && echo "   ✓ Removed swarmos:sim" || echo "   ✗ swarmos:sim not found"
docker rmi swarmos-qa-test:latest -f 2>/dev/null && echo "   ✓ Removed swarmos-qa-test:latest" || echo "   ✗ swarmos-qa-test:latest not found"
docker rmi swarmos:base -f 2>/dev/null && echo "   ✓ Removed swarmos:base" || echo "   ✗ swarmos:base not found"
docker rmi eclipse/zenoh:latest -f 2>/dev/null && echo "   ✓ Removed eclipse/zenoh:latest" || echo "   ✗ eclipse/zenoh:latest not found"
echo ""

# Prune dangling images
echo "3. Cleaning up dangling images..."
docker image prune -f > /dev/null
echo "   ✓ Dangling images removed"
echo ""

# Verify
echo "4. Verification:"
REMAINING=$(docker images | grep -E "swarmos|zenoh" | wc -l)
if [ $REMAINING -eq 0 ]; then
  echo "   ✓ All SwarmOS and Zenoh images successfully removed"
  echo ""
  echo "You can now run SwarmOS using the manual setup commands."
  echo "See MANUAL_SETUP.md for details."
else
  echo "   ⚠ Warning: Found $REMAINING remaining images related to SwarmOS/Zenoh"
  docker images | grep -E "swarmos|zenoh"
fi
echo ""
echo "=== Cleanup Complete ==="
```

Make it executable:

```bash
chmod +x /opt/swarmos/cleanup.sh
./cleanup.sh
```

---

## Important Notes

1. **Irreversible:** Removing images deletes them permanently. Rebuild with `docker-compose build` if needed.
2. **Volumes:** The `--volumes` flag removes Docker volumes (data persisted from containers).
3. **Dependencies:** If other services depend on these images, they will break.
4. **Selective Removal:** To keep some images, omit them from the `docker rmi` command.

---

## After Cleanup

To verify Docker is clean:

```bash
# No swarmos or zenoh images
docker images | grep -i swarmos
docker images | grep -i zenoh

# No related containers
docker ps -a | grep -i swarmos
docker ps -a | grep -i zenoh

# Free up additional space (optional)
docker system prune -a -f
```

---

## Reverting (Rebuilding Docker)

If you need to rebuild Docker images later:

```bash
cd /opt/swarmos
docker-compose -f docker/docker-compose.yml build
docker-compose -f docker/docker-compose.yml up
```

---

**Next:** Follow `MANUAL_SETUP.md` to run SwarmOS without Docker.
