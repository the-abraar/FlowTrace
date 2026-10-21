// Header status badge for the store's `connection` mode. Only a live backend may look "active" (CODING_STANDARDS: Disclose).
const BADGE = {
  connecting: { label: 'Connecting', box: 'bg-neutral-800 text-neutral-400 border-neutral-700', dot: 'bg-neutral-500 animate-pulse' },
  connected: { label: 'System Active', box: 'bg-green-900/30 text-green-400 border-green-800/50', dot: 'bg-green-500 animate-pulse' },
  demo: { label: 'Demo Data', box: 'bg-yellow-900/30 text-yellow-400 border-yellow-800/50', dot: 'bg-yellow-400' },
  offline: { label: 'Offline', box: 'bg-red-900/30 text-red-400 border-red-800/50', dot: 'bg-red-500' },
}

export const systemBadge = (connection) => BADGE[connection] || BADGE.offline
