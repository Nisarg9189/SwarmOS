# SwarmOS Deployment Configuration

## Nginx Reverse Proxy Setup

The SwarmOS frontend and backend are exposed via an Nginx reverse proxy for unified public access.

### Configuration

- **Nginx Site:** `/etc/nginx/sites-available/swarmos`
- **Listen Ports:** 9000 (IPv4 and IPv6)
- **Upstream Servers:**
  - Frontend: `127.0.0.1:3000` (Next.js)
  - Backend API: `127.0.0.1:8000` (FastAPI/Uvicorn)

### Routes

```
/              → Frontend (Next.js app)
/api/*         → Backend API (FastAPI)
/ws            → WebSocket endpoint for real-time updates
```

### IPv6 Support

The nginx configuration includes IPv6 listener to enable public access via the VPS's IPv6 address:

```nginx
listen 9000;        # IPv4
listen [::]:9000;   # IPv6
```

**Public Access URL:**
```
http://[2001:41d0:303:ec51::23fa]:9000
```

### Backend Services

- **Frontend:** Next.js 14.2.35 on port 3000
- **Backend API:** FastAPI/Uvicorn on port 8000
- **ROS 2 Environment:** Gazebo warehouse simulation with 3 AMRs
- **Zenoh Router:** Peer discovery and coordination messaging

### Verification

All services verified and operational:
- Frontend: HTTP 200 OK ✓
- Backend API Health: Healthy ✓
- Robot Discovery: 3 active robots ✓
- WebSocket: HTTP 101 Upgrade successful ✓
- Paperclip: Operational on port 80 ✓

**Last Updated:** 2026-08-24
