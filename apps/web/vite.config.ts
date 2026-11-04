/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      // En desarrollo, /api puede reenviarse al backend sin exponer su origen al navegador.
      // `API_PROXY_AUTHORIZATION` (lo pone scripts/iniciar-web.ps1) agrega las credenciales al reenviar: el navegador
      // no las pide ni las guarda, así que la clave no sale del proceso del servidor de desarrollo.
      proxy: env.API_PROXY_TARGET
        ? {
            '/api': {
              target: env.API_PROXY_TARGET,
              headers: env.API_PROXY_AUTHORIZATION ? { Authorization: env.API_PROXY_AUTHORIZATION } : undefined,
            },
          }
        : undefined,
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test-setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
    },
  };
});
