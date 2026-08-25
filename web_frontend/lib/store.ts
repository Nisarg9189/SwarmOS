import { create } from 'zustand'
import type {
  Robot,
  SimulationStatus,
  WarehouseGraph,
  SimulationEvent,
  RobotStatus,
  CoordinationStatus,
} from '@/types/api'

interface SimulationStore {
  robots: Map<string, Robot>
  simulationStatus: SimulationStatus | null
  warehouseGraph: WarehouseGraph | null
  events: SimulationEvent[]
  selectedRobotId: string | null
  eventFilter: 'all' | 'navigation' | 'coordination' | 'warning' | 'error'

  setRobots: (robots: Robot[]) => void
  setRobot: (robot: Robot) => void
  setSimulationStatus: (status: SimulationStatus) => void
  setWarehouseGraph: (graph: WarehouseGraph) => void
  addEvent: (event: SimulationEvent) => void
  setSelectedRobot: (id: string | null) => void
  setEventFilter: (filter: 'all' | 'navigation' | 'coordination' | 'warning' | 'error') => void

  getRobot: (id: string) => Robot | undefined
  getSelectedRobot: () => Robot | undefined
  getFilteredEvents: () => SimulationEvent[]
  clearEvents: () => void
}

export const useSimulationStore = create<SimulationStore>((set, get) => ({
  robots: new Map(),
  simulationStatus: null,
  warehouseGraph: null,
  events: [],
  selectedRobotId: null,
  eventFilter: 'all',

  setRobots: (robots: Robot[]) => {
    const map = new Map<string, Robot>()
    robots.forEach(robot => {
      map.set(robot.id, robot)
    })
    set({ robots: map })
  },

  setRobot: (robot: Robot) => {
    set(state => {
      const newRobots = new Map(state.robots)
      newRobots.set(robot.id, robot)
      return { robots: newRobots }
    })
  },

  setSimulationStatus: (status: SimulationStatus) => {
    set({ simulationStatus: status })
  },

  setWarehouseGraph: (graph: WarehouseGraph) => {
    set({ warehouseGraph: graph })
  },

  addEvent: (event: SimulationEvent) => {
    set(state => ({
      events: [event, ...state.events].slice(0, 500), // Keep last 500 events
    }))
  },

  setSelectedRobot: (id: string | null) => {
    set({ selectedRobotId: id })
  },

  setEventFilter: (filter) => {
    set({ eventFilter: filter })
  },

  getRobot: (id: string) => {
    return get().robots.get(id)
  },

  getSelectedRobot: () => {
    const selectedId = get().selectedRobotId
    return selectedId ? get().robots.get(selectedId) : undefined
  },

  getFilteredEvents: () => {
    const { events, eventFilter } = get()
    if (eventFilter === 'all') return events
    return events.filter(e => e.type === eventFilter)
  },

  clearEvents: () => {
    set({ events: [] })
  },
}))
