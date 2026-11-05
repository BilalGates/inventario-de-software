/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter Variable", "Inter", "Segoe UI Variable", "Segoe UI", "system-ui", "sans-serif"],
        display: ["Inter Tight Variable", "Inter Variable", "Inter", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono Variable", "JetBrains Mono", "Cascadia Code", "Consolas", "monospace"],
      },
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        subtle: token("subtle"),
        border: token("border"),
        "border-strong": token("border-strong"),
        fg: token("fg"),
        "fg-2": token("fg-2"),
        muted: token("muted"),
        accent: token("accent"),
        "accent-fg": token("accent-fg"),
        signal: token("signal"),
        "signal-fill": token("signal-fill"),
        ok: token("ok"),
        warn: token("warn"),
        danger: token("danger"),
        info: token("info"),
        "chart-1": token("chart-1"),
        "chart-2": token("chart-2"),
        "chart-3": token("chart-3"),
        "chart-4": token("chart-4"),
        side: token("side"),
      },
      borderRadius: { DEFAULT: "6px", panel: "10px" },
      fontSize: { "2xs": ["0.6875rem", "1rem"] },
    },
  },
  plugins: [],
};
