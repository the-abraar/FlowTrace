import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import { DEMO_ZONES, DEMO_NODE_POSITIONS, apiZoneToRect } from '../utils/positioning'

// ─── Mock data generators ────────────────────────────────────────────────────
const ZONES = ['VR Zone', 'Laser Tag', 'Food Court', 'Exit', 'Lobby']

function randomBetween(a, b) {
  return Math.random() * (b - a) + a
}

function generateDevice(id) {
  const zone = ZONES[Math.floor(Math.random() * ZONES.length)]
  return {
    id: `DEV-${String(id).padStart(4, '0')}`,
    x: randomBetween(0.5, 9.5),
    y: randomBetween(0.5, 9.5),
    zone,
    dwellTime: Math.floor(randomBetween(0, 45)),          // minutes
    firstSeen: Date.now() - Math.floor(randomBetween(0, 3_600_000)),
    lastSeen: Date.now(),
    rssi: Math.floor(randomBetween(-90, -40)),
    trail: [],
  }
}

function generateNode({ id, x, y }) {
  return {
    id,
    x,
    y,
    online: Math.random() > 0.15,
    lastSeen: Date.now() - Math.floor(randomBetween(0, 60_000)),
    rssi: Math.floor(randomBetween(-80, -30)),
    readingRate: Math.floor(randomBetween(8, 42)),         // readings/min
    uptime: Math.floor(randomBetween(60, 99_999)),         // seconds
  }
}

function generateInsight(index) {
  const types = ['UPSELL', 'ALERT', 'RECOMMENDATION', 'ANOMALY']
  const type = types[Math.floor(Math.random() * types.length)]
  const deviceId = `DEV-${String(Math.floor(randomBetween(1, 50))).padStart(4, '0')}`
  const messages = {
    UPSELL: [
      `${deviceId} has spent 25+ min in VR Zone — prime upsell candidate for premium package.`,
      `${deviceId} revisited Food Court 3 times. Offer loyalty discount.`,
    ],
    ALERT: [
      `${deviceId} stationary for 15 min near Exit — possible assistance needed.`,
      `Crowd density in Laser Tag exceeds safe threshold (>30 devices).`,
    ],
    RECOMMENDATION: [
      `Route ${deviceId} toward Laser Tag — low occupancy window detected.`,
      `Open second Food Court register — avg wait time approaching 8 min.`,
    ],
    ANOMALY: [
      `${deviceId} teleported 8m in <2s — possible signal multipath.`,
      `NODE-03 reporting anomalous RSSI variance — check hardware.`,
    ],
  }
  const actions = {
    UPSELL: 'Send push offer',
    ALERT: 'Dispatch staff',
    RECOMMENDATION: 'Update digital signage',
    ANOMALY: 'Flag for review',
  }
  const pool = messages[type]
  return {
    id: `INS-${Date.now()}-${index}`,
    type,
    deviceId,
    message: pool[Math.floor(Math.random() * pool.length)],
    suggestedAction: actions[type],
    timestamp: Date.now() - Math.floor(randomBetween(0, 300_000)),
    acted: false,
  }
}

// ─── Store ───────────────────────────────────────────────────────────────────
// connection: 'connecting' (before the first attempt ends) | 'connected' (live backend) | 'demo' (backend unreachable, MOCK data) | 'offline' (lost live backend, data frozen)
// same origin: nginx (docker) and the Vite dev proxy both forward /ws to the backend. VITE_WS_URL overrides.
const WS_URL = import.meta.env.VITE_WS_URL || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
const EMPTY_STATS = { totalToday: 0, currentlyActive: 0, avgDwellMinutes: 0, topZone: '—', conversionEvents: null, bounceRate: null, abTest: null }

// Backend READ_API_KEY, if set. It ships in the JS bundle, so it only keeps out people who cannot load the dashboard.
const READ_KEY = import.meta.env.VITE_READ_API_KEY || ''
const withKey = (url) => (READ_KEY ? `${url}${url.includes('?') ? '&' : '?'}key=${encodeURIComponent(READ_KEY)}` : url)

async function api(path) {
  const res = await fetch(`/api/v1${path}`, READ_KEY ? { headers: { 'X-API-Key': READ_KEY } } : undefined)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

let _retry = null
let _wasLive = false  // reached the backend at least once
let _poll = null

export const useFlowTraceStore = create(
  subscribeWithSelector((set, get) => ({
    devices: [],
    insights: [],
    nodeHealth: [],
    zones: [],                // venue zone rectangles: from /api/v1/analytics/zones when live, DEMO_ZONES in demo
    insightsNote: null,       // why AI insights are empty when connected (e.g. 503 message)
    connection: 'connecting',
    wsStatus: 'disconnected',  // raw socket state, kept for existing consumers
    wsRef: null,
    venueStats: EMPTY_STATS,

    setWsStatus: (status) => set({ wsStatus: status }),

    updateDevices: (payload) => {
      // live backend: upsert by device_id (positions message); trail kept for the ghost-trail view
      set((state) => {
        const byId = new Map(state.devices.map((d) => [d.id, d]))
        for (const p of payload) {
          const id = p.id ?? p.device_id
          const d = byId.get(id)
          const trail = d ? [{ x: d.x, y: d.y, t: Date.now() }, ...d.trail.slice(0, 119)] : []
          byId.set(id, { dwellTime: 0, rssi: null, firstSeen: Date.now(), ...d, ...p, id, trail, lastSeen: Date.now() })
        }
        return { devices: [...byId.values()] }
      })
    },

    addDevice: (device) =>
      set((state) => ({ devices: [...state.devices, { ...device, trail: [] }] })),
    removeDevice: (id) =>
      set((state) => ({ devices: state.devices.filter((d) => d.id !== id) })),
    addInsight: (insight) =>
      set((state) => ({ insights: [insight, ...state.insights].slice(0, 100) })),
    markInsightActed: (id) =>
      set((state) => ({
        insights: state.insights.map((i) => (i.id === id ? { ...i, acted: true } : i)),
      })),
    updateNodeHealth: (nodes) => set({ nodeHealth: nodes }),
    updateVenueStats: (patch) =>
      set((state) => ({ venueStats: { ...state.venueStats, ...patch } })),

    // Pull real values from /api/v1 (only called while connected)
    refreshFromApi: async () => {
      const [nodes, devs, summary, ins, zones] = await Promise.allSettled([
        api('/nodes'), api('/devices'), api('/analytics/summary'), api('/insights'), api('/analytics/zones'),
      ])
      if (get().connection !== 'connected') return
      const patch = {}
      if (nodes.status === 'fulfilled') {
        patch.nodeHealth = nodes.value.map((n) => ({
          id: n.id, x: n.x_pos, y: n.y_pos, online: !!n.active, lastSeen: null, rssi: null, readingRate: null,
        }))
      }
      if (zones.status === 'fulfilled') patch.zones = zones.value.map(apiZoneToRect)
      const stats = { ...get().venueStats }
      if (devs.status === 'fulfilled') stats.totalToday = devs.value.length
      if (summary.status === 'fulfilled') {
        const zs = Object.entries(summary.value.zones ?? {})
        const visited = zs.filter(([, z]) => z.total_visits > 0)
        stats.currentlyActive = zs.reduce((n, [, z]) => n + z.current_occupancy, 0)
        stats.avgDwellMinutes = visited.length
          ? Math.round(visited.reduce((n, [, z]) => n + z.avg_dwell_seconds, 0) / visited.length / 6) / 10
          : 0
        const top = zs.sort((a, b) => b[1].current_occupancy - a[1].current_occupancy)[0]
        stats.topZone = top && top[1].current_occupancy > 0 ? top[1].label : '—'
        stats.bounceRate = summary.value.bounce_rate ?? null
        stats.abTest = summary.value.ab_test ?? null
      }
      patch.venueStats = stats
      if (ins.status === 'fulfilled') {
        const t = Date.parse(ins.value.generated_at) || Date.now()
        patch.insights = ins.value.insights.map((i, k) => ({
          id: `INS-${t}-${k}`, type: i.insight_type, deviceId: i.device_id, message: i.message,
          suggestedAction: i.suggested_action, timestamp: t, acted: false,
        }))
        patch.insightsNote = null
      } else {
        patch.insights = []
        patch.insightsNote = 'AI insights unavailable (backend reports disabled or not ready)'
      }
      set(patch)
    },

    enterDemo: () => {
      const devices = Array.from({ length: 24 }, (_, i) => generateDevice(i + 1))
      set({
        connection: 'demo', zones: DEMO_ZONES, devices, nodeHealth: DEMO_NODE_POSITIONS.map(generateNode), insightsNote: null,
        insights: Array.from({ length: 8 }, (_, i) => generateInsight(i)).sort((a, b) => b.timestamp - a.timestamp),
        venueStats: { totalToday: 312, currentlyActive: devices.length, avgDwellMinutes: 18, topZone: 'VR Zone', conversionEvents: 47,
          bounceRate: 0.34, abTest: { a: 'Front Display', b: 'Back Wall', a_share: 0.65, b_share: 0.35 } },
      })
      startMockUpdates(set, get)
    },

    // ── WebSocket connection (backend /ws) ────────────────────────────────────
    connectWebSocket: (url = WS_URL) => {
      const { wsRef } = get()
      if (wsRef && wsRef.readyState <= WebSocket.OPEN) return
      set({ wsStatus: 'reconnecting' })

      let ws
      try { ws = new WebSocket(withKey(url)) } catch { ws = null }  // browsers cannot set WS headers: ?key=
      const lost = () => {
        stopMockUpdates(); clearInterval(_poll)
        set({ wsRef: null, wsStatus: 'reconnecting' })
        if (get().connection === 'connected') {
          set({ connection: 'offline' })           // keep last real data, flagged stale
        } else if (get().connection === 'offline' && _wasLive) {
          // failed reconnect after live data: stay offline, never swap real data for mock
        } else if (get().connection !== 'demo') {
          get().enterDemo()                        // never reached backend: explicit demo
        } else {
          startMockUpdates(set, get)
        }
        clearTimeout(_retry)
        _retry = setTimeout(() => get().connectWebSocket(url), 3000)
      }
      if (!ws) return lost()
      set({ wsRef: ws })

      ws.onopen = () => {
        _wasLive = true
        stopMockUpdates()
        // drop demo data so mock values never mix with live ones
        set({ connection: 'connected', wsStatus: 'connected', devices: [], insights: [], nodeHealth: [], zones: [], venueStats: EMPTY_STATS })
        get().refreshFromApi()
        clearInterval(_poll)
        _poll = setInterval(() => get().refreshFromApi(), 5000)
      }
      ws.onmessage = (event) => {
        try { handleWsMessage(JSON.parse(event.data), set, get) } catch (e) { console.warn('[FlowTrace WS] Invalid message', e) }
      }
      ws.onerror = () => ws.close()
      ws.onclose = lost
    },

    disconnectWebSocket: () => {
      clearTimeout(_retry); clearInterval(_poll)
      const { wsRef } = get()
      if (wsRef) { wsRef.onclose = null; wsRef.close() }
      set({ wsRef: null, wsStatus: 'disconnected' })
      stopMockUpdates()
    },
  }))
)

// ─── WebSocket message router ─────────────────────────────────────────────────
function handleWsMessage(msg, set, get) {
  switch (msg.type) {
    case 'positions':
      get().updateDevices(msg.data)
      break
    case 'insight':
      get().addInsight(msg.data)
      break
    case 'node_health':
      get().updateNodeHealth(msg.data)
      break
    case 'venue_stats':
      get().updateVenueStats(msg.data)
      break
    case 'device_join':
      get().addDevice(msg.data)
      break
    case 'device_leave':
      get().removeDevice(msg.data.id)
      break
    default:
      break
  }
}

// ─── Mock update loop (when backend is offline) ───────────────────────────────
let _mockTimers = []

function stopMockUpdates() {
  _mockTimers.forEach(clearInterval)
  _mockTimers = []
}

function startMockUpdates(set, get) {
  stopMockUpdates()

  // Drift device positions every 1.5 s
  const posTimer = setInterval(() => {
    set((state) => {
      const updated = state.devices.map((d) => {
        const dx = randomBetween(-0.3, 0.3)
        const dy = randomBetween(-0.3, 0.3)
        const nx = Math.min(9.8, Math.max(0.2, d.x + dx))
        const ny = Math.min(9.8, Math.max(0.2, d.y + dy))

        // Determine zone from position
        const zone = positionToZone(nx, ny)
        const trail = [{ x: d.x, y: d.y, t: Date.now() }, ...d.trail.slice(0, 119)]

        return {
          ...d,
          x: nx,
          y: ny,
          zone,
          trail,
          dwellTime: zone === d.zone ? d.dwellTime + 0.025 : 0,
          lastSeen: Date.now(),
        }
      })
      return { devices: updated }
    })
  }, 1500)

  // Emit a random insight every 12 s
  const insightTimer = setInterval(() => {
    const insight = generateInsight(Date.now())
    get().addInsight(insight)
  }, 12_000)

  // Update venue stats every 5 s
  const statsTimer = setInterval(() => {
    set((state) => {
      const active = state.devices.length
      const topZone = computeTopZone(state.devices)
      return {
        venueStats: {
          ...state.venueStats,
          currentlyActive: active,
          totalToday: state.venueStats.totalToday + Math.floor(randomBetween(0, 2)),
          avgDwellMinutes: Math.round(
            state.devices.reduce((s, d) => s + d.dwellTime, 0) / active
          ),
          topZone,
          conversionEvents:
            state.venueStats.conversionEvents + Math.floor(randomBetween(0, 1)),
        },
      }
    })
  }, 5_000)

  // Randomly toggle a node offline/online every 15 s
  const nodeTimer = setInterval(() => {
    set((state) => {
      const nodes = state.nodeHealth.map((n) => ({
        ...n,
        online: Math.random() > 0.12,
        lastSeen: n.online ? Date.now() : n.lastSeen,
        readingRate: Math.floor(randomBetween(8, 42)),
        rssi: Math.floor(randomBetween(-80, -30)),
      }))
      return { nodeHealth: nodes }
    })
  }, 15_000)

  _mockTimers = [posTimer, insightTimer, statsTimer, nodeTimer]
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function positionToZone(x, y) {
  if (x < 4 && y < 5) return 'VR Zone'
  if (x >= 4 && x < 8 && y < 4) return 'Laser Tag'
  if (x >= 4 && y >= 5) return 'Food Court'
  if (x >= 8) return 'Exit'
  return 'Lobby'
}

function computeTopZone(devices) {
  const counts = {}
  devices.forEach((d) => {
    counts[d.zone] = (counts[d.zone] || 0) + 1
  })
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'N/A'
}
