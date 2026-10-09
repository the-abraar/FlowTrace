/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        flowtrace: {
          bg:       '#080c14',
          surface:  '#0d1220',
          card:     '#111827',
          border:   '#1e2d45',
          neon:     '#00f5ff',
          purple:   '#a855f7',
          green:    '#10b981',
          red:      '#ef4444',
          orange:   '#f97316',
          blue:     '#3b82f6',
          yellow:   '#eab308',
          muted:    '#4b5563',
          text:     '#e2e8f0',
          textMuted:'#94a3b8',
        },
      },
      boxShadow: {
        neon:   '0 0 10px rgba(0,245,255,0.4), 0 0 30px rgba(0,245,255,0.1)',
        purple: '0 0 10px rgba(168,85,247,0.4), 0 0 30px rgba(168,85,247,0.1)',
        green:  '0 0 10px rgba(16,185,129,0.4)',
        red:    '0 0 10px rgba(239,68,68,0.4)',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-neon': 'pulseNeon 2s ease-in-out infinite',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
      },
      keyframes: {
        pulseNeon: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        slideIn: {
          '0%': { transform: 'translateX(-10px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
