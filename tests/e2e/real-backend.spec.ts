import { mkdirSync, writeFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';

// Recorrido completo por la UI contra el backend real. Registra lo observado en
// test-results/real-backend-observations.json (ignorado por git) para el reporte.
const SVG_PATH = new URL('../../Anime_Socks_Bordado/Anime_Socks_InkStitch.svg', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const OUT_DIR = 'test-results/real-backend';
const REVIEW_TIMEOUT_MS = 120_000;

interface ApiCall {
  method: string;
  path: string;
  status: number;
  ms: number;
}
const observations: Record<string, unknown> = {};
const calls: ApiCall[] = [];
const jobStatuses: Array<{ status: string; atMs: number; cancellation_requested: boolean }> = [];
let t0 = 0;

function watch(page: Page) {
  page.on('response', async (response) => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith('/api/v1/')) return;
    const request = response.request();
    const timing = request.timing();
    calls.push({ method: request.method(), path: url.pathname.replace('/api/v1', ''), status: response.status(), ms: Math.round(timing.responseEnd) });
    if (request.method() === 'GET' && /\/jobs\/[^/]+$/.test(url.pathname)) {
      try {
        const job = await response.json();
        if (jobStatuses.at(-1)?.status !== job.status || jobStatuses.at(-1)?.cancellation_requested !== job.cancellation_requested) {
          jobStatuses.push({ status: job.status, atMs: Date.now() - t0, cancellation_requested: job.cancellation_requested });
        }
      } catch {
        /* respuesta sin cuerpo */
      }
    }
  });
}

async function startProjectWithSvg(page: Page, name: string) {
  await page.goto('/');
  await page.getByLabel('Nombre del proyecto').fill(name);
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
  await page.getByLabel('Elegir archivo').setInputFiles(SVG_PATH);
  // El backend real no emite `original_download` (llega null): no hay vista previa del original.
  await expect(page.getByText(/Anime_Socks_InkStitch\.svg · Sin medida en píxeles/)).toBeVisible();
  observations.originalDownload = (await page.getByText('La vista previa del original no está disponible.').count()) > 0 ? 'null (sin vista previa)' : 'disponible';
  await page.getByLabel('Ancho máximo (mm)').fill('150');
  await page.getByLabel('Alto máximo (mm)').fill('150');
  await expect(page.getByLabel('Bastidor')).toHaveValue('sq20b');
  await expect(page.getByLabel('Tela')).toHaveValue('gabardina_inicial');
  t0 = Date.now();
  await page.getByRole('button', { name: 'Generar bordado' }).click();
  await expect(page.getByRole('heading', { name: 'Generación del bordado' })).toBeVisible();
}

test.afterAll(() => {
  mkdirSync(OUT_DIR, { recursive: true });
  writeFileSync(`${OUT_DIR}/real-backend-observations.json`, JSON.stringify({ observations, jobStatuses, calls }, null, 2));
});

test('recorrido completo: flujo inicial, estados, archivos, JEF, muestra física', async ({ page }) => {
  watch(page);
  await startProjectWithSvg(page, 'Verificación backend real');
  const created = calls.filter((c) => c.method === 'POST').map((c) => `${c.method} ${c.path} → ${c.status} (${c.ms} ms)`);
  observations.postsDelFlujoInicial = created;

  await expect(page.getByText('Hay un elemento que necesita revisión')).toBeVisible({ timeout: REVIEW_TIMEOUT_MS });
  observations.segundosHastaNeedsReview = Math.round((Date.now() - t0) / 100) / 10;

  // Estado digital y aviso de archivos.
  await expect.soft(page.getByText('Listo para prueba (digital)')).toHaveCount(0);
  await expect.soft(page.getByText('Archivos para revisar: no están listos para prueba')).toBeVisible();
  const issueRows = page.locator('.issue');
  observations.incidenciasEnPantalla = await issueRows.count();
  observations.objectIdsEnPantalla = await page.getByRole('combobox', { name: /Qué querés hacer/ }).evaluateAll((els) =>
    els.map((el) => (el.getAttribute('id') ? (document.querySelector(`label[for="${el.id}"]`)?.textContent ?? '') : '')),
  );
  observations.medidasMostradas = (await page.locator('.metrics').first().innerText()).replace(/\n+/g, ' | ');

  // Archivos: contamos los enlaces de descarga de la UI.
  const links = page.getByRole('link', { name: /Descargar/ });
  await expect(links.first()).toBeVisible();
  observations.enlacesDeDescarga = await links.evaluateAll((els) => els.map((el) => (el as HTMLAnchorElement).download));

  // Descarga del JEF con el enlace vigente.
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: /Descargar\s*Archivo de bordado/ }).click();
  const download = await downloadPromise;
  mkdirSync(OUT_DIR, { recursive: true });
  await download.saveAs(`${OUT_DIR}/output.jef`);
  observations.jefDescargado = { nombre: download.suggestedFilename(), guardadoEn: `${OUT_DIR}/output.jef` };

  // Muestra física desde la UI.
  await expect(page.getByText('Sin probar en tela')).toBeVisible();
  await page.getByRole('radio', { name: 'Aprobada' }).check();
  await page.getByLabel('Fecha de la muestra').fill('2026-10-01T11:00');
  await page.getByLabel('Estabilizador').fill('Cut-away');
  await page.getByLabel('Hilo').fill('Poliéster 40');
  await page.getByLabel('Observaciones').fill('Prueba de verificación contra el backend real.');
  await page.getByRole('button', { name: 'Registrar muestra' }).click();
  await expect(page.getByText(/Muestra registrada/)).toBeVisible();
  await expect(page.getByText('Muestra física aprobada')).toBeVisible();
  observations.estadoDigitalTrasMuestra = (await page.locator('.badge').first().innerText());
  await expect.soft(page.getByText('Listo para prueba (digital)')).toHaveCount(0);
  const sewoutCall = calls.find((c) => c.method === 'POST' && c.path.endsWith('/sewouts'));
  observations.postSewouts = sewoutCall ? `${sewoutCall.status} (${sewoutCall.ms} ms)` : 'no se llamó';
});

test('cancelación de un job en curso', async ({ page }) => {
  watch(page);
  jobStatuses.length = 0;
  await startProjectWithSvg(page, 'Cancelación backend real');
  await page.getByRole('button', { name: 'Cancelar generación' }).click();
  const cancelCall = () => calls.find((c) => c.method === 'POST' && c.path.endsWith('/cancel'));
  await expect(page.getByText('Generación cancelada')).toBeVisible({ timeout: 90_000 });
  observations.cancelacion = {
    postCancel: cancelCall() ? `${cancelCall()!.status} (${cancelCall()!.ms} ms)` : 'no se llamó',
    estadosObservados: jobStatuses.map((s) => `${s.status}${s.cancellation_requested ? ' (cancellation_requested)' : ''}`),
  };
  await expect(page.getByRole('link', { name: /Descargar/ })).toHaveCount(0);
});
