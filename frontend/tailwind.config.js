/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Paper & ink — an accounting ledger, not a dark SaaS dashboard.
        paper: { DEFAULT: "#F4EFE2", 100: "#FBF8F0", 200: "#EFE8D6", 300: "#E4DAC1" },
        ink: { DEFAULT: "#1A1712", 700: "#3A352C", 500: "#6B6353", 300: "#9A9081" },
        rule: "#1A1712",
        accent: { DEFAULT: "#1F2EE6", ink: "#0E1696" }, // cobalt stamp
        credit: "#0A7D3C", // money in / settled
        debit: "#B3261E", // money out / blocked
      },
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { none: "0", sm: "2px" },
      boxShadow: { hard: "4px 4px 0 0 #1A1712" },
      keyframes: {
        blink: { "0%,49%": { opacity: 1 }, "50%,100%": { opacity: 0 } },
      },
      animation: { blink: "blink 1s steps(1) infinite" },
    },
  },
  plugins: [],
};
