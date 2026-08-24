'use client'

import React from 'react'
import { useSimulationStore } from '@/lib/store'
import { AlertCircle, Info, Zap } from 'lucide-react'

export function EventLog() {
  const events = useSimulationStore(state => state.getFilteredEvents())
  const eventFilter = useSimulationStore(state => state.eventFilter)
  const setEventFilter = useSimulationStore(state => state.setEventFilter)
  const clearEvents = useSimulationStore(state => state.clearEvents)

  const filterOptions: Array<'all' | 'navigation' | 'coordination' | 'warning' | 'error'> = [
    'all',
    'navigation',
    'coordination',
    'warning',
    'error',
  ]

  const getEventIcon = (type: string) => {
    if (type === 'warning') return <AlertCircle className="w-4 h-4 text-yellow-400" />
    if (type === 'error') return <AlertCircle className="w-4 h-4 text-red-400" />
    if (type === 'coordination') return <Zap className="w-4 h-4 text-purple-400" />
    return <Info className="w-4 h-4 text-blue-400" />
  }

  const getEventColor = (type: string) => {
    if (type === 'warning') return 'text-yellow-300'
    if (type === 'error') return 'text-red-300'
    if (type === 'coordination') return 'text-purple-300'
    return 'text-slate-300'
  }

  const getEventBg = (type: string) => {
    if (type === 'warning') return 'bg-yellow-900/10'
    if (type === 'error') return 'bg-red-900/10'
    if (type === 'coordination') return 'bg-purple-900/10'
    return 'bg-slate-800/10'
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Header and Filters */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
            Event Log ({events.length})
          </h3>
          <button
            onClick={clearEvents}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            Clear
          </button>
        </div>
        <div className="flex gap-1 flex-wrap">
          {filterOptions.map(filter => (
            <button
              key={filter}
              onClick={() => setEventFilter(filter)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors capitalize ${
                eventFilter === filter
                  ? 'bg-blue-900/50 text-blue-300'
                  : 'bg-slate-800/30 text-slate-400 hover:bg-slate-700/30'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      {/* Events List */}
      <div className="flex-1 overflow-y-auto space-y-1 min-h-0">
        {events.length === 0 ? (
          <div className="text-center text-slate-500 text-sm py-8">
            {eventFilter === 'all'
              ? 'No events yet'
              : `No ${eventFilter} events`}
          </div>
        ) : (
          events.map((event, idx) => (
            <div
              key={idx}
              className={`p-2 rounded text-xs border border-slate-700/20 ${getEventBg(event.type)}`}
            >
              <div className="flex items-start gap-2">
                <div className="flex-shrink-0 mt-0.5">
                  {getEventIcon(event.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`font-medium ${getEventColor(event.type)}`}>
                    {event.type === 'navigation'
                      ? `Navigation: ${event.data?.event_type || 'goal_update'}`
                      : event.type === 'coordination'
                        ? `Coordination: ${event.data?.event_type || 'update'}`
                        : event.type === 'warning'
                          ? `Warning: ${event.data?.message || 'unknown'}`
                          : event.type === 'error'
                            ? `Error: ${event.data?.message || 'unknown'}`
                            : event.type}
                  </div>
                  {(() => {
                    const data = event.data as any
                    if (data && typeof data === 'object' && 'details' in data) {
                      const details = typeof data.details === 'string'
                        ? data.details
                        : JSON.stringify(data.details).substring(0, 80)
                      return (
                        <div className="text-slate-400 text-xs mt-1 break-words">
                          {details}
                        </div>
                      )
                    }
                    return null
                  })()}
                  {event.robot_id && (
                    <div className="text-slate-500 text-xs mt-1">
                      {event.robot_id}
                    </div>
                  )}
                </div>
                <div className="text-slate-500 text-xs flex-shrink-0 whitespace-nowrap">
                  {new Date(event.timestamp * 1000).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
