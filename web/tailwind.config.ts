import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        muted: "var(--muted)",
        line: "var(--line)",
        canvas: "var(--canvas)",
        surface: "var(--surface)",
        brand: {
          DEFAULT: "var(--brand)",
          dark: "var(--brand-dark)",
          soft: "var(--brand-soft)",
        },
        up: "var(--up)",
        down: "var(--down)",
      },
      fontFamily: {
        sans: [
          "Pretendard",
          "Noto Sans KR",
          "Apple SD Gothic Neo",
          "sans-serif",
        ],
      },
      boxShadow: {
        soft: "0 8px 24px rgba(26,26,26,0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
