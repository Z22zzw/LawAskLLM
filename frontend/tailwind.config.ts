import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        parchment:   '#f5f4ed',
        ivory:       '#faf9f5',
        'warm-sand': '#e8e6dc',
        'dark-surface': '#30302e',
        'deep-dark':  '#141413',
        terracotta:  '#c96442',
        coral:       '#d97757',
        'error-crimson': '#b53333',
        'focus-ring': 'rgba(201,100,66,0.22)',
        'charcoal-warm': '#4d4c48',
        'olive-gray': '#5e5d59',
        'stone-gray': '#87867f',
        'dark-warm':  '#3d3d3a',
        'warm-silver':'#b0aea5',
        'border-cream':'#f0eee6',
        'border-warm': '#e8e6dc',
        'border-dark': '#30302e',
        'ring-warm':   '#d1cfc5',
      },
      fontFamily: {
        serif: ['Georgia', 'serif'],
        sans:  ['Inter', 'system-ui', 'Arial', 'sans-serif'],
        mono:  ['JetBrains Mono', 'monospace'],
      },
      lineHeight: {
        'tight-serif': '1.10',
        body: '1.60',
      },
      borderRadius: {
        sm:   '4px',
        DEFAULT: '8px',
        md:   '12px',
        lg:   '16px',
        xl:   '24px',
        '2xl':'32px',
      },
      boxShadow: {
        ring:    '0px 0px 0px 1px #d1cfc5',
        whisper: 'rgba(0,0,0,0.05) 0px 4px 24px',
      },
    },
  },
  plugins: [],
} satisfies Config
