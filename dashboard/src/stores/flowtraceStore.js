import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

// ─── Mock data generators ────────────────────────────────────────────────────
const ZONES = ['VR Zone', 'Laser Tag', 'Food Court', 'Exit', 'Lobby']
const NODES = ['NODE-01', 'NODE-02', 'NODE-03', 'NODE-04', 'NODE-05', 'NODE-06']

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

function generateNode(id) {
  return {
    id,
    x: randomBetween(1, 9),
    y: randomBetween(1, 9),
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

// ─── Initial state ───────────────────────────────────────────────────────────
const INITIAL_DEVICES = Array.from({ length: 24 }, (_, i) => generateDevice(i + 1))
const INITIAL_NODES = NODES.map(generateNode)
const INITIAL_INSIGHTS = Array.from({ length: 8 }, (_, i) => generateInsight(i))

// ─── Zustand store ───────────────────────────────────────────────────────────
export const useFlowTraceStore = create(
  subscribeWithSelector((set, get) => ({
    // State slices
    devices: INITIAL_DEVICES,
    insights: INITIAL_INSIGHTS.sort((a, b) => b.timestamp - a.timestamp),
    nodeHealth: INITIAL_NODES,
    wsStatus: 'disconnected',  // 'connected' | 'disconnected' | 'reconnecting'
    wsRef: null,

    // Venue aggregate stats (computed / updated by WS)
    venueStats: {
      totalToday: 312,
      currentlyActive: INITIAL_DEVICES.length,
      avgDwellMinutes: 18,
      topZone: 'VR Zone',
      conversionEvents: 47,
    },

    // ── Actions ──────────────────────────────────────────────────────────────
    setWsStatus: (status) => set({ wsStatus: status }),

    updateDevices: (payload) => {
      set((state) => {
        const updated = state.devices.map((d) => {
          const patch = payload.find((p) => p.id === d.id)
          if (!patch) return d
          const trail = [
            { x: d.x, y: d.y, t: Date.now() },
            ...d.trail.slice(0, 119),            // keep last 120 points ≈ 10 min
          ]
          return { ...d, ...patch, trail, lastSeen: Date.now() }
        })
        return { devices: updated }
      })
    },

    addDevice: (device) =>
      set((state) => ({ devices: [...state.devices, { ...device, trail: [] }] })),

    removeDevice: (id) =>
      set((state) => ({ devices: state.devices.filter((d) => d.id !== id) })),

    addInsight: (insight) =>
      set((state) => ({
        insights: [insight, ...state.insights].slice(0, 100),
      })),

    markInsightActed: (id) =>
      set((state) => ({
        insights: state.insights.map((i) =>
          i.id === id ? { ...i, acted: true } : i
        ),
      })),

    updateNodeHealth: (nodes) => set({ nodeHealth: nodes }),

    updateVenueStats: (patch) =>
      set((state) => ({ venueStats: { ...state.venueStats, ...patch } })),

    // ── WebSocket connection ──────────────────────────────────────────────────
    connectWebSocket: () => {
      const { wsRef } = get()
      if (wsRef && wsRef.readyState === WebSocket.OPEN) return

      const connect = () => {
        set({ wsStatus: 'reconnecting' })

        let ws
        try {
          ws = new WebSocket('ws://localhost:8000/ws/dashboard')
        } catch {
          // Backend not running — fall through to mock mode
          startMockUpdates(set, get)
          set({ wsStatus: 'connected' })
          return
        }

        set({ wsRef: ws })

        ws.onopen = () => {
          console.log('[FlowTrace WS] Connected')
          set({ wsStatus: 'connected' })
        }

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            handleWsMessage(msg, set, get)
          } catch (e) {
            console.warn('[FlowTrace WS] Invalid message', e)
          }
        }

        ws.onerror = () => {
          console.warn('[FlowTrace WS] Error — falling back to mock mode')
          ws.close()
        }

        ws.onclose = () => {
          set({ wsStatus: 'reconnecting', wsRef: null })
          console.log('[FlowTrace WS] Disconnected — retrying in 3s')
          setTimeout(() => {
            // After two failed attempts, use mock data
            startMockUpdates(set, get)
            set({ wsStatus: 'connected' })
          }, 3000)
        }
      }

      connect()
    },

    disconnectWebSocket: () => {
      const { wsRef } = get()
      if (wsRef) {
        wsRef.close()
        set({ wsRef: null, wsStatus: 'disconnected' })
      }
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
