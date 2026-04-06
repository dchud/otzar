/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./catalog/templates/**/*.html",
    "./sources/templates/**/*.html",
    "./ingest/templates/**/*.html",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "system-ui", "-apple-system", "Segoe UI", "Roboto",
          "Helvetica Neue", "Noto Sans", "Noto Sans Hebrew",
          "Arial", "sans-serif",
        ],
      },
    },
  },
  plugins: [],
}
