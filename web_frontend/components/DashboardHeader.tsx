'use client'

import React, { useState } from 'react'
import { useSimulationStore } from '@/lib/store'
import { Play, Pause, RotateCcw } from 'lucide-react'

interface DashboardHeaderProps {
  onStartSimulation?: () => void
  onStopSimulation?: () => void
  onRestartSimulation?: () => void
  isLoading?: boolean
  disabled?: boolean
}

export function DashboardHeader({
  onStartSimulation,
  onStopSimulation,
  onRestartSimulation,
  isLoading = false,
  disabled = false,
}: DashboardHeaderProps) {
  const simulationStatus = useSimulationStore(state => state.simulationStatus)

  const statusColor =
    simulationStatus?.status === 'running'
      ? 'text-green-400'
      : simulationStatus?.status === 'error'
        ? 'text-red-400'
        : 'text-slate-400'

  const statusBgColor =
    simulationStatus?.status === 'running'
      ? 'bg-green-900/20 border-green-700/50'
      : simulationStatus?.status === 'error'
        ? 'bg-red-900/20 border-red-700/50'
        : 'bg-slate-800/20 border-slate-700/50'

  return (
    <div className="border-b border-slate-700/30 pb-4 space-y-4">
      {/* Title */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">
          SwarmOS Simulation Control Center
        </h1>
        <div className={`flex items-center gap-2 px-3 py-1 rounded border text-sm font-medium ${statusBgColor} ${statusColor}`}>
          <div className="w-2 h-2 bg-current rounded-full animate-pulse" />
          {simulationStatus?.status || 'unknown'}
        </div>
      </div>

      {/* Stats Bar */}
      {simulationStatus && (
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-3">
            <div className="text-xs text-slate-400 uppercase tracking-wide">Simulation Time</div>
            <div className="text-lg font-mono font-semibold text-slate-100 mt-1">
              {(simulationStatus.sim_time || 0).toFixed(2)}s
            </div>
          </div>
          <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-3">
            <div className="text-xs text-slate-400 uppercase tracking-wide">Active Robots</div>
            <div className="text-lg font-mono font-semibold text-slate-100 mt-1">
              {simulationStatus.num_active_robots}
            </div>
          </div>
          <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-3">
            <div className="text-xs text-slate-400 uppercase tracking-wide">Navigating</div>
            <div className="text-lg font-mono font-semibold text-green-400 mt-1">
              {simulationStatus.num_navigating_robots}
            </div>
          </div>
          <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-3">
            <div className="text-xs text-slate-400 uppercase tracking-wide">Scenario</div>
            <div className="text-lg font-mono font-semibold text-slate-100 mt-1">
              {simulationStatus.current_scenario || 'none'}
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2">
        <button
          onClick={onStartSimulation}
          disabled={disabled || isLoading || simulationStatus?.status === 'running'}
          title={disabled ? 'ROS 2 connection required' : ''}
          className="flex items-center gap-2 px-4 py-2 bg-green-900/40 border border-green-700/50 hover:bg-green-900/60 disabled:opacity-50 disabled:cursor-not-allowed rounded text-green-300 font-medium transition-colors"
        >
          <Play className="w-4 h-4" />
          Start
        </button>
        <button
          onClick={onStopSimulation}
          disabled={disabled || isLoading || simulationStatus?.status !== 'running'}
          title={disabled ? 'ROS 2 connection required' : ''}
          className="flex items-center gap-2 px-4 py-2 bg-red-900/40 border border-red-700/50 hover:bg-red-900/60 disabled:opacity-50 disabled:cursor-not-allowed rounded text-red-300 font-medium transition-colors"
        >
          <Pause className="w-4 h-4" />
          Stop
        </button>
        <button
          onClick={onRestartSimulation}
          disabled={disabled || isLoading}
          title={disabled ? 'ROS 2 connection required' : ''}
          className="flex items-center gap-2 px-4 py-2 bg-blue-900/40 border border-blue-700/50 hover:bg-blue-900/60 disabled:opacity-50 disabled:cursor-not-allowed rounded text-blue-300 font-medium transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          Restart
        </button>
      </div>

      {/* Warnings/Errors */}
      {simulationStatus?.errors && simulationStatus.errors.length > 0 && (
        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-3 text-red-300 text-sm">
          {simulationStatus.errors[0]}
        </div>
      )}
      {simulationStatus?.warnings && simulationStatus.warnings.length > 0 && (
        <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-3 text-yellow-300 text-sm">
          {simulationStatus.warnings[0]}
        </div>
      )}
    </div>
  )
}
