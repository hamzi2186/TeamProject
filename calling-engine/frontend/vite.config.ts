import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5176,
    proxy: {
      // Auth endpoints → root platform backend (issues JWTs)
      "/api/v1/auth": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      // Calling engine data → calling engine backend
      "/api/v1/calling": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
      "/api/v1/webhooks": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
    },
  },
});
