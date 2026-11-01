import { defineConfig, devices } from '@playwright/test';

// Estas pruebas corren contra la web con el cliente SIMULADO (VITE_USE_MOCKS=true).
// No demuestran generación real: eso requiere el worker y el JEF releído (H1).
const PORT = 5174;
const WEB_DIR = '../../apps/web';

export default defineConfig({
  testDir: '.',
  timeout: 45_000,
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    // Usa el Chrome instalado: evita descargar navegadores.
    channel: process.env.E2E_BROWSER_CHANNEL ?? 'chrome',
  },
  projects: [
    { name: 'escritorio', use: { viewport: { width: 1280, height: 800 } } },
    { name: 'movil', use: { ...devices['Pixel 7'], channel: process.env.E2E_BROWSER_CHANNEL ?? 'chrome' } },
  ],
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    cwd: WEB_DIR,
    url: `http://localhost:${PORT}`,
    env: { VITE_USE_MOCKS: 'true' },
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
