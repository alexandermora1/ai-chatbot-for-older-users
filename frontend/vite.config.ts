import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The backend runs on port 8000. Requests to /api are forwarded there during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
