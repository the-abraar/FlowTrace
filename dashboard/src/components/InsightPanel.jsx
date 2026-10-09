import { useEffect, useRef, useCallback } from 'react'
import { Bell, CheckCircle, AlertTriangle, TrendingUp, Lightbulb, Zap } from 'lucide-react'
import { useFlowTraceStore } from '../stores/flowtraceStore'
import { timeAgo } from '../utils/positioning'

// ── Type config ───────────────────────────────────────────────────────────────
const TYPE_CONFIG = {
  UPSELL: {
    label: 'UPSELL',
    badgeClass: 'badge-green',
    borderColor: 'border-emerald-500/40',
    bgColor: 'bg-emerald-950/30',
    iconColor: 'text-emerald-400',
    Icon: TrendingUp,
  },
  ALERT: {
    label: 'ALERT',
    badgeClass: 'badge-red',
    borderColor: 'border-red-500/40',
    bgColor: 'bg-red-950/30',
    iconColor: 'text-red-400',
    Icon: AlertTriangle,
  },
  RECOMMENDATION: {
    label: 'ADVICE',
    badgeClass: 'badge-blue',
    borderColor: 'border-blue-500/40',
    bgColor: 'bg-blue-950/30',
    iconColor: 'text-blue-400',
    Icon: Lightbulb,
  },
  ANOMALY: {
    label: 'ANOMALY',
    badgeClass: 'badge-orange',
    borderColor: 'border-orange-500/40',
    bgColor: 'bg-orange-950/30',
    iconColor: 'text-orange-400',
    Icon: Zap,
  },
}

// ── Sound alert for ALERT type ────────────────────────────────────────────────
function playAlertSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, ctx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.3)
    gain.gain.setValueAtTime(0.15, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + 0.5)
  } catch {
    // AudioContext not available (e.g., SSR or restricted)
  }
}

// ── Single insight card ────────────────────────────────────────────────────────
function InsightCard({ insight, onAct }) {
  const cfg = TYPE_CONFIG[insight.type] ?? TYPE_CONFIG.RECOMMENDATION
  const { Icon } = cfg

  return (
    <div
      className={`
        rounded-lg border p-3 transition-all duration-300 animate-fade-in
        ${cfg.borderColor} ${cfg.bgColor}
        ${insight.acted ? 'opacity-50' : ''}
      `}
    >
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 shrink-0 ${cfg.iconColor}`}>
          <Icon size={14} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`badge ${cfg.badgeClass}`}>{cfg.label}</span>
            <span className="font-mono text-xs text-flowtrace-neon">{insight.deviceId}</span>
            <span className="text-xs text-flowtrace-textMuted ml-auto">{timeAgo(insight.timestamp)}</span>
          </div>
          <p className="text-xs text-flowtrace-text leading-relaxed">{insight.message}</p>
          <p className="text-xs text-flowtrace-textMuted mt-1">
            → <span className="italic">{insight.suggestedAction}</span>
          </p>
        </div>
      </div>

      {!insight.acted && (
        <button
          onClick={() => onAct(insight.id)}
          className="mt-2 ml-5 flex items-center gap-1 text-xs text-flowtrace-textMuted
                     hover:text-flowtrace-text transition-colors duration-150 group"
        >
          <CheckCircle
            size={12}
            className="group-hover:text-emerald-400 transition-colors"
          />
          Mark as Acted
        </button>
      )}
      {insight.acted && (
        <div className="mt-2 ml-5 flex items-center gap-1 text-xs text-emerald-500">
          <CheckCircle size={12} /> Acted
        </div>
      )}
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────
export default function InsightPanel() {
  const insights = useFlowTraceStore((s) => s.insights)
  const markInsightActed = useFlowTraceStore((s) => s.markInsightActed)
  const prevCountRef = useRef(insights.length)
  const [filter, setFilter] = useStateLocal('ALL')

  // Sound alert on new ALERT insights
  useEffect(() => {
    if (insights.length > prevCountRef.current) {
      const newest = insights[0]
      if (newest?.type === 'ALERT' && !newest.acted) {
        playAlertSound()
      }
    }
    prevCountRef.current = insights.length
  }, [insights])

  const filtered = filter === 'ALL'
    ? insights
    : insights.filter((i) => i.type === filter)

  const counts = {
    ALL: insights.length,
    UPSELL: insights.filter((i) => i.type === 'UPSELL').length,
    ALERT: insights.filter((i) => i.type === 'ALERT').length,
    RECOMMENDATION: insights.filter((i) => i.type === 'RECOMMENDATION').length,
    ANOMALY: insights.filter((i) => i.type === 'ANOMALY').length,
  }

  return (
    <div className="flowtrace-card-glow h-full flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-flowtrace-text tracking-wide flex items-center gap-2">
          <Bell size={14} className="text-flowtrace-neon" />
          AGENT INSIGHTS
        </h2>
        <span className="badge badge-yellow">{counts.ALL} total</span>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 flex-wrap">
        {['ALL', 'UPSELL', 'ALERT', 'RECOMMENDATION', 'ANOMALY'].map((t) => {
          const cfg = t === 'ALL' ? null : TYPE_CONFIG[t]
          return (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`
                px-2 py-0.5 rounded text-xs font-mono font-semibold transition-all
                ${filter === t
                  ? 'bg-flowtrace-border text-flowtrace-text'
                  : 'text-flowtrace-textMuted hover:text-flowtrace-text'}
              `}
            >
              {t === 'ALL' ? 'ALL' : TYPE_CONFIG[t].label} ({counts[t]})
            </button>
          )
        })}
      </div>

      {/* Scrolling feed */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-0">
        {filtered.length === 0 && (
          <div className="text-center text-flowtrace-textMuted text-xs py-8 italic">
            No insights yet — waiting for agent engine…
          </div>
        )}
        {filtered.map((insight) => (
          <InsightCard
            key={insight.id}
            insight={insight}
            onAct={markInsightActed}
          />
        ))}
      </div>
    </div>
  )
}

// Simple local state helper (avoids importing useState everywhere)
function useStateLocal(initial) {
  const { useState } = require('react')
  return useState(initial)
}
