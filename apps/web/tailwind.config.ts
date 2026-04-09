import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#1e2f59",
        mist: "#f4f8ff",
        sand: "#eef3ff",
        alert: "#b4242a",
        safe: "#1f6f50",
        brand: {
          50: "#eef4ff",
          100: "#dce9ff",
          200: "#bdd4ff",
          300: "#99bcff",
          400: "#719fff",
          500: "#4f84f1",
          600: "#3f70db",
          700: "#315bb8",
          800: "#2b4f99",
          900: "#253f78",
        },
      },
      fontFamily: {
        sans: ["var(--font-poppins)", "ui-sans-serif", "system-ui", "sans-serif"],
        slogan: ["var(--font-slogan)", "cursive"],
      },
      boxShadow: {
        panel: "0 14px 36px rgba(43, 79, 153, 0.12)",
      },
      backgroundImage: {
        "brand-glow": "radial-gradient(circle at top right, rgba(113, 159, 255, 0.25), transparent 56%)",
      },
    },
  },
  plugins: [],
};

export default config;
