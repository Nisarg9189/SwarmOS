# SwarmOS Simulation Control Center - Web Frontend

Modern, real-time dashboard for controlling and monitoring the SwarmOS multi-robot warehouse simulation.

## Features

- **Live Warehouse Visualization**: Interactive 2D map showing robot positions, orientation, and planned routes
- **Real-time Robot Monitoring**: See all robots with current status, pose, velocity, and coordination state
- **Simulation Controls**: Start, stop, and restart simulations with scenario selection
- **Event Streaming**: Real-time event log with filtering by event type
- **Safe Goal Dispatch**: Send navigation goals through the proper coordination architecture
- **Dynamic Robot Discovery**: Automatically discovers and tracks all robots in the simulation
- **WebSocket Integration**: Real-time updates without polling

## Technology Stack

- **Next.js 14** - React framework with server/client components
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **Zustand** - Lightweight state management
- **React** - UI components
- **Lucide React** - Icon library

## Getting Started

### Prerequisites

- Node.js 18+ and npm or yarn
- Backend service running on `http://localhost:8000` (or configure via `NEXT_PUBLIC_API_BASE`)

### Installation

```bash
# Install dependencies
npm install
# or
yarn install
```

### Development

```bash
# Start development server
npm run dev
# or
yarn dev
```

The frontend will be available at `http://localhost:3000`

### Production Build

```bash
# Build for production
npm run build

# Start production server
npm run start
```

## Configuration

Set the backend API URL via environment variable:

```bash
# .env.local
NEXT_PUBLIC_API_BASE=http://your-backend:8000
```

Or pass it at build time:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build
```

## Project Structure

```
web_frontend/
├── app/                      # Next.js app directory
│   ├── page.tsx             # Main dashboard
│   ├── layout.tsx           # Root layout
│   └── globals.css          # Global styles
├── components/              # Reusable components
│   ├── DashboardHeader.tsx  # Header with controls
│   ├── WarehouseVisualization.tsx  # Map visualization
│   ├── RobotPanel.tsx       # Robot list & details
│   ├── EventLog.tsx         # Event stream
│   └── ScenarioControl.tsx  # Scenario selector
├── lib/
│   ├── api.ts              # API client
│   └── store.ts            # Zustand state management
├── types/
│   └── api.ts              # TypeScript types
├── package.json
├── tsconfig.json
├── next.config.js
├── tailwind.config.ts
└── postcss.config.js
```

## Architecture

### Component Hierarchy

```
Dashboard (page.tsx)
├── DashboardHeader
├── WarehouseVisualization
│   └── Canvas-based 2D rendering
├── RobotPanel
│   └── Robot list + detail view
├── EventLog
│   └── Real-time event stream
└── ScenarioControl
    └── Scenario selector
```

### State Management (Zustand)

- **robots**: Map of active robots
- **simulationStatus**: Current simulation state
- **warehouseGraph**: Warehouse topology
- **events**: Event log with filtering
- **selectedRobotId**: Currently selected robot

### Real-time Communication

- **REST API**: Fetch initial state and send actions
- **WebSocket**: Receive real-time updates (robot poses, events)
- **Polling**: 500ms refresh cycle for current state

## API Integration

The frontend communicates with the backend via:

```
GET  /api/simulation/status       - Get simulation state
GET  /api/robots                  - Get all robots
GET  /api/robots/{id}             - Get robot details
GET  /api/warehouse/graph         - Get topology
POST /api/robots/{id}/goal        - Send navigation goal
POST /api/robots/{id}/cancel      - Cancel navigation
POST /api/scenarios/{name}/start  - Start scenario
GET  /api/scenarios               - List available scenarios
GET  /api/events                  - Get event history
WS   /ws                          - WebSocket for live updates
```

## Warehouse Visualization

The interactive map features:

- **Robot Rendering**: Color-coded by status (idle=orange, navigating=green, selected=blue)
- **Current Goal**: Yellow dashed line and marker
- **Planned Route**: Purple dashed line showing waypoints
- **Warehouse Graph**: Gray nodes and edges from topology
- **Interactive Controls**:
  - Click robots to inspect details
  - Scroll to zoom
  - Drag to pan
  - Real-time updates at 10 Hz

## Development Notes

### Adding New Components

1. Create component in `components/` directory
2. Use TypeScript for type safety
3. Integrate with Zustand store for state
4. Use Tailwind CSS for styling
5. Import Lucide icons as needed

### Extending State

Update `types/api.ts` and `lib/store.ts` to add new state properties.

### API Error Handling

The API client gracefully handles:
- Network failures (reconnects WebSocket)
- Missing robots (empty list)
- Connection loss (falls back to polling)

## Performance Considerations

- **Canvas Rendering**: 10 Hz update rate for smooth visualization
- **Event Log**: Limited to 500 recent events to prevent memory issues
- **Polling**: 500ms interval balances freshness with server load
- **WebSocket**: Reduces polling overhead for real-time updates

## Future Enhancements

- 3D visualization with Gazebo camera streams
- Manual goal selection on map click
- Coordination state visualization
- Network topology diagrams
- Historical data playback
- Multi-user collaboration

## Troubleshooting

### Backend not connecting
- Ensure backend is running on configured `NEXT_PUBLIC_API_BASE`
- Check CORS headers from backend
- Verify network connectivity

### Robots not appearing
- Check backend is discovering robots from ROS2
- Verify warehouse graph is loaded
- Check browser console for API errors

### Slow performance
- Reduce event log size
- Lower polling frequency if many robots
- Check browser performance tab

## License

Part of the SwarmOS multi-robot warehouse simulation project.
