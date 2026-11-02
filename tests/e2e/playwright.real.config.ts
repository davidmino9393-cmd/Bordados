import { defineConfig } from '@playwright/test';

// Verificación contra el BACKEND REAL (uvicorn en localhost:8000). No forma parte de la suite
// normal: se corre a mano con `npx playwright test -c playwright.real.config.ts`.
// Las credenciales son las de desarrollo local del backend (HTTP Basic); no se guardan en la web.
const PORT = 5176;
const ORIGIN = `http://localhost:${PORT}`;
const channel = process.env.E2E_BROWSER_CHANNEL ?? 'chrome';

export default defineConfig({
  testDir: '.',
  testMatch: 'real-backend.spec.ts',
  timeout: 180_000,
  workers: 1,
  reporter: 'list',
  use: {
    channel,
    baseURL: ORIGIN,
    viewport: { width: 1280, height: 900 },
    httpCredentials: {
      username: process.env.E2E_API_USER ?? 'test',
      password: process.env.E2E_API_PASSWORD ?? 'test',
      origin: ORIGIN,
    },
  },
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    cwd: '../../apps/web',
    url: ORIGIN,
    // El proxy de Vite reenvía /api al backend: el navegador sigue en un solo origen.
    env: { VITE_USE_MOCKS: 'false', API_PROXY_TARGET: process.env.E2E_API_TARGET ?? 'http://localhost:8000' },
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
