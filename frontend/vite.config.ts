import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to Root Backend in dev
      "/api": {
        target: process.env.BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      // Proxy /agent to Agent Engine frontend
      "/agent": {
        target: process.env.AGENT_FRONTEND_URL || "http://localhost:5177",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});