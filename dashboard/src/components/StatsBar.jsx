import React from 'react'
import { useFlowTraceStore } from '../stores/flowtraceStore'

export default function StatsBar() {
  const venueStats = useFlowTraceStore((s) => s.venueStats)
  const insightCount = useFlowTraceStore((s) => s.insights.length)
  const connection = useFlowTraceStore((s) => s.connection)
  const live = connection === 'connected'

  const stats = [
    { label: "Currently Active", value: venueStats.currentlyActive, color: "text-blue-400" },
    { label: "Avg Dwell Time", value: `${venueStats.avgDwellMinutes}m`, color: "text-purple-400" },
    { label: "Busiest Zone", value: venueStats.topZone, color: "text-orange-400" },
    { label: "Insights Generated", value: insightCount, color: "text-green-400" },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {connection === 'demo' && <div className="col-span-full text-xs font-bold text-yellow-400">DEMO DATA: simulated values</div>}
      {connection === 'offline' && <div className="col-span-full text-xs font-bold text-red-400">STALE: backend offline, last known values</div>}
      {stats.map((s, i) => (
        <div key={i} className="bg-neutral-800 rounded-xl p-5 border border-neutral-700/50">
          <div className="text-neutral-400 text-sm mb-1">{s.label}</div>
          <div className={`text-3xl font-bold ${s.color}`}>{s.value}</div>
        </div>
      ))}
    </div>
  )
}
