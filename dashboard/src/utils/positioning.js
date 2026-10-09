/**
 * positioning.js
 * Utilities for position interpolation, zone colour mapping,
 * and dwell-time colour coding used across the dashboard.
 */

// ── Zone definitions (in 10m × 10m coordinate space) ──────────────────────
export const ZONE_DEFINITIONS = [
  {
    id: 'vr',
    name: 'VR Zone',
    x: 0, y: 0, w: 4, h: 5,
    fill: 'rgba(168, 85, 247, 0.15)',
    stroke: '#a855f7',
    label: { x: 2, y: 2.5 },
  },
  {
    id: 'laser',
    name: 'Laser Tag',
    x: 4, y: 0, w: 4, h: 4,
    fill: 'rgba(0, 245, 255, 0.10)',
    stroke: '#00f5ff',
    label: { x: 6, y: 2 },
  },
  {
    id: 'food',
    name: 'Food Court',
    x: 4, y: 4, w: 4, h: 6,
    fill: 'rgba(249, 115, 22, 0.12)',
    stroke: '#f97316',
    label: { x: 6, y: 7 },
  },
  {
    id: 'lobby',
    name: 'Lobby',
    x: 0, y: 5, w: 4, h: 5,
    fill: 'rgba(59, 130, 246, 0.10)',
    stroke: '#3b82f6',
    label: { x: 2, y: 7.5 },
  },
  {
    id: 'exit',
    name: 'Exit',
    x: 8, y: 0, w: 2, h: 10,
    fill: 'rgba(16, 185, 129, 0.10)',
    stroke: '#10b981',
    label: { x: 9, y: 5 },
  },
]

// ── Node positions (fixed hardware) ──────────────────────────────────────────
export const NODE_POSITIONS = [
  { id: 'NODE-01', x: 1.5, y: 1.5 },
  { id: 'NODE-02', x: 5.5, y: 1.5 },
  { id: 'NODE-03', x: 8.5, y: 1.5 },
  { id: 'NODE-04', x: 1.5, y: 7.5 },
  { id: 'NODE-05', x: 5.5, y: 6.5 },
  { id: 'NODE-06', x: 8.5, y: 7.5 },
]

// ── Zone colour map (name → tailwind/hex) ─────────────────────────────────
export const ZONE_COLOR_MAP = {
  'VR Zone':    { hex: '#a855f7', tw: 'purple' },
  'Laser Tag':  { hex: '#00f5ff', tw: 'cyan'   },
  'Food Court': { hex: '#f97316', tw: 'orange' },
  'Lobby':      { hex: '#3b82f6', tw: 'blue'   },
  'Exit':       { hex: '#10b981', tw: 'green'  },
}

// ── Dwell-time colour scale ──────────────────────────────────────────────────
// 0 min → cool cyan → yellow → warm red at 45+ min
const DWELL_STOPS = [
  { t: 0,  r: 0,   g: 245, b: 255 },  // #00f5ff — cyan (new)
  { t: 10, r: 59,  g: 130, b: 246 },  // #3b82f6 — blue
  { t: 20, r: 234, g: 179, b: 8   },  // #eab308 — yellow
  { t: 35, r: 249, g: 115, b: 22  },  // #f97316 — orange
  { t: 45, r: 239, g: 68,  b: 68  },  // #ef4444 — red (long stay)
]

function lerp(a, b, t) {
  return a + (b - a) * t
}

/**
 * Returns an rgba string representing dwell time intensity.
 * @param {number} minutes
 * @param {number} [alpha=0.9]
 */
export function dwellTimeColor(minutes, alpha = 0.9) {
  const clamped = Math.max(0, Math.min(45, minutes))
  let lo = DWELL_STOPS[0]
  let hi = DWELL_STOPS[DWELL_STOPS.length - 1]

  for (let i = 0; i < DWELL_STOPS.length - 1; i++) {
    if (clamped >= DWELL_STOPS[i].t && clamped <= DWELL_STOPS[i + 1].t) {
      lo = DWELL_STOPS[i]
      hi = DWELL_STOPS[i + 1]
      break
    }
  }

  const t = lo.t === hi.t ? 0 : (clamped - lo.t) / (hi.t - lo.t)
  const r = Math.round(lerp(lo.r, hi.r, t))
  const g = Math.round(lerp(lo.g, hi.g, t))
  const b = Math.round(lerp(lo.b, hi.b, t))
  return `rgba(${r},${g},${b},${alpha})`
}

/**
 * Linear interpolation between two 2-D positions.
 * Used to smooth device movement between telemetry frames.
 */
export function interpolatePosition(from, to, progress) {
  return {
    x: lerp(from.x, to.x, progress),
    y: lerp(from.y, to.y, progress),
  }
}

/**
 * Convert grid coordinates to SVG pixel coordinates.
 * @param {number} gx — grid x (0–10)
 * @param {number} gy — grid y (0–10)
 * @param {number} svgW — SVG width in px
 * @param {number} svgH — SVG height in px
 * @param {number} [gridSize=10]
 */
export function gridToSvg(gx, gy, svgW, svgH, gridSize = 10) {
  return {
    px: (gx / gridSize) * svgW,
    py: (gy / gridSize) * svgH,
  }
}

/**
 * Convert SVG pixel coordinates back to grid space.
 */
export function svgToGrid(px, py, svgW, svgH, gridSize = 10) {
  return {
    x: (px / svgW) * gridSize,
    y: (py / svgH) * gridSize,
  }
}

/**
 * Format a dwell duration in minutes to a human-readable string.
 */
export function formatDwell(minutes) {
  if (minutes < 1) return '<1 min'
  if (minutes < 60) return `${Math.round(minutes)} min`
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return `${h}h ${m}m`
}

/**
 * Format a UNIX ms timestamp as a relative time string.
 */
export function timeAgo(ts) {
  const diff = Date.now() - ts
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  return `${Math.floor(diff / 3_600_000)}h ago`
}

/**
 * RSSI quality label + colour.
 */
export function rssiQuality(rssi) {
  if (rssi >= -50) return { label: 'Excellent', color: '#10b981' }
  if (rssi >= -65) return { label: 'Good',      color: '#00f5ff' }
  if (rssi >= -75) return { label: 'Fair',      color: '#eab308' }
  return                    { label: 'Poor',     color: '#ef4444' }
}
