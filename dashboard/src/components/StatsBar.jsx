import React from 'react'
import { useFlowTraceStore } from '../stores/flowtraceStore'

export default function StatsBar() {
  const { devices, venueStats } = useFlowTraceStore()
  
  const activeCount = Object.keys(devices).length
  
  const stats = [
    { label: "Currently Active", value: activeCount, color: "text-blue-400" },
    { label: "Avg Dwell Time", value: "14m", color: "text-purple-400" },
    { label: "Busiest Zone", value: "VR Zone", color: "text-orange-400" },
    { label: "Insights Generated", value: "24", color: "text-green-400" }
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((s, i) => (
        <div key={i} className="bg-neutral-800 rounded-xl p-5 border border-neutral-700/50">
          <div className="text-neutral-400 text-sm mb-1">{s.label}</div>
          <div className={`text-3xl font-bold ${s.color}`}>{s.value}</div>
        </div>
      ))}
    </div>
  )
}
