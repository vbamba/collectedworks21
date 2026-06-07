// CHANGED: new file — replaces Create React App (react-scripts) with Vite.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 3000, // CHANGED: keep CRA's dev port so existing bookmarks/docs hold
    // CHANGED: replaces CRA's package.json "proxy" field. Same-origin
    // fetch('/api/...') calls in services/api.js (text_search, ai_search)
    // are proxied to the Flask backend during dev. Axios calls that use an
    // absolute VITE_BACKEND_URL bypass this and hit the backend directly.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
      },
    },
  },

  build: {
    // CHANGED: emit to build/ (Vite default is dist/) so the existing rsync
    // deploy, which ships frontend/build, keeps working unchanged.
    outDir: 'build',
  },

  // CHANGED: Vitest config (was react-scripts/jest). jsdom + globals so the
  // existing @testing-library tests run with minimal edits.
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
  },
});
