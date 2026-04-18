import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0b0d12",
          raised: "#12151c",
          border: "#1f2430",
          muted: "#8892a6",
        },
        brand: {
          DEFAULT: "#5b9dff",
          soft: "#1f3a67",
          emerald: "#34d399",
          amber: "#fbbf24",
          rose: "#fb7185",
        },
      },
      boxShadow: {
        panel:
          "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 10px 30px -10px rgba(0,0,0,0.4)",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Inter",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
