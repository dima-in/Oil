/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'ios-blue': '#007AFF',
        'ios-green': '#34C759',
        'ios-red': '#FF3B30',
        'ios-orange': '#FF9500',
        'ios-gray': '#8E8E93',
        'ios-light-gray': '#F2F2F7',
        'ios-dark': '#1C1C1E',
        'ios-card': '#2C2C2E',
      },
      backdropBlur: {
        'ios': '20px',
      },
      boxShadow: {
        'ios': '0 4px 24px rgba(0, 0, 0, 0.12)',
        'ios-inset': 'inset 0 1px 0 rgba(255, 255, 255, 0.1)',
      },
    },
  },
  plugins: [],
}
