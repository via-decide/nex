import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/query": "http://localhost:8000",
      "/sources": "http://localhost:8000",
      "/status": "http://localhost:8000",
      "/subchat": "http://localhost:8000",
    },
  },
});
