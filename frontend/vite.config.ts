import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend (FastAPI) runs on http://localhost:8000.
// During dev we proxy the API path prefixes so the frontend can call them
// same-origin (avoids CORS entirely and keeps VITE_API_BASE_URL empty).
const BACKEND = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/agent": { target: BACKEND, changeOrigin: true },
      "/ratings": { target: BACKEND, changeOrigin: true },
      "/health": { target: BACKEND, changeOrigin: true },
    },
  },
});
