import { expect, test, type Page } from '@playwright/test';

declare global {
  interface Window {
    __mockApiCalls?: string[];
  }
}

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
  await page.getByRole('link', { name: /Descargar\s*Archivo de bordado/ }).click();
  expect((await download).suggestedFilename()).toMatch(/^job_sim_\d+-mock\.jef$/);
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
  await expect(page.getByText(/object_mock_satin/).first()).toBeVisible();
  await expectNoHorizontalScroll(page);
  await page.getByLabel(/Qué querés hacer \(object_mock_satin\)/).selectOption({ label: 'Excluir del bordado' });
  await page.getByRole('button', { name: 'Aplicar y regenerar' }).click();
  await expect(page.getByText('Listo para prueba (digital)').first()).toBeVisible({ timeout: RUN_TIMEOUT_MS });
});

// --- Job completo (SIMULADO): SVG preparado en needs_review, con archivos y 14 incidencias de satén ---
const SVG_VALIDO = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>');
const SATIN_ISSUES = 14;
const SHORT_TTL_MS = 1500;
const stampOf = (url: string) => Number(url.split('#issued=')[1]);

test('job completo en needs_review: incidencias, muestra física, descarga del JEF y enlace vencido', async ({ page }) => {
  await page.goto(`/?mockDownloadTtlMs=${SHORT_TTL_MS}&mockTrace=1`);
  await page.getByLabel('Nombre del proyecto').fill('Prueba completo');
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
  await page.getByLabel('Elegir archivo').setInputFiles({ name: 'logo-completo.svg', mimeType: 'image/svg+xml', buffer: SVG_VALIDO });
  // Un SVG no trae vista previa del original (original_download llega null): se espera el nombre del archivo.
  await expect(page.getByText(/logo-completo\.svg · /)).toBeVisible();
  await page.getByRole('button', { name: 'Generar bordado' }).click();

  // needs_review: nunca "listo para prueba", pero con archivos y muestra física.
  await expect(page.getByText('Hay un elemento que necesita revisión')).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await expect(page.locator('.issue')).toHaveCount(SATIN_ISSUES);
  // object_ids reales del backend (H0-04): los 14 avisos los listan todos.
  await expect(page.getByLabel(/Qué querés hacer \(satin_A_descenso_0\)/)).toBeVisible();
  await expect(page.getByLabel(/Qué querés hacer \(satin_n_0\)/)).toBeVisible();
  await expect(page.locator('.issue').first()).toContainText('satin_SOCKS_S_1_0');
  await expect(page.getByText('Archivos para revisar: no están listos para prueba')).toBeVisible();
  await expect(page.getByText('Listo para prueba (digital)')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Registrar muestra física' })).toBeVisible();
  await expect(page.getByText('150,0 × 142,8 mm')).toBeVisible();
  await expectNoHorizontalScroll(page);

  // El JEF está habilitado; lo bajamos con el enlace vigente.
  const jef = page.getByRole('link', { name: /Descargar\s*Archivo de bordado/ });
  await expect(jef).toBeEnabled();
  const firstHref = (await jef.getAttribute('href'))!;
  const artifactCalls = () => page.evaluate(() => (window.__mockApiCalls ?? []).filter((m) => m === 'getArtifacts').length);
  const callsAtStart = await artifactCalls();
  expect(callsAtStart).toBeGreaterThanOrEqual(1);

  // Pasa el TTL: la web vuelve a pedir GET artifacts y el enlace cambia por uno nuevo.
  await page.waitForTimeout(SHORT_TTL_MS + 1500);
  expect(await artifactCalls()).toBeGreaterThan(callsAtStart);
  const freshHref = (await jef.getAttribute('href'))!;
  expect(stampOf(freshHref)).toBeGreaterThan(stampOf(firstHref));

  const download = page.waitForEvent('download');
  await jef.click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/-output\.jef$/);
  expect(stampOf(file.url())).toBeGreaterThanOrEqual(stampOf(freshHref));
});
