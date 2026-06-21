/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: "var(--paper)",
          sunk: "var(--paper-sunk)",
          raised: "var(--paper-raised)",
        },
        ink: {
          DEFAULT: "var(--ink)",
          muted: "var(--ink-muted)",
          subtle: "var(--ink-subtle)",
        },
        rule: "var(--rule)",
        accent: {
          DEFAULT: "var(--accent)",
          soft: "var(--accent-soft)",
        },
        positive: {
          DEFAULT: "var(--positive)",
          soft: "var(--positive-soft)",
        },
        negative: {
          DEFAULT: "var(--negative)",
          soft: "var(--negative-soft)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          soft: "var(--warning-soft)",
        },
      },
      fontFamily: {
        display: ['"Fraunces Variable"', "ui-serif", "Georgia", "serif"],
        sans: [
          '"Inter Tight Variable"',
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono Variable"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      letterSpacing: {
        tightish: "-0.01em",
      },
      boxShadow: {
        panel:
          "0 1px 0 rgba(14,26,43,0.04), 0 24px 48px -24px rgba(14,26,43,0.18)",
        rule: "inset 0 -1px 0 var(--rule)",
      },
      borderRadius: {
        sheet: "2px",
      },
    },
  },
  plugins: [],
};
