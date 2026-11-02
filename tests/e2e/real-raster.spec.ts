import { mkdirSync, writeFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

// Imagen → E1 REAL → needs_review → SVG editable descargable, contra el backend real
// levantado con real-backend/serve_with_simulated_analysis.py (solo el análisis de IA es simulado).
const OUT_DIR = 'test-results/real-raster';
const REVIEW_TIMEOUT_MS = 120_000;

test('imagen: E1 real termina en needs_review con parámetros provisionales y SVG editable descargable', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Nombre del proyecto').fill('Verificación E1 real');
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
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
  await expect(page.getByRole('radio', { name: /OpenAI/ })).toBeEnabled();
  await page.getByLabel('Ancho máximo (mm)').fill('80');
  await page.getByLabel('Alto máximo (mm)').fill('60');
  await page.getByRole('button', { name: 'Generar bordado' }).click();

  await expect(page.getByText('Hay un elemento que necesita revisión')).toBeVisible({ timeout: REVIEW_TIMEOUT_MS });
  await expect(page.getByText('Listo para prueba (digital)')).toHaveCount(0);

  // Solo geometría: sin JEF no hay correcciones de puntadas ni muestra física que registrar.
  await expect(page.getByText('Solo geometría: todavía no hay archivo de bordado')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Aplicar y regenerar' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Registrar muestra física' })).toHaveCount(0);

  // Comparación: el original (enlace firmado) y el vector (SVG editable de E1) cargan como imágenes reales.
  const original = page.getByRole('img', { name: 'Original', exact: true });
  await expect(original).toBeVisible();
  await expect.poll(() => original.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth === 640)).toBe(true);
  const vector = page.locator('figure', { hasText: 'Vector' }).locator('img');
  await expect(vector).toBeVisible();
  await expect.poll(() => vector.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);

  // Sin JEF no hay medidas releídas ni vista previa del JEF.
  await expect(page.locator('.metrics')).toHaveCount(0);

  // Descarga del SVG editable.
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: /Descargar/ }).first().click(),
  ]);
  const path = await download.path();
  expect(path).toBeTruthy();
  const { readFileSync } = await import('node:fs');
  const svg = readFileSync(path!, 'utf-8');
  expect(svg).toContain('<svg');
  expect(svg).toContain('evenodd');

  mkdirSync(OUT_DIR, { recursive: true });
  writeFileSync(`${OUT_DIR}/summary.json`, JSON.stringify({
    filename: download.suggestedFilename(), bytes: svg.length,
    issuesOnScreen: await page.locator('.issue').allInnerTexts(),
    downloadRows: await page.locator('.list__item').allInnerTexts(),
  }, null, 2));
  await page.screenshot({ path: `${OUT_DIR}/needs-review.png`, fullPage: true });
});
