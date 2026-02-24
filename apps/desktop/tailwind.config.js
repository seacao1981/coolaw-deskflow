/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        code: ['"Fira Code"', "monospace"],
        sans: ['"Fira Sans"', "system-ui", "sans-serif"],
      },
      colors: {
        "bg-deep": "var(--color-bg-deep)",
        "bg-base": "var(--color-bg-base)",
        surface: "var(--color-surface)",
        "surface-el": "var(--color-surface-el)",
        accent: "var(--color-accent)",
        "accent-hover": "var(--color-accent-hover)",
        "text-p": "var(--color-text-p)",
        "text-s": "var(--color-text-s)",
        "text-m": "var(--color-text-m)",
        info: "#3B82F6",
        warning: "#F59E0B",
        error: "#EF4444",
        success: "#10B981",
      },
      animation: {
        blink: "blink 1s step-end infinite",
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
      },
      keyframes: {
        blink: {
          "50%": { opacity: "0" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
    },
  },
  plugins: [],
};
