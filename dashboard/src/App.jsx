import React from 'react'
import LiveMap from './components/LiveMap'
import StatsBar from './components/StatsBar'
import NodeHealth from './components/NodeHealth'
import InsightPanel from './components/InsightPanel'
import useWebSocket from './hooks/useWebSocket'
import './index.css'

function App() {
  useWebSocket() // Connect to real-time feed

  return (
    <div className="min-h-screen bg-neutral-900 text-white p-6 flex flex-col gap-6 font-sans">
      <header className="flex justify-between items-center border-b border-neutral-800 pb-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent tracking-tight">Project FlowTrace</h1>
          <p className="text-neutral-400 text-sm mt-1">Agentic Analytics Engine</p>
        </div>
        <div className="flex gap-4">
          <span className="px-3 py-1 bg-green-900/30 text-green-400 border border-green-800/50 rounded-full text-xs flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            System Active
          </span>
        </div>
      </header>
      
      <StatsBar />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        <div className="lg:col-span-2 flex flex-col gap-6">
          <div className="bg-neutral-800 rounded-xl border border-neutral-700 overflow-hidden shadow-2xl flex-1 flex flex-col">
            <div className="p-4 border-b border-neutral-700 bg-neutral-800/50">
              <h2 className="font-semibold text-lg">Live Map</h2>
            </div>
            <div className="flex-1 relative min-h-[500px]">
              <LiveMap />
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-6">
          <InsightPanel />
          <NodeHealth />
        </div>
      </div>
    </div>
  )
}

export default App
