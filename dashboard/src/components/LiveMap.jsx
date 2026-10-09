import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3'
import { useFlowTraceStore } from '../stores/flowtraceStore'
import {
  ZONE_DEFINITIONS,
  NODE_POSITIONS,
  dwellTimeColor,
  gridToSvg,
  formatDwell,
  timeAgo,
} from '../utils/positioning'

const GRID_SIZE = 10

export default function LiveMap() {
  const svgRef = useRef(null)
  const containerRef = useRef(null)
  const [dims, setDims] = useState({ w: 600, h: 600 })
  const [tooltip, setTooltip] = useState(null)
  const devices = useFlowTraceStore((s) => s.devices)
  const nodeHealth = useFlowTraceStore((s) => s.nodeHealth)

  // ── Responsive resize ──────────────────────────────────────────────────────
  useEffect(() => {
    const ro = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect
      const size = Math.min(width, 640)
      setDims({ w: size, h: size })
    })
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  // ── D3 render ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const svg = d3.select(svgRef.current)
    const { w, h } = dims

    const toSvg = (gx, gy) => gridToSvg(gx, gy, w, h, GRID_SIZE)

    // ── Grid lines ───────────────────────────────────────────────────────────
    svg.selectAll('.grid-line').remove()
    const gridG = svg.select('.grid-layer')

    for (let i = 0; i <= GRID_SIZE; i++) {
      gridG.append('line')
        .attr('class', 'grid-line')
        .attr('x1', (i / GRID_SIZE) * w).attr('y1', 0)
        .attr('x2', (i / GRID_SIZE) * w).attr('y2', h)
        .attr('stroke', '#1e2d45').attr('stroke-width', 0.5)

      gridG.append('line')
        .attr('class', 'grid-line')
        .attr('x1', 0).attr('y1', (i / GRID_SIZE) * h)
        .attr('x2', w).attr('y2', (i / GRID_SIZE) * h)
        .attr('stroke', '#1e2d45').attr('stroke-width', 0.5)
    }

    // ── Zones ─────────────────────────────────────────────────────────────
    const zoneG = svg.select('.zone-layer')
    zoneG.selectAll('.zone-rect').remove()
    zoneG.selectAll('.zone-label').remove()

    ZONE_DEFINITIONS.forEach((z) => {
      const { px: x1, py: y1 } = toSvg(z.x, z.y)
      const { px: x2, py: y2 } = toSvg(z.x + z.w, z.y + z.h)
      const { px: lx, py: ly } = toSvg(z.label.x, z.label.y)

      zoneG.append('rect')
        .attr('class', 'zone-rect')
        .attr('x', x1).attr('y', y1)
        .attr('width', x2 - x1).attr('height', y2 - y1)
        .attr('fill', z.fill)
        .attr('stroke', z.stroke)
        .attr('stroke-width', 1.5)
        .attr('rx', 4)

      zoneG.append('text')
        .attr('class', 'zone-label')
        .attr('x', lx).attr('y', ly)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', z.stroke)
        .attr('font-size', Math.max(9, w / 60))
        .attr('font-family', 'JetBrains Mono, monospace')
        .attr('font-weight', '600')
        .attr('opacity', 0.9)
        .text(z.name)
    })

    // ── Node antennas ──────────────────────────────────────────────────────
    const nodeG = svg.select('.node-layer')
    nodeG.selectAll('.node').remove()

    NODE_POSITIONS.forEach((np) => {
      const health = nodeHealth.find((n) => n.id === np.id)
      const online = health?.online ?? true
      const { px, py } = toSvg(np.x, np.y)
      const r = Math.max(6, w / 90)

      const g = nodeG.append('g').attr('class', 'node').attr('transform', `translate(${px},${py})`)

      // Glow circle
      if (online) {
        g.append('circle')
          .attr('r', r * 2.2)
          .attr('fill', 'rgba(0,245,255,0.07)')
          .attr('stroke', 'rgba(0,245,255,0.2)')
          .attr('stroke-width', 0.5)
      }

      // Antenna body
      g.append('circle')
        .attr('r', r)
        .attr('fill', online ? '#0d1220' : '#1a0a0a')
        .attr('stroke', online ? '#00f5ff' : '#ef4444')
        .attr('stroke-width', 1.5)

      // Antenna icon (simple lines)
      const lh = r * 0.7
      g.append('line').attr('x1', 0).attr('y1', -lh).attr('x2', 0).attr('y2', lh)
        .attr('stroke', online ? '#00f5ff' : '#ef4444').attr('stroke-width', 1.2)
      g.append('line').attr('x1', -lh).attr('y1', 0).attr('x2', lh).attr('y2', 0)
        .attr('stroke', online ? '#00f5ff' : '#ef4444').attr('stroke-width', 1.2)

      // Node ID
      g.append('text')
        .attr('y', r + Math.max(8, w / 70))
        .attr('text-anchor', 'middle')
        .attr('fill', online ? '#00f5ff' : '#ef4444')
        .attr('font-size', Math.max(7, w / 85))
        .attr('font-family', 'JetBrains Mono, monospace')
        .attr('opacity', 0.8)
        .text(np.id)
    })
  }, [dims, nodeHealth])

  // ── Animate device dots (separate effect for performance) ─────────────────
  useEffect(() => {
    const svg = d3.select(svgRef.current)
    const { w, h } = dims
    const deviceG = svg.select('.device-layer')
    const r = Math.max(5, w / 100)

    // Bind data
    const dots = deviceG.selectAll('.device-dot').data(devices, (d) => d.id)

    // Enter
    const entered = dots.enter()
      .append('g')
      .attr('class', 'device-dot')
      .attr('transform', (d) => {
        const { px, py } = gridToSvg(d.x, d.y, w, h, GRID_SIZE)
        return `translate(${px},${py})`
      })
      .style('cursor', 'pointer')

    entered.append('circle')
      .attr('class', 'device-glow')
      .attr('r', r * 2)
      .attr('fill', 'transparent')

    entered.append('circle')
      .attr('class', 'device-core')
      .attr('r', r)
      .attr('stroke', '#080c14')
      .attr('stroke-width', 1)

    entered.append('circle')
      .attr('class', 'device-pulse')
      .attr('r', r)
      .attr('fill', 'transparent')
      .attr('stroke-width', 1.5)

    // Merge & update
    const merged = entered.merge(dots)

    merged
      .on('mouseenter', (event, d) => {
        setTooltip({ device: d, x: event.clientX, y: event.clientY })
        d3.select(event.currentTarget).raise()
      })
      .on('mousemove', (event) => {
        setTooltip((prev) => prev ? { ...prev, x: event.clientX, y: event.clientY } : null)
      })
      .on('mouseleave', () => setTooltip(null))

    merged
      .transition()
      .duration(1400)
      .ease(d3.easeCubicInOut)
      .attr('transform', (d) => {
        const { px, py } = gridToSvg(d.x, d.y, w, h, GRID_SIZE)
        return `translate(${px},${py})`
      })

    merged.select('.device-core')
      .transition()
      .duration(600)
      .attr('fill', (d) => dwellTimeColor(d.dwellTime))

    merged.select('.device-glow')
      .attr('fill', (d) => dwellTimeColor(d.dwellTime, 0.15))

    merged.select('.device-pulse')
      .attr('stroke', (d) => dwellTimeColor(d.dwellTime, 0.6))

    // Exit
    dots.exit()
      .transition().duration(400)
      .attr('opacity', 0)
      .remove()
  }, [devices, dims])

  // ── Legend ────────────────────────────────────────────────────────────────
  const legendStops = [
    { label: '0m',   color: '#00f5ff' },
    { label: '10m',  color: '#3b82f6' },
    { label: '20m',  color: '#eab308' },
    { label: '35m',  color: '#f97316' },
    { label: '45m+', color: '#ef4444' },
  ]

  return (
    <div className="flowtrace-card-glow h-full flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-flowtrace-text tracking-wide flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-flowtrace-neon animate-pulse-neon inline-block" />
          LIVE FLOOR MAP
        </h2>
        <span className="badge badge-green">{devices.length} active</span>
      </div>

      <div ref={containerRef} className="relative flex-1 min-h-0 flex items-center justify-center">
        <svg
          ref={svgRef}
          width={dims.w}
          height={dims.h}
          className="rounded-lg overflow-hidden"
          style={{ background: '#080c14' }}
        >
          <g className="grid-layer" />
          <g className="zone-layer" />
          <g className="node-layer" />
          <g className="device-layer" />
        </svg>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="fixed z-50 pointer-events-none flowtrace-card border-flowtrace-neon/40 text-xs shadow-neon"
            style={{ left: tooltip.x + 14, top: tooltip.y - 10 }}
          >
            <p className="font-mono text-flowtrace-neon font-bold">{tooltip.device.id}</p>
            <p className="text-flowtrace-textMuted mt-0.5">Zone: <span className="text-flowtrace-text">{tooltip.device.zone}</span></p>
            <p className="text-flowtrace-textMuted">Dwell: <span className="text-flowtrace-text">{formatDwell(tooltip.device.dwellTime)}</span></p>
            <p className="text-flowtrace-textMuted">RSSI: <span className="text-flowtrace-text">{tooltip.device.rssi} dBm</span></p>
            <p className="text-flowtrace-textMuted">Last seen: <span className="text-flowtrace-text">{timeAgo(tooltip.device.lastSeen)}</span></p>
          </div>
        )}
      </div>

      {/* Dwell-time legend */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-flowtrace-textMuted font-mono">Dwell:</span>
        {legendStops.map((s) => (
          <div key={s.label} className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: s.color }} />
            <span className="text-xs text-flowtrace-textMuted">{s.label}</span>
          </div>
        ))}
        <div className="ml-3 flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#00f5ff', border: '1px solid #00f5ff' }} />
          <span className="text-xs text-flowtrace-textMuted">Node (online)</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#ef4444', border: '1px solid #ef4444' }} />
          <span className="text-xs text-flowtrace-textMuted">Node (offline)</span>
        </div>
      </div>
    </div>
  )
}
