import { expect, test, type Page } from '@playwright/test';

// Recorridos contra el cliente SIMULADO. Se identifican por el nombre del archivo subido.
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);
const RUN_TIMEOUT_MS = 20_000;

async function generate(page: Page, filename: string) {
  await page.goto('/');
  await page.getByLabel('Nombre del proyecto').fill('Prueba e2e');
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
  await page.getByLabel('Elegir archivo').setInputFiles({ name: filename, mimeType: 'image/png', buffer: PNG_1X1 });
  await expect(page.getByAltText(`Imagen original: ${filename}`)).toBeVisible();
  await page.getByRole('button', { name: 'Generar bordado' }).click();
  await expect(page.getByRole('heading', { name: 'Generación del bordado' })).toBeVisible();
}

async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

test('muestra el aviso de datos simulados', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('note')).toContainText('Datos simulados');
  await expectNoHorizontalScroll(page);
});

test('éxito: etapas reales, listo para prueba y descarga del trabajo correcto', async ({ page }) => {
  await generate(page, 'logo.png');
  await expect(page.getByText('Listo para prueba (digital)').first()).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await expect(page.getByText('Sin probar en tela')).toBeVisible();
  await expect(page.getByText('Muestra física aprobada')).toHaveCount(0);
  await expect(page.getByAltText('Puntadas del archivo releído')).toBeVisible();
  await expectNoHorizontalScroll(page);

  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: /Descargar Archivo de bordado/ }).click();
  expect((await download).suggestedFilename()).toMatch(/^job_sim_\d+\.jef$/);
});

test('fallo: causa visible y sin descargas', async ({ page }) => {
  await generate(page, 'logo-fallo.png');
  await expect(page.getByText('No se pudo generar el bordado')).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await expect(page.getByRole('link', { name: /Descargar/ })).toHaveCount(0);
  await expectNoHorizontalScroll(page);
});

test('cancelación: queda cancelado y sin archivos', async ({ page }) => {
  await generate(page, 'logo.png');
  await page.getByRole('button', { name: 'Cancelar generación' }).click();
  await expect(page.getByText('Generación cancelada')).toBeVisible();
  await page.waitForTimeout(3000);
  await expect(page.getByText('Listo para prueba (digital)')).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Descargar/ })).toHaveCount(0);
});

test('revisión localizada: corrige y regenera', async ({ page }) => {
  await generate(page, 'logo-revision.png');
  await expect(page.getByText('Hay un elemento que necesita revisión')).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await expect(page.getByText(/Elementos: obj_007/)).toBeVisible();
  await expectNoHorizontalScroll(page);
  await page.getByLabel(/Qué querés hacer \(obj_007\)/).selectOption({ label: 'Excluir del bordado' });
  await page.getByRole('button', { name: 'Aplicar y regenerar' }).click();
  await expect(page.getByText('Listo para prueba (digital)').first()).toBeVisible({ timeout: RUN_TIMEOUT_MS });
});
