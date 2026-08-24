'use client'

import React, { useState } from 'react'
import { useSimulationStore } from '@/lib/store'
import { apiClient } from '@/lib/api'

interface GoalConfirmDialogProps {
  isOpen: boolean
  robotId: string | null
  goalX: number
  goalY: number
  onClose: () => void
  onSuccess?: () => void
}

export function GoalConfirmDialog({
  isOpen,
  robotId,
  goalX,
  goalY,
  onClose,
  onSuccess,
}: GoalConfirmDialogProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const robots = useSimulationStore(state => Array.from(state.robots.values()))
  const addEvent = useSimulationStore(state => state.addEvent)

  if (!isOpen || !robotId) {
    return null
  }

  const robot = robots.find(r => r.id === robotId)

  const handleConfirm = async () => {
    if (!robot) return

    setIsLoading(true)
    setError(null)

    try {
      // Send goal to backend
      await apiClient.sendGoal(robotId, goalX, goalY)

      // Add event to log
      addEvent({
        timestamp: Date.now() / 1000,
        type: 'navigation',
        robot_id: robotId,
        data: {
          event_type: 'goal_sent',
          goal: { x: goalX, y: goalY },
          message: `Goal sent to ${robotId}`,
        },
      })

      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send goal')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCancel = () => {
    setError(null)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-slate-800 border border-slate-600 rounded-lg shadow-xl max-w-sm w-full mx-4">
        {/* Header */}
        <div className="border-b border-slate-600 px-6 py-4">
          <h2 className="text-lg font-semibold text-white">Send Navigation Goal</h2>
        </div>

        {/* Content */}
        <div className="px-6 py-4 space-y-4">
          {/* Robot info */}
          <div className="bg-slate-700 rounded p-3">
            <div className="text-sm text-slate-400">Robot:</div>
            <div className="text-lg font-semibold text-white">{robot?.id}</div>
            <div className="text-sm text-slate-400 mt-1">
              Current Position: ({robot?.pose.x.toFixed(2)}, {robot?.pose.y.toFixed(2)})
            </div>
          </div>

          {/* Goal info */}
          <div className="bg-slate-700 rounded p-3">
            <div className="text-sm text-slate-400">Goal Location:</div>
            <div className="text-lg font-semibold text-white">
              ({goalX.toFixed(2)}, {goalY.toFixed(2)})
            </div>
            <div className="text-sm text-slate-400 mt-1">
              Distance: {(Math.sqrt(Math.pow(goalX - (robot?.pose.x || 0), 2) + Math.pow(goalY - (robot?.pose.y || 0), 2))).toFixed(2)}m
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div className="bg-red-900/20 border border-red-600 rounded p-3">
              <div className="text-sm text-red-200">{error}</div>
            </div>
          )}

          {/* Info message */}
          <div className="bg-blue-900/20 border border-blue-600 rounded p-3">
            <div className="text-sm text-blue-200">
              The goal will be dispatched through the coordination system, ensuring safe navigation and preventing conflicts with other robots.
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-600 px-6 py-4 flex gap-3 justify-end">
          <button
            onClick={handleCancel}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-slate-300 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded transition-colors flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <span className="animate-spin">⏳</span>
                Sending...
              </>
            ) : (
              'Send Goal'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
