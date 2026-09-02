import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The FastAPI backend owns auth, the ERP and the compliance engine. In dev the
// Vite server proxies /api and /ws straight through, so the SPA never needs to
// know an absolute host — which keeps it working behind any preview proxy too.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Hosted previews / tunnels reach the dev server through arbitrary
    // proxy hostnames — allow them (dev-only server, API auth still applies).
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
