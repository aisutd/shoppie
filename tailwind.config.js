/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#102746',
        'navy-deep': '#071326',
        'navy-light': '#315987',
        'blue-mist': '#dbeafe',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(18px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        drift: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(1)', opacity: '0.55' },
          '50%': { transform: 'translate3d(48px, -32px, 0) scale(1.18)', opacity: '1' },
        },
        aurora: {
          '0%, 100%': { backgroundPosition: '15% 45%', opacity: '0.45' },
          '50%': { backgroundPosition: '85% 55%', opacity: '0.8' },
        },
      },
      animation: {
        'fade-up': 'fade-up 700ms ease-out both',
        'fade-in': 'fade-in 700ms ease-out both',
        drift: 'drift 12s ease-in-out infinite',
        aurora: 'aurora 16s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
