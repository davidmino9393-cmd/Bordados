import { mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';

// Imagen → E1 REAL → SVG de Ink/Stitch con parámetros de referencia → worker REAL (Ink/Stitch) → JEF descargable,
// contra el backend real levantado con real-backend/serve_with_simulated_analysis.py. Aquí no se usa IA: la imagen
// se envía con «Sin análisis de IA». Cada prueba tarda de uno a tres minutos porque Ink/Stitch corre de verdad.
const OUT_DIR = 'test-results/real-raster';
const JEF_TIMEOUT_MS = 420_000;
const JEF_MAGIC_BYTES_MIN = 128; // un JEF real trae cabecera y tabla de colores antes de las puntadas

async function openImageProject(page: Page, name: string) {
  await page.goto('/');
  await page.getByLabel('Nombre del proyecto').fill(name);
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
}

/** `hero`: el botón de arriba de la página; si no, la fila de la lista de descargas. */
async function downloadJef(page: Page, fileName: string, hero: boolean) {
  const link = hero
    ? page.getByRole('link', { name: 'Descargar archivo JEF' })
    : page.locator('.list__item', { hasText: /JEF/ }).first().getByRole('link', { name: /Descargar/ });
  const [download] = await Promise.all([page.waitForEvent('download'), link.click()]);
  const path = await download.path();
  expect(path).toBeTruthy();
  mkdirSync(OUT_DIR, { recursive: true });
  const bytes = readFileSync(path!);
  writeFileSync(`${OUT_DIR}/${fileName}`, bytes);
  return { bytes, suggested: download.suggestedFilename() };
}

test('imagen sin IA: Ink/Stitch real entrega un JEF descargable con medidas releídas', async ({ page }) => {
  await openImageProject(page, 'Verificación JEF real');
  const base64 = await page.evaluate(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, 640, 480);
    ctx.fillStyle = '#1f3a93';
    ctx.beginPath();
    ctx.arc(320, 240, 190, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(320, 240, 90, 0, Math.PI * 2);
    ctx.fill();
    return canvas.toDataURL('image/png').split(',')[1];
  });
  await page.getByLabel('Elegir archivo').setInputFiles({ name: 'anillo.png', mimeType: 'image/png', buffer: Buffer.from(base64, 'base64') });
  await expect(page.getByText('Imagen para analizar', { exact: true })).toBeVisible();
  await page.getByRole('radio', { name: 'Sin análisis de IA' }).check();
  await page.getByLabel('Ancho máximo (mm)').fill('80');
  await page.getByLabel('Alto máximo (mm)').fill('60');
  await page.getByRole('button', { name: 'Generar bordado' }).click();

  await expect(page.getByText('Hay un elemento que necesita revisión')).toBeVisible({ timeout: JEF_TIMEOUT_MS });
  await expect(page.getByText('Listo para prueba (digital)')).toHaveCount(0); // el JEF no es una aprobación
  // Ya no es «solo geometría»: hay JEF, medidas releídas y vista previa del JEF.
  await expect(page.getByText('Solo geometría: todavía no hay archivo de bordado')).toHaveCount(0);
  await expect(page.locator('.metrics')).toBeVisible();
  // El JEF está arriba de todo y una imagen no ofrece correcciones (el servidor solo las admite para un SVG preparado).
  await expect(page.getByRole('heading', { name: 'Tu archivo de bordado' })).toBeVisible();
  await expect(page.getByText(/no están calibrados para tu tela/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Aplicar y regenerar' })).toHaveCount(0);
  await page.screenshot({ path: `${OUT_DIR}/jef-needs-review.png`, fullPage: true });

  const { bytes, suggested } = await downloadJef(page, 'anillo.jef', true);
  expect(suggested).toBe('anillo.jef'); // se llama como la imagen que se subió
  expect(bytes.length).toBeGreaterThan(JEF_MAGIC_BYTES_MIN);

  writeFileSync(`${OUT_DIR}/summary.json`, JSON.stringify({
    jefFilename: suggested, jefBytes: bytes.length,
    issuesOnScreen: await page.locator('.issue').allInnerTexts(),
    downloadRows: await page.locator('.list__item').allInnerTexts(),
    metrics: await page.locator('.metrics').allInnerTexts(),
  }, null, 2));

  // Variante de tamaño: un trabajo nuevo que vuelve a generar desde la imagen (no escala el JEF) y deja el origen como estaba.
  const measuredWidth = async () => {
    const found = (await page.locator('.metrics').innerText()).match(/([\d.,]+) × ([\d.,]+) mm/);
    return Number(found![1].replace('.', '').replace(',', '.'));
  };
  const originalWidth = await measuredWidth();
  const originalUrl = page.url();
  await expect(page.getByRole('heading', { name: 'Variante de tamaño' })).toBeVisible();
  await page.getByLabel('Ancho máximo (mm)').fill('60');
  await page.getByLabel('Alto máximo (mm)').fill('45');
  await page.getByRole('button', { name: 'Generar variante' }).click();
  await expect(page).not.toHaveURL(originalUrl);
  await expect(page.getByRole('link', { name: 'Descargar archivo JEF' })).toBeVisible({ timeout: JEF_TIMEOUT_MS });
  const variantWidth = await measuredWidth();
  expect(variantWidth).toBeLessThan(originalWidth * 0.9); // 60 mm de destino frente a 80 mm: el bordado se regeneró más chico
  const variantJef = await downloadJef(page, 'anillo-variante.jef', true);
  expect(variantJef.bytes.length).toBeGreaterThan(JEF_MAGIC_BYTES_MIN);
  expect(variantJef.bytes.equals(bytes)).toBe(false);
  await page.goto(originalUrl);
  await expect(page.getByRole('link', { name: 'Descargar archivo JEF' })).toBeVisible(); // el origen sigue con su JEF
  expect(await measuredWidth()).toBe(originalWidth);
  writeFileSync(`${OUT_DIR}/variante.json`, JSON.stringify({ originalWidth, variantWidth, variantBytes: variantJef.bytes.length }, null, 2));
});

// La referencia real del proyecto (1122 × 1402 px): la capa casi blanca se omite y quedan dos hilos.
const ANIME_SOCKS = new URL('../fixtures/h2/Anime_Socks.png', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

test('Anime Socks: del PNG al JEF real, con el aviso de lo que se quitó', async ({ page }) => {
  const started = Date.now();
  await openImageProject(page, 'Anime Socks JEF real');
  await page.getByLabel('Elegir archivo').setInputFiles(ANIME_SOCKS);
  await expect(page.getByText('Imagen para analizar', { exact: true })).toBeVisible();
  await page.getByRole('radio', { name: 'Sin análisis de IA' }).check();
  await page.getByLabel('Ancho máximo (mm)').fill('150');
  await page.getByLabel('Alto máximo (mm)').fill('150');
  await page.getByLabel('Cantidad de colores').fill('3');
  await page.getByRole('button', { name: 'Generar bordado' }).click();
  await expect(page.getByText('Hay un elemento que necesita revisión')).toBeVisible({ timeout: JEF_TIMEOUT_MS });
  const jobMs = Date.now() - started;
  await expect(page.locator('.metrics')).toBeVisible();

  const { bytes } = await downloadJef(page, 'anime-socks.jef', false);
  expect(bytes.length).toBeGreaterThan(JEF_MAGIC_BYTES_MIN);

  writeFileSync(`${OUT_DIR}/anime-socks.json`, JSON.stringify({
    jobMs, jefBytes: bytes.length, statSize: statSync(`${OUT_DIR}/anime-socks.jef`).size,
    issuesOnScreen: await page.locator('.issue').allInnerTexts(),
    downloadRows: await page.locator('.list__item').allInnerTexts(),
    metrics: await page.locator('.metrics').allInnerTexts(),
  }, null, 2));
  await page.screenshot({ path: `${OUT_DIR}/anime-socks.png`, fullPage: true });
});
