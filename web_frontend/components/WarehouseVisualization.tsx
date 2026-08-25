'use client'

import React, { useRef, useEffect, useState } from 'react'
import { useSimulationStore } from '@/lib/store'
import { GoalConfirmDialog } from './GoalConfirmDialog'
import type { Robot, WarehouseGraph } from '@/types/api'

interface VisualizationProps {
  onRobotClick?: (robotId: string) => void
}

interface PendingGoal {
  robotId: string
  x: number
  y: number
}

const CANVAS_WIDTH = 1200
const CANVAS_HEIGHT = 800
const SCALE = 40 // pixels per meter

export function WarehouseVisualization({ onRobotClick }: VisualizationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [goalDialog, setGoalDialog] = useState<PendingGoal | null>(null)

  const robots = useSimulationStore(state => Array.from(state.robots.values()))
  const warehouseGraph = useSimulationStore(state => state.warehouseGraph)
  const selectedRobotId = useSimulationStore(state => state.selectedRobotId)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear canvas
    ctx.fillStyle = '#1e293b'
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)

    // Save context state
    ctx.save()

    // Apply transformations
    ctx.translate(CANVAS_WIDTH / 2 + pan.x, CANVAS_HEIGHT / 2 + pan.y)
    ctx.scale(SCALE * zoom, SCALE * zoom)

    // Draw warehouse graph (nodes and edges)
    if (warehouseGraph) {
      // Draw edges
      ctx.strokeStyle = '#475569'
      ctx.lineWidth = 0.1
      warehouseGraph.edges.forEach(edge => {
        const fromNode = warehouseGraph.nodes.find(n => n.id === edge.from)
        const toNode = warehouseGraph.nodes.find(n => n.id === edge.to)
        if (fromNode && toNode) {
          ctx.beginPath()
          ctx.moveTo(fromNode.x, fromNode.y)
          ctx.lineTo(toNode.x, toNode.y)
          ctx.stroke()
        }
      })

      // Draw nodes
      ctx.fillStyle = '#64748b'
      warehouseGraph.nodes.forEach(node => {
        ctx.beginPath()
        ctx.arc(node.x, node.y, 0.15, 0, 2 * Math.PI)
        ctx.fill()
      })
    }

    // Draw robots
    robots.forEach(robot => {
      const isSelected = robot.id === selectedRobotId
      const isNavigating = robot.status === 'navigating'
      const isOnline = robot.is_online

      // Robot body
      ctx.save()
      ctx.translate(robot.pose.x, robot.pose.y)
      ctx.rotate(robot.pose.theta)

      if (!isOnline) {
        ctx.fillStyle = '#64748b'
      } else if (isNavigating) {
        ctx.fillStyle = '#22c55e'
      } else if (isSelected) {
        ctx.fillStyle = '#0ea5e9'
      } else {
        ctx.fillStyle = '#f97316'
      }

      ctx.fillRect(-0.25, -0.25, 0.5, 0.5)

      // Robot direction indicator
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0.15, -0.1, 0.2, 0.2)

      ctx.restore()

      // Draw selection ring
      if (isSelected) {
        ctx.strokeStyle = '#0ea5e9'
        ctx.lineWidth = 0.15
        ctx.beginPath()
        ctx.arc(robot.pose.x, robot.pose.y, 0.6, 0, 2 * Math.PI)
        ctx.stroke()
      }

      // Draw current goal
      if (robot.current_goal) {
        ctx.strokeStyle = '#f59e0b'
        ctx.lineWidth = 0.1
        ctx.setLineDash([0.2, 0.1])
        ctx.beginPath()
        ctx.moveTo(robot.pose.x, robot.pose.y)
        ctx.lineTo(robot.current_goal.x, robot.current_goal.y)
        ctx.stroke()
        ctx.setLineDash([])

        // Goal marker
        ctx.fillStyle = '#f59e0b'
        ctx.beginPath()
        ctx.arc(robot.current_goal.x, robot.current_goal.y, 0.2, 0, 2 * Math.PI)
        ctx.fill()
      }

      // Draw planned route
      if (robot.planned_route && robot.planned_route.length > 0) {
        ctx.strokeStyle = '#8b5cf6'
        ctx.lineWidth = 0.08
        ctx.setLineDash([0.15, 0.1])
        ctx.beginPath()
        ctx.moveTo(robot.pose.x, robot.pose.y)
        robot.planned_route.forEach(waypoint => {
          ctx.lineTo(waypoint.x, waypoint.y)
        })
        ctx.stroke()
        ctx.setLineDash([])
      }

      // Robot label
      ctx.restore()
      ctx.save()
      ctx.translate(CANVAS_WIDTH / 2 + pan.x, CANVAS_HEIGHT / 2 + pan.y)

      const screenX =
        (robot.pose.x * SCALE * zoom + (CANVAS_WIDTH / 2 + pan.x)) / (SCALE * zoom)
      const screenY =
        (robot.pose.y * SCALE * zoom + (CANVAS_HEIGHT / 2 + pan.y)) / (SCALE * zoom)

      ctx.fillStyle = '#e2e8f0'
      ctx.font = '12px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(robot.id, screenX, screenY - 25)

      ctx.restore()
    })

    // Restore context
    ctx.restore()
  }, [robots, warehouseGraph, selectedRobotId, zoom, pan])

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging) return
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    })
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  // Attached via a native (non-passive) listener below, not React's onWheel,
  // because React attaches wheel/touch listeners as passive by default, which
  // silently ignores preventDefault() and spams the console with warnings.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const wheelHandler = (e: WheelEvent) => {
      e.preventDefault()
      const delta = e.deltaY > 0 ? 0.9 : 1.1
      setZoom(prev => Math.max(0.5, Math.min(3, prev * delta)))
    }

    canvas.addEventListener('wheel', wheelHandler, { passive: false })
    return () => canvas.removeEventListener('wheel', wheelHandler)
  }, [])

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = (e.clientX - rect.left - (CANVAS_WIDTH / 2 + pan.x)) / (SCALE * zoom)
    const y = (e.clientY - rect.top - (CANVAS_HEIGHT / 2 + pan.y)) / (SCALE * zoom)

    // Check if click is near any robot
    let clickedRobot = false
    robots.forEach(robot => {
      const dist = Math.sqrt(
        Math.pow(robot.pose.x - x, 2) + Math.pow(robot.pose.y - y, 2)
      )
      if (dist < 0.5) {
        onRobotClick?.(robot.id)
        clickedRobot = true
      }
    })

    // If no robot clicked and a robot is selected, treat as goal selection
    if (!clickedRobot && selectedRobotId) {
      setGoalDialog({ robotId: selectedRobotId, x, y })
    }
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <canvas
          ref={canvasRef}
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          className="border border-slate-600 rounded-lg cursor-grab active:cursor-grabbing"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onClick={handleCanvasClick}
        />
        <div className="text-sm text-slate-400 flex justify-between px-2">
          <span>
            Click robots to inspect • {selectedRobotId && 'Click map to send goal'} • Scroll to zoom • Drag to pan
          </span>
          <span>Zoom: {(zoom * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Goal confirmation dialog */}
      {goalDialog && (
        <GoalConfirmDialog
          isOpen={!!goalDialog}
          robotId={goalDialog.robotId}
          goalX={goalDialog.x}
          goalY={goalDialog.y}
          onClose={() => setGoalDialog(null)}
          onSuccess={() => {
            setGoalDialog(null)
            // Goal sent successfully
          }}
        />
      )}
    </>
  )
}
