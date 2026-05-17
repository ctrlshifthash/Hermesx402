import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { nodePolyfills } from "vite-plugin-node-polyfills";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [
    react(),
    // Solana wallet libs (Phantom connector) need Buffer/process/global.
    nodePolyfills({ globals: { Buffer: true, global: true, process: true } }),
  ],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  optimizeDeps: {
    include: [
      "@privy-io/react-auth",
      "@privy-io/react-auth/solana",
    ],
  },
  server: { host: "0.0.0.0", port: 5173 },
});
