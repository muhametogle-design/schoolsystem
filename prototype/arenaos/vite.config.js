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
  // Behavioural checks for the prototype fixes (src/ArenaOS.test.jsx): a real
  // render in jsdom, not a snapshot of markup. Vite's transform pipeline is
  // reused, so there is no separate test bundler config to keep in sync.
  test: {
    environment: 'jsdom',
    css: false,
    // globals lets @testing-library/react auto-run its cleanup hook; without it every
    // render in the file piles up in the same jsdom document and queries find
    // the previous test's login form.
    globals: true,
    setupFiles: ['./src/setup-tests.js'],
  },
});
