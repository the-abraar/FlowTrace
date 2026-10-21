import React from 'react'
import { useFlowTraceStore } from '../stores/flowtraceStore'

const TEXT = {
  connecting: 'CONNECTING to the backend... No data yet.',
  demo: 'DEMO MODE: backend unreachable. Everything shown is simulated, not real venue data.',
  offline: 'OFFLINE: lost connection to the backend. Data below is stale. Reconnecting...',
}

export default function ConnectionBanner() {
  const connection = useFlowTraceStore((s) => s.connection)
  if (connection === 'connected') return null
  return (
    <div role="alert" className={`sticky top-0 z-50 px-4 py-2 text-sm font-bold text-center ${{ demo: 'bg-yellow-400 text-black', connecting: 'bg-neutral-700 text-white' }[connection] || 'bg-red-600 text-white'}`}>
      {TEXT[connection]}
    </div>
  )
}
