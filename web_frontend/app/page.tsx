'use client'

import React, { useEffect, useState, useCallback } from 'react'
import { DashboardHeader } from '@/components/DashboardHeader'
import { WarehouseVisualization } from '@/components/WarehouseVisualization'
import { RobotPanel } from '@/components/RobotPanel'
import { EventLog } from '@/components/EventLog'
import { ScenarioControl } from '@/components/ScenarioControl'
import { useSimulationStore } from '@/lib/store'
import { apiClient } from '@/lib/api'
import type { Robot, SimulationStatus, WarehouseGraph, SimulationEvent } from '@/types/api'

export default function Dashboard() {
  const [isLoading, setIsLoading] = useState(false)
  const [connected, setConnected] = useState(false)
  const [ros2Connected, setRos2Connected] = useState(true)
  const [healthError, setHealthError] = useState<string | null>(null)

  const setRobots = useSimulationStore(state => state.setRobots)
  const setSimulationStatus = useSimulationStore(state => state.setSimulationStatus)
  const setWarehouseGraph = useSimulationStore(state => state.setWarehouseGraph)
  const setSelectedRobot = useSimulationStore(state => state.setSelectedRobot)
  const addEvent = useSimulationStore(state => state.addEvent)

  // Check health on startup
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch('/api/health')
        if (!response.ok) {
          setHealthError('Backend health check failed')
          setRos2Connected(false)
          return
        }
        const health = await response.json()
        if (!health.services?.ros2?.available) {
          setHealthError('ROS 2 is not connected. Please verify ROS 2 environment is set up correctly.')
          setRos2Connected(false)
        } else {
          setHealthError(null)
          setRos2Connected(true)
        }
      } catch (error) {
        setHealthError('Unable to reach backend. Please verify the backend service is running.')
        setRos2Connected(false)
      }
    }

    checkHealth()
  }, [])

  // Initialize API connection and data
  useEffect(() => {
    let wsUnsubscribe: (() => void) | null = null
    let reconnectTimeout: NodeJS.Timeout | null = null

    const connectToApi = async () => {
      try {
        // Fetch initial data
        const [status, robots, graph] = await Promise.all([
          apiClient.getSimulationStatus().catch(() => null),
          apiClient.getRobots().catch(() => []),
          apiClient.getWarehouseGraph().catch(() => null),
        ])

        if (status) setSimulationStatus(status)
        if (robots.length > 0) setRobots(robots)
        if (graph) setWarehouseGraph(graph)

        // Connect WebSocket for real-time updates
        wsUnsubscribe = apiClient.connectWebSocket(
          (data: any) => {
            if (data.type === 'robot_state') {
              const robot = data.data as Robot
              useSimulationStore.setState(state => {
                const newRobots = new Map(state.robots)
                newRobots.set(robot.id, robot)
                return { robots: newRobots }
              })
            } else if (data.type === 'simulation_status') {
              setSimulationStatus(data.data as SimulationStatus)
            } else if (data.type === 'coordination_event' || data.type === 'navigation_event') {
              addEvent({
                timestamp: Date.now() / 1000,
                type: data.type as any,
                robot_id: data.data?.robot_id,
                data: data.data,
              } as SimulationEvent)
            }
          },
          () => {
            setConnected(false)
            scheduleReconnect()
          },
          () => {
            setConnected(false)
            scheduleReconnect()
          }
        )

        setConnected(true)
      } catch (error) {
        console.error('Failed to connect to API:', error)
        scheduleReconnect()
      }
    }

    const scheduleReconnect = () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      reconnectTimeout = setTimeout(connectToApi, 3000)
    }

    connectToApi()

    return () => {
      if (wsUnsubscribe) wsUnsubscribe()
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
    }
  }, [])

  // Poll for simulation updates every 500ms
  useEffect(() => {
    const pollInterval = setInterval(async () => {
      try {
        const [status, robots] = await Promise.all([
          apiClient.getSimulationStatus().catch(() => null),
          apiClient.getRobots().catch(() => null),
        ])
        if (status) setSimulationStatus(status)
        if (robots) setRobots(robots)
      } catch (error) {
        console.debug('Poll error:', error)
      }
    }, 500)

    return () => clearInterval(pollInterval)
  }, [])

  const handleStartSimulation = useCallback(async () => {
    setIsLoading(true)
    try {
      await apiClient.startSimulation()
      const status = await apiClient.getSimulationStatus()
      setSimulationStatus(status)
    } catch (error) {
      console.error('Failed to start simulation:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleStopSimulation = useCallback(async () => {
    setIsLoading(true)
    try {
      await apiClient.stopSimulation()
      const status = await apiClient.getSimulationStatus()
      setSimulationStatus(status)
    } catch (error) {
      console.error('Failed to stop simulation:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleRestartSimulation = useCallback(async () => {
    setIsLoading(true)
    try {
      await apiClient.stopSimulation()
      await new Promise(resolve => setTimeout(resolve, 500))
      await apiClient.startSimulation()
      const status = await apiClient.getSimulationStatus()
      setSimulationStatus(status)
      setSelectedRobot(null)
    } catch (error) {
      console.error('Failed to restart simulation:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleStartScenario = useCallback(async (scenarioName: string) => {
    setIsLoading(true)
    try {
      await apiClient.startScenario(scenarioName)
      const status = await apiClient.getSimulationStatus()
      setSimulationStatus(status)
    } catch (error) {
      console.error('Failed to start scenario:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleSelectRobot = useCallback((robotId: string | null) => {
    setSelectedRobot(robotId)
  }, [])

  const handleRobotClick = useCallback((robotId: string) => {
    setSelectedRobot(robotId)
  }, [])

  return (
    <div className="min-h-screen bg-darker">
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <DashboardHeader
          onStartSimulation={handleStartSimulation}
          onStopSimulation={handleStopSimulation}
          onRestartSimulation={handleRestartSimulation}
          isLoading={isLoading}
          disabled={!ros2Connected}
        />

        {/* ROS 2 Connection Error */}
        {!ros2Connected && healthError && (
          <div className="mt-4 bg-red-900/20 border border-red-700/50 rounded-lg p-4 text-red-300 text-sm flex items-start gap-3">
            <div className="w-2 h-2 bg-red-500 rounded-full flex-shrink-0 mt-1.5" />
            <div className="flex-1">
              <p className="font-semibold">ROS 2 Connection Failed</p>
              <p className="text-red-400 text-xs mt-1">{healthError}</p>
            </div>
          </div>
        )}

        {/* Connection Status */}
        {!connected && (
          <div className="mt-4 bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-3 text-yellow-300 text-sm flex items-center gap-2">
            <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />
            Connecting to simulation backend...
          </div>
        )}

        {/* Main Content */}
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Sidebar */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            {/* Warehouse Visualization */}
            <div className="bg-slate-800/20 border border-slate-700/30 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-slate-200 mb-4">Warehouse Map</h2>
              <WarehouseVisualization onRobotClick={handleRobotClick} />
            </div>

            {/* Event Log */}
            <div className="bg-slate-800/20 border border-slate-700/30 rounded-lg p-4 flex flex-col h-80">
              <h2 className="text-lg font-semibold text-slate-200 mb-4">Event Log</h2>
              <EventLog />
            </div>
          </div>

          {/* Right Sidebar */}
          <div className="flex flex-col gap-6">
            {/* Robot Panel */}
            <div className="bg-slate-800/20 border border-slate-700/30 rounded-lg p-4 flex flex-col max-h-96">
              <h2 className="text-lg font-semibold text-slate-200 mb-3">Robots</h2>
              <RobotPanel onSelectRobot={handleSelectRobot} />
            </div>

            {/* Scenario Control */}
            <div className="bg-slate-800/20 border border-slate-700/30 rounded-lg p-4">
              <ScenarioControl
                onStartScenario={handleStartScenario}
                isLoading={isLoading}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
