import { defineConfig, devices } from '@playwright/test';

// recorridos.spec.ts: web con el cliente SIMULADO (VITE_USE_MOCKS=true).
// real-client.spec.ts: web con el cliente HTTP real contra un stub dentro del test.
// Ninguna demuestra generación real: eso requiere el worker y el JEF releído.
const MOCK_PORT = 5174;
const REAL_PORT = 5175;
const WEB_DIR = '../../apps/web';
// Usa el Chrome instalado: evita descargar navegadores.
const channel = process.env.E2E_BROWSER_CHANNEL ?? 'chrome';

const server = (port: number, mocks: boolean) => ({
  command: `npm run dev -- --port ${port} --strictPort`,
  cwd: WEB_DIR,
  url: `http://localhost:${port}`,
  env: { VITE_USE_MOCKS: mocks ? 'true' : 'false' },
  reuseExistingServer: false,
  timeout: 60_000,
});

export default defineConfig({
  testDir: '.',
  timeout: 45_000,
  fullyParallel: true,
  reporter: 'list',
  use: { channel },
  projects: [
    {
      name: 'escritorio',
      testMatch: 'recorridos.spec.ts',
      use: { baseURL: `http://localhost:${MOCK_PORT}`, viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'movil',
      testMatch: 'recorridos.spec.ts',
      use: { ...devices['Pixel 7'], channel, baseURL: `http://localhost:${MOCK_PORT}` },
    },
    {
      name: 'cliente-real',
      testMatch: 'real-client.spec.ts',
      use: { baseURL: `http://localhost:${REAL_PORT}`, viewport: { width: 1280, height: 800 } },
    },
  ],
  webServer: [server(MOCK_PORT, true), server(REAL_PORT, false)],
});
