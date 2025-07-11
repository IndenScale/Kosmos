/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1a1a1a',
        secondary: '#4a4a4a',
        tertiary: '#8a8a8a',
      }
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false, // 避免与 Ant Design 样式冲突
  }
}