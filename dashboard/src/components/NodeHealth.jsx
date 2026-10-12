import React from 'react'
import { useFlowTraceStore } from '../stores/flowtraceStore'

export default function NodeHealth() {
  const nodes = useFlowTraceStore((s) => s.nodeHealth)
  const connection = useFlowTraceStore((s) => s.connection)

  return (
    <div className="bg-neutral-800 rounded-xl border border-neutral-700 p-4">
      <h3 className="font-semibold mb-4 flex justify-between items-center">
        <span>Node Health {connection === 'demo' && <span className="text-xs font-bold text-yellow-400">DEMO DATA</span>}</span>
        <span className="text-xs px-2 py-1 bg-neutral-700 rounded text-neutral-300">{nodes.length} Deployed</span>
      </h3>
      
      <div className="flex flex-col gap-2">
        {nodes.map(node => (
          <div key={node.id} className="flex justify-between items-center p-2 rounded bg-neutral-900/50 border border-neutral-700/30">
            <div className="flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full ${node.online ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span className="text-sm font-mono text-neutral-300">{node.id}</span>
            </div>
            {node.online ? (
              <span className="text-xs text-neutral-500 font-mono">{node.rssi == null ? 'online' : `${node.rssi} dBm`}</span>
            ) : (
              <span className="text-xs text-red-400">Offline</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
