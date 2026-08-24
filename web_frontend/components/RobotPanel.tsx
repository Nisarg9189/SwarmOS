'use client'

import React from 'react'
import { useSimulationStore } from '@/lib/store'
import { ChevronDown, AlertCircle, Zap } from 'lucide-react'

interface RobotPanelProps {
  onSelectRobot?: (robotId: string | null) => void
}

export function RobotPanel({ onSelectRobot }: RobotPanelProps) {
  const robots = useSimulationStore(state => Array.from(state.robots.values()))
  const selectedRobotId = useSimulationStore(state => state.selectedRobotId)
  const selectedRobot = useSimulationStore(state => state.getSelectedRobot())

  const robotStatusColor = (status: string) => {
    switch (status) {
      case 'idle':
        return 'text-slate-400'
      case 'navigating':
        return 'text-green-400'
      case 'waiting':
        return 'text-yellow-400'
      case 'error':
        return 'text-red-400'
      default:
        return 'text-slate-300'
    }
  }

  const coordinationStatusColor = (status: string) => {
    switch (status) {
      case 'free':
        return 'bg-green-900/30 text-green-300'
      case 'reserved':
        return 'bg-blue-900/30 text-blue-300'
      case 'negotiating':
        return 'bg-yellow-900/30 text-yellow-300'
      case 'deadlock':
        return 'bg-red-900/30 text-red-300'
      default:
        return 'bg-slate-700/30 text-slate-300'
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Robot List */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
          Active Robots ({robots.length})
        </h3>
        <div className="space-y-1 max-h-96 overflow-y-auto">
          {robots.map(robot => (
            <button
              key={robot.id}
              onClick={() => {
                onSelectRobot?.(selectedRobotId === robot.id ? null : robot.id)
              }}
              className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                selectedRobotId === robot.id
                  ? 'bg-blue-900/40 border border-blue-600/50'
                  : 'bg-slate-800/40 hover:bg-slate-700/40 border border-slate-700/30'
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-mono font-medium">{robot.id}</div>
                  <div className={`text-xs ${robotStatusColor(robot.status)}`}>
                    {robot.status}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-slate-400">
                    {robot.pose.x.toFixed(2)}, {robot.pose.y.toFixed(2)}
                  </div>
                  {!robot.is_online && (
                    <AlertCircle className="w-4 h-4 text-red-400 inline" />
                  )}
                </div>
              </div>
            </button>
          ))}
          {robots.length === 0 && (
            <div className="text-slate-400 text-sm py-4 text-center">No robots discovered</div>
          )}
        </div>
      </div>

      {/* Selected Robot Details */}
      {selectedRobot && (
        <div className="border border-slate-700/50 rounded-lg p-3 bg-slate-800/20 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-mono font-semibold text-blue-300">{selectedRobot.id}</h4>
            <div className="flex gap-2">
              {selectedRobot.is_online ? (
                <div className="w-2 h-2 bg-green-500 rounded-full" title="Online" />
              ) : (
                <div className="w-2 h-2 bg-red-500 rounded-full" title="Offline" />
              )}
            </div>
          </div>

          {/* Position & Velocity */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <div className="text-slate-400">Position</div>
              <div className="font-mono text-slate-200">
                ({selectedRobot.pose.x.toFixed(2)}, {selectedRobot.pose.y.toFixed(2)})
              </div>
            </div>
            <div>
              <div className="text-slate-400">Orientation</div>
              <div className="font-mono text-slate-200">
                {(selectedRobot.pose.theta * (180 / Math.PI)).toFixed(1)}°
              </div>
            </div>
            <div>
              <div className="text-slate-400">Velocity</div>
              <div className="font-mono text-slate-200">
                {selectedRobot.velocity.vx.toFixed(2)} m/s
              </div>
            </div>
            <div>
              <div className="text-slate-400">Angular Vel</div>
              <div className="font-mono text-slate-200">
                {selectedRobot.velocity.omega.toFixed(2)} rad/s
              </div>
            </div>
          </div>

          {/* Status Indicators */}
          <div className="space-y-2">
            <div>
              <div className="text-slate-400 text-xs mb-1">Navigation Status</div>
              <div className={`${robotStatusColor(selectedRobot.status)} font-medium text-sm`}>
                {selectedRobot.status}
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs mb-1">Coordination Status</div>
              <div className={`inline-block px-2 py-1 rounded text-xs font-medium ${coordinationStatusColor(selectedRobot.coordination_status)}`}>
                {selectedRobot.coordination_status}
              </div>
            </div>
          </div>

          {/* Current Goal */}
          {selectedRobot.current_goal && (
            <div className="border-t border-slate-700/30 pt-2">
              <div className="text-slate-400 text-xs mb-1">Current Goal</div>
              <div className="font-mono text-sm text-amber-300">
                ({selectedRobot.current_goal.x.toFixed(2)}, {selectedRobot.current_goal.y.toFixed(2)})
              </div>
            </div>
          )}

          {/* Planned Route */}
          {selectedRobot.planned_route && selectedRobot.planned_route.length > 0 && (
            <div className="border-t border-slate-700/30 pt-2">
              <div className="text-slate-400 text-xs mb-2">Planned Route ({selectedRobot.planned_route.length} waypoints)</div>
              <div className="space-y-1 max-h-32 overflow-y-auto text-xs">
                {selectedRobot.planned_route.map((waypoint, idx) => (
                  <div key={idx} className="font-mono text-slate-300 flex justify-between">
                    <span>→ ({waypoint.x.toFixed(1)}, {waypoint.y.toFixed(1)})</span>
                    {waypoint.cell_id && <span className="text-slate-500">{waypoint.cell_id}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Blocked By */}
          {selectedRobot.blocked_by && (
            <div className="border-t border-slate-700/30 pt-2 bg-yellow-900/20 -mx-3 px-3 py-2 rounded flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-yellow-400 flex-shrink-0" />
              <div className="text-sm text-yellow-300">Blocked by {selectedRobot.blocked_by}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
