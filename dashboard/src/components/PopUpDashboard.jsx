import React from 'react';
import { useFlowTraceStore } from '../stores/flowtraceStore';

export default function PopUpDashboard() {
  const { devices } = useFlowTraceStore();
  const totalVisitors = Object.keys(devices).length;
  
  // Simulated pop-up metrics to match the new D2C agent prompts
  const bounceRate = "34%"; 
  const avgDwell = "4m 12s";
  
  return (
    <div className="bg-neutral-800 rounded-xl border border-neutral-700 overflow-hidden shadow-2xl flex-1 flex flex-col mt-6">
      <div className="p-4 border-b border-neutral-700 bg-neutral-900 flex justify-between items-center">
        <div>
          <h2 className="font-bold text-xl text-green-400">Pop-Up Mode Active</h2>
          <p className="text-xs text-neutral-400">Optimized for 1-3 day physical events</p>
        </div>
        <div className="px-3 py-1 bg-green-900/30 text-green-400 border border-green-800 rounded-full text-xs">
          Local Hotspot: FlowTrace_PopUp
        </div>
      </div>
      
      <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Physical Bounce Rate */}
        <div className="bg-neutral-900 p-5 rounded-lg border border-neutral-700">
          <div className="text-neutral-400 text-sm mb-2">Physical Bounce Rate</div>
          <div className="text-4xl font-bold text-red-400">{bounceRate}</div>
          <div className="text-xs text-neutral-500 mt-2">Visitors leaving in &lt; 60 seconds</div>
        </div>

        {/* Avg Dwell Time */}
        <div className="bg-neutral-900 p-5 rounded-lg border border-neutral-700">
          <div className="text-neutral-400 text-sm mb-2">Avg Session (Dwell Time)</div>
          <div className="text-4xl font-bold text-blue-400">{avgDwell}</div>
          <div className="text-xs text-neutral-500 mt-2">Across all product stations</div>
        </div>

        {/* A/B Test Results */}
        <div className="bg-neutral-900 p-5 rounded-lg border border-neutral-700">
          <div className="text-neutral-400 text-sm mb-2">A/B Layout Test</div>
          <div className="flex justify-between items-end mt-2">
            <div>
              <div className="text-lg font-bold text-purple-400">Front Display</div>
              <div className="text-xs text-neutral-500">65% Traffic</div>
            </div>
            <div className="text-neutral-600 font-bold text-xl">vs</div>
            <div className="text-right">
              <div className="text-lg font-bold text-neutral-400">Back Wall</div>
              <div className="text-xs text-neutral-500">35% Traffic</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
