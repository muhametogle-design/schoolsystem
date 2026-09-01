import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Standalone prototype: Tailwind is provided by @tailwindcss/vite (v4 zero-config
// content scanning), so the pasted utility classes render without the SPA build
// in web/ being touched at all. There is deliberately no /api proxy — this
// prototype runs entirely on the mock data inside ArenaOS.jsx.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
