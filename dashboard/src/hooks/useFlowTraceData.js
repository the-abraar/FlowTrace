import { useQuery } from '@tanstack/react-query'

const API_BASE = '/api'

async function apiFetch(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

// ── Zone analytics ──────────────────────────────────────────────────────────
export function useZoneAnalytics() {
  return useQuery({
    queryKey: ['zone-analytics'],
    queryFn: () => apiFetch('/analytics/zones'),
    refetchInterval: 30_000,
    // Provide fallback data so the UI works without a live backend
    placeholderData: {
      zones: [
        { name: 'VR Zone',    avgDwell: 22, visits: 89,  revenue: 1240 },
        { name: 'Laser Tag',  avgDwell: 18, visits: 134, revenue: 2680 },
        { name: 'Food Court', avgDwell: 12, visits: 201, revenue: 3150 },
        { name: 'Lobby',      avgDwell: 4,  visits: 312, revenue: 0    },
        { name: 'Exit',       avgDwell: 1,  visits: 312, revenue: 0    },
      ],
    },
  })
}

// ── Historical device trails ─────────────────────────────────────────────────
export function useDeviceTrail(deviceId, enabled = true) {
  return useQuery({
    queryKey: ['device-trail', deviceId],
    queryFn: () => apiFetch(`/devices/${deviceId}/trail?minutes=10`),
    enabled: !!deviceId && enabled,
    refetchInterval: 5_000,
    placeholderData: { trail: [] },
  })
}

// ── Global venue stats ───────────────────────────────────────────────────────
export function useVenueStats() {
  return useQuery({
    queryKey: ['venue-stats'],
    queryFn: () => apiFetch('/stats/venue'),
    refetchInterval: 10_000,
    placeholderData: {
      totalToday: 312,
      currentlyActive: 24,
      avgDwellMinutes: 18,
      topZone: 'VR Zone',
      conversionEvents: 47,
    },
  })
}

// ── Node health history ──────────────────────────────────────────────────────
export function useNodeHistory(nodeId) {
  return useQuery({
    queryKey: ['node-history', nodeId],
    queryFn: () => apiFetch(`/nodes/${nodeId}/history`),
    enabled: !!nodeId,
    refetchInterval: 60_000,
    placeholderData: { readings: [] },
  })
}

// ── Insight history ──────────────────────────────────────────────────────────
export function useInsightHistory(limit = 50) {
  return useQuery({
    queryKey: ['insights', limit],
    queryFn: () => apiFetch(`/insights?limit=${limit}`),
    refetchInterval: 20_000,
    placeholderData: { insights: [] },
  })
}
