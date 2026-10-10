// Dev server for src/web/ with live reload. The app stays plain static files (no
// build step); /api and /exams are proxied to the uvicorn backend started by dev.sh.
import { defineConfig } from "vite";

const api = `http://127.0.0.1:${process.env.API_PORT || 8000}`;

export default defineConfig({
  root: "src/web",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": api, "/exams": api },
  },
});
