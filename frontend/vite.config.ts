import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // The backend has no CORS middleware by design: the browser always talks
    // same-origin /api (this proxy in dev, Caddy in prod).
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
