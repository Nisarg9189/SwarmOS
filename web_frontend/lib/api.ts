import type {
  Robot,
  SimulationStatus,
  WarehouseGraph,
  HealthStatus,
} from '@/types/api'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || ''

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = this.baseUrl ? `${this.baseUrl}${endpoint}` : endpoint
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`)
    }

    return response.json()
  }

  async getSimulationStatus(): Promise<SimulationStatus> {
    return this.request('/api/simulation/status')
  }

  async getRobots(): Promise<Robot[]> {
    return this.request('/api/robots')
  }

  async getRobot(id: string): Promise<Robot> {
    return this.request(`/api/robots/${id}`)
  }

  async getWarehouseGraph(): Promise<WarehouseGraph> {
    return this.request('/api/warehouse/graph')
  }

  async sendRobotGoal(
    robotId: string,
    x: number,
    y: number
  ): Promise<{ status: string }> {
    return this.request(`/api/robots/${robotId}/goal`, {
      method: 'POST',
      body: JSON.stringify({ x, y }),
    })
  }

  // Alias for sendRobotGoal
  async sendGoal(
    robotId: string,
    x: number,
    y: number
  ): Promise<{ status: string }> {
    return this.sendRobotGoal(robotId, x, y)
  }

  async cancelRobotGoal(robotId: string): Promise<{ status: string }> {
    return this.request(`/api/robots/${robotId}/cancel`, {
      method: 'POST',
    })
  }

  async startSimulation(): Promise<{ status: string }> {
    return this.request('/api/simulation/start', {
      method: 'POST',
    })
  }

  async stopSimulation(): Promise<{ status: string }> {
    return this.request('/api/simulation/stop', {
      method: 'POST',
    })
  }

  async startScenario(scenarioName: string): Promise<{ status: string }> {
    return this.request(`/api/scenarios/${scenarioName}/start`, {
      method: 'POST',
    })
  }

  async getScenarios(): Promise<string[]> {
    return this.request('/api/scenarios')
  }

  async getHealth(): Promise<HealthStatus> {
    return this.request('/health')
  }

  async getEvents(limit: number = 100): Promise<any[]> {
    return this.request(`/api/events?limit=${limit}`)
  }

  connectWebSocket(
    onMessage: (data: any) => void,
    onError?: (error: Event) => void,
    onClose?: (event: CloseEvent) => void
  ): () => void {
    const wsUrl = this.baseUrl.replace('http', 'ws') + '/ws'
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('WebSocket connected')
      // Send ping every 30s to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 30000)

      // Store interval ID for cleanup
      ;(ws as any)._pingInterval = pingInterval
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      if (onError) onError(error)
    }

    ws.onclose = (event) => {
      clearInterval((ws as any)._pingInterval)
      console.log('WebSocket closed')
      if (onClose) onClose(event)
    }

    return () => {
      clearInterval((ws as any)._pingInterval)
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }
}

export const apiClient = new ApiClient(API_BASE)
