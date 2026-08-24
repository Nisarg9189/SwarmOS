'use client'

import React, { useState } from 'react'
import { Play } from 'lucide-react'

interface ScenarioControlProps {
  onStartScenario?: (scenarioName: string) => void
  isLoading?: boolean
}

const SCENARIOS = [
  { name: 'normal_ops', description: 'Standard warehouse operations' },
  { name: 'overlapping_paths', description: 'Robots with conflicting routes' },
  { name: 'blocked_aisle', description: 'Aisle blocked, alternate routing required' },
  { name: 'robot_failure', description: 'One robot fails during operation' },
  { name: 'network_disruption', description: 'Network connectivity issues' },
]

export function ScenarioControl({ onStartScenario, isLoading = false }: ScenarioControlProps) {
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null)

  const handleStart = (scenarioName: string) => {
    setSelectedScenario(scenarioName)
    onStartScenario?.(scenarioName)
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
        Scenarios
      </h3>
      <div className="space-y-2">
        {SCENARIOS.map(scenario => (
          <button
            key={scenario.name}
            onClick={() => handleStart(scenario.name)}
            disabled={isLoading}
            className={`w-full text-left p-3 rounded border transition-colors flex items-center justify-between group ${
              selectedScenario === scenario.name
                ? 'bg-blue-900/40 border-blue-600/50'
                : 'bg-slate-800/30 border-slate-700/30 hover:bg-slate-700/40 hover:border-slate-600/50'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <div>
              <div className="font-medium text-slate-200 capitalize">{scenario.name.replace('_', ' ')}</div>
              <div className="text-xs text-slate-400 mt-0.5">{scenario.description}</div>
            </div>
            <Play className="w-4 h-4 text-slate-400 group-hover:text-slate-300 transition-colors flex-shrink-0 ml-2" />
          </button>
        ))}
      </div>
    </div>
  )
}
