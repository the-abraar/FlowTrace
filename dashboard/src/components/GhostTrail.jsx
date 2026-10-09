import { useEffect, useRef, useState, useMemo } from 'react'
import * as d3 from 'd3'
import { useFlowTraceStore } from '../stores/flowtraceStore'
import { gridToSvg, dwellTimeColor, ZONE_DEFINITIONS } from '../utils/positioning'

const GRID_SIZE = 10
const TRAIL_MINUTES = 10

export default function GhostTrail() {
  const svgRef = useRef(null)
  const containerRef = useRef(null)
  const [dims, setDims] = useState({ w: 600, h: 500 })
  const [selectedId, setSelectedId] = useState('')
  const [scrubberValue, setScrubberValue] = useState(100)  // 0–100 %, 100 = now
  const devices = useFlowTraceStore((s) => s.devices)

  const deviceOptions = useMemo(
    () => devices.map((d) => d.id).sort(),
    [devices]
  )

  // Auto-select first device
  useEffect(() => {
    if (!selectedId && deviceOptions.length) setSelectedId(deviceOptions[0])
  }, [deviceOptions, selectedId])

  // Responsive
  useEffect(() => {
    const ro = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect
      setDims({ w: width, h: Math.min(width * 0.75, 480) })
    })
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  const selectedDevice = useMemo(
    () => devices.find((d) => d.id === selectedId),
    [devices, selectedId]
  )

  // Build trail from device history, filtered by scrubber
  const trailPoints = useMemo(() => {
    if (!selectedDevice) return []
    const nowMs = Date.now()
    const windowMs = (scrubberValue / 100) * TRAIL_MINUTES * 60_000

    const raw = [
      { x: selectedDevice.x, y: selectedDevice.y, t: nowMs },
      ...(selectedDevice.trail || []),
    ].filter((p) => nowMs - p.t <= windowMs)

    return raw
  }, [selectedDevice, scrubberValue])

  // ── D3 render ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const svg = d3.select(svgRef.current)
    const { w, h } = dims
    const toSvg = (gx, gy) => gridToSvg(gx, gy, w, h, GRID_SIZE)

    // Background zones (faint)
    const zoneG = svg.select('.gt-zones')
    zoneG.selectAll('*').remove()
    ZONE_DEFINITIONS.forEach((z) => {
      const { px: x1, py: y1 } = toSvg(z.x, z.y)
      const { px: x2, py: y2 } = toSvg(z.x + z.w, z.y + z.h)
      zoneG.append('rect')
        .attr('x', x1).attr('y', y1)
        .attr('width', x2 - x1).attr('height', y2 - y1)
        .attr('fill', z.fill.replace('0.15', '0.07').replace('0.10', '0.05').replace('0.12', '0.06'))
        .attr('stroke', z.stroke)
        .attr('stroke-width', 1)
        .attr('stroke-opacity', 0.3)
        .attr('rx', 4)
      const { px: lx, py: ly } = toSvg(z.label.x, z.label.y)
      zoneG.append('text')
        .attr('x', lx).attr('y', ly)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', z.stroke).attr('opacity', 0.4)
        .attr('font-size', Math.max(8, w / 65))
        .attr('font-family', 'JetBrains Mono, monospace')
        .text(z.name)
    })

    // Trail
    const trailG = svg.select('.gt-trail')
    trailG.selectAll('*').remove()

    if (trailPoints.length < 2) return

    const nowMs = Date.now()
    const maxAge = TRAIL_MINUTES * 60_000

    // Draw segments with fading opacity
    for (let i = 0; i < trailPoints.length - 1; i++) {
      const p0 = trailPoints[i]
      const p1 = trailPoints[i + 1]
      const age0 = (nowMs - p0.t) / maxAge
      const alpha0 = Math.max(0, 1 - age0)

      const { px: x0, py: y0 } = toSvg(p0.x, p0.y)
      const { px: x1, py: y1 } = toSvg(p1.x, p1.y)

      trailG.append('line')
        .attr('x1', x0).attr('y1', y0)
        .attr('x2', x1).attr('y2', y1)
        .attr('stroke', dwellTimeColor(selectedDevice?.dwellTime ?? 0, alpha0 * 0.85))
        .attr('stroke-width', Math.max(1, 3 * alpha0))
        .attr('stroke-linecap', 'round')
    }

    // Draw dots along trail
    trailPoints.forEach((p, i) => {
      const age = (nowMs - p.t) / maxAge
      const alpha = Math.max(0.05, 1 - age)
      const { px, py } = toSvg(p.x, p.y)
      const dotR = i === 0 ? Math.max(5, w / 80) : Math.max(2, (w / 80) * alpha * 0.6)

      trailG.append('circle')
        .attr('cx', px).attr('cy', py)
        .attr('r', dotR)
        .attr('fill', dwellTimeColor(selectedDevice?.dwellTime ?? 0, alpha))
        .attr('stroke', i === 0 ? '#fff' : 'none')
        .attr('stroke-width', i === 0 ? 1.5 : 0)
    })

    // Ghost pulse on latest position
    if (trailPoints.length > 0) {
      const { px, py } = toSvg(trailPoints[0].x, trailPoints[0].y)
      const pulse = trailG.append('circle')
        .attr('cx', px).attr('cy', py)
        .attr('r', 4)
        .attr('fill', 'none')
        .attr('stroke', '#00f5ff')
        .attr('stroke-width', 1.5)
        .attr('opacity', 0.8)

      pulse
        .transition()
        .duration(1500)
        .ease(d3.easeLinear)
        .attr('r', 20)
        .attr('opacity', 0)
        .on('end', function () {
          d3.select(this).attr('r', 4).attr('opacity', 0.8)
            .transition().duration(1500).ease(d3.easeLinear)
            .attr('r', 20).attr('opacity', 0)
        })
    }
  }, [trailPoints, dims, selectedDevice])

  return (
    <div className="flowtrace-card-glow h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="text-sm font-semibold text-flowtrace-text tracking-wide flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-flowtrace-purple animate-pulse-neon inline-block" />
          GHOST TRAIL
        </h2>
        <div className="flex items-center gap-3">
          <label className="text-xs text-flowtrace-textMuted font-mono">Device:</label>
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="bg-flowtrace-surface border border-flowtrace-border rounded px-2 py-1 text-xs
                       text-flowtrace-text font-mono focus:outline-none focus:border-flowtrace-neon"
          >
            {deviceOptions.map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
          {selectedDevice && (
            <span className="badge badge-blue">
              Zone: {selectedDevice.zone}
            </span>
          )}
        </div>
      </div>

      {/* SVG */}
      <div ref={containerRef} className="flex-1 min-h-0">
        <svg
          ref={svgRef}
          width={dims.w}
          height={dims.h}
          className="rounded-lg overflow-hidden w-full"
          style={{ background: '#080c14' }}
        >
          <g className="gt-zones" />
          <g className="gt-trail" />
        </svg>
      </div>

      {/* Timeline scrubber */}
      <div className="flex flex-col gap-1">
        <div className="flex justify-between text-xs text-flowtrace-textMuted font-mono">
          <span>–{TRAIL_MINUTES}m</span>
          <span>Showing last {Math.round(scrubberValue / 10)} min</span>
          <span>Now</span>
        </div>
        <input
          type="range"
          min={10}
          max={100}
          step={5}
          value={scrubberValue}
          onChange={(e) => setScrubberValue(Number(e.target.value))}
          className="w-full h-1.5 rounded accent-flowtrace-neon"
          style={{ accentColor: '#00f5ff' }}
        />
        <div className="flex justify-between text-xs text-flowtrace-textMuted">
          <span>{trailPoints.length} position records</span>
          {trailPoints.length === 0 && (
            <span className="text-flowtrace-textMuted italic">No trail data yet — device is moving</span>
          )}
        </div>
      </div>
    </div>
  )
}
