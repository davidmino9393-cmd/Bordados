// SIMULADO — opciones del cliente simulado tomadas de la URL (solo se usan con VITE_USE_MOCKS=true).
// ?mockDownloadTtlMs=1500  acorta el TTL de las descargas para probar vencimientos
// ?mockTrace=1             anota cada operación en window.__mockApiCalls (pruebas e2e)
import type { MockOptions } from './MockApiClient';

declare global {
  interface Window {
    __mockApiCalls?: string[];
  }
}

export function mockOptionsFromUrl(search: string, target: Window = window): MockOptions {
  const params = new URLSearchParams(search);
  const ttl = Number(params.get('mockDownloadTtlMs'));
  const options: MockOptions = {};
  if (Number.isFinite(ttl) && ttl > 0) options.downloadTtlMs = ttl;
  if (params.has('mockTrace')) {
    target.__mockApiCalls = [];
    options.onCall = (method) => target.__mockApiCalls?.push(method);
  }
  return options;
}
