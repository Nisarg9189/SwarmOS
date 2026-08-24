export interface Pose {
  x: number
  y: number
  theta: number
}

export interface Velocity {
  vx: number
  vy: number
  omega: number
}

export interface Waypoint {
  x: number
  y: number
  eta?: number
  etd?: number
  cell_id?: string
}

export interface Robot {
  id: string
  namespace: string
  pose: Pose
  velocity: Velocity
  status: RobotStatus
  coordination_status: CoordinationStatus
  blocked_by?: string | null
  current_goal?: { x: number; y: number } | null
  planned_route: Waypoint[]
  is_online: boolean
  last_update_time?: number
}

export interface SimulationStatus {
  status: 'running' | 'stopped' | 'starting' | 'error'
  sim_time: number
  num_active_robots: number
  num_navigating_robots: number
  current_scenario?: string
  warnings?: string[]
  errors?: string[]
}

export interface WarehouseGraph {
  nodes: Array<{
    id: string
    x: number
    y: number
  }>
  edges: Array<{
    from: string
    to: string
    segment_id?: string
  }>
}

export interface SimulationEvent {
  timestamp: number
  type: 'navigation' | 'coordination' | 'warning' | 'error' | 'all'
  robot_id?: string
  data: Record<string, unknown>
}

export enum RobotStatus {
  Idle = 'idle',
  Navigating = 'navigating',
  Waiting = 'waiting',
  Rerouting = 'rerouting',
  GoalReached = 'goal_reached',
  Error = 'error',
  Offline = 'offline',
}

export enum CoordinationStatus {
  Free = 'free',
  Reserved = 'reserved',
  Negotiating = 'negotiating',
  Deadlock = 'deadlock',
  Offline = 'offline',
}

export interface HealthStatus {
  status: 'ok'
  ros_initialized: boolean
  zenoh_initialized: boolean
  num_robots: number
  num_connected_clients: number
}
