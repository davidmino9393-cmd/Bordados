import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// Accesibilidad con axe-core sobre la UI real (cliente SIMULADO), en escritorio y móvil.
// Reglas: WCAG 2.0/2.1/2.2 A y AA más las buenas prácticas de axe. Contraste incluido.
const RUN_TIMEOUT_MS = 20_000;
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'];
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);
const SVG = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>');

async function expectAccessible(page: Page, where: string) {
  const { violations } = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const report = violations.map(
    (v) => `${v.id} (${v.impact}): ${v.help}\n   ${v.nodes.map((n) => n.target.join(' ')).slice(0, 4).join('\n   ')}`,
  );
  expect.soft(report, `Problemas de accesibilidad en «${where}»`).toEqual([]);
}

async function openProject(page: Page, file?: { name: string; mimeType: string; buffer: Buffer }) {
  await page.goto('/');
  await page.getByLabel('Nombre del proyecto').fill('Prueba a11y');
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
  await expect(page.getByLabel('Elegir archivo')).toBeVisible();
  if (!file) return;
  await page.getByLabel('Elegir archivo').setInputFiles(file);
  await expect(page.getByText(new RegExp(`${file.name.replace('.', '\\.')} · `))).toBeVisible();
}

const generate = async (page: Page) => {
  await page.getByRole('button', { name: 'Generar bordado' }).click();
  await expect(page.getByRole('heading', { name: 'Generación del bordado' })).toBeVisible();
};

test('proyectos: lista vacía y lista con un proyecto', async ({ page }) => {
  await page.goto('/');
  await expectAccessible(page, 'proyectos (vacío)');
  await page.getByLabel('Nombre del proyecto').fill('Prueba a11y');
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
  await page.getByRole('link', { name: 'Proyectos' }).click();
  await expect(page.getByRole('link', { name: 'Prueba a11y' })).toBeVisible();
  await expectAccessible(page, 'proyectos (con uno)');
});

test('proyecto: sin imagen y con imagen y ajustes (validación visible)', async ({ page }) => {
  await openProject(page);
  await expectAccessible(page, 'proyecto sin imagen');
  await page.getByLabel('Elegir archivo').setInputFiles({ name: 'logo.png', mimeType: 'image/png', buffer: PNG_1X1 });
  await expect(page.getByAltText('Imagen original: logo.png')).toBeVisible();
  // Orden 4: el tamaño lo fija el bastidor (ya no hay ancho ni alto que escribir); la validación visible es la de colores.
  await page.getByLabel('Cantidad de colores').fill('0');
  await page.getByRole('button', { name: 'Generar bordado' }).click();
  await expect(page.getByText(/Elegí entre 1 y \d+ colores\./)).toBeVisible();
  await expectAccessible(page, 'proyecto con imagen y error de validación');
  await page.getByLabel('Bastidor').selectOption({ label: 'Bastidor chico (SIMULADO)' });
  await expectAccessible(page, 'proyecto con aviso de bastidor');
});

test('trabajo en curso y fallido', async ({ page }) => {
  await openProject(page, { name: 'logo-fallo.png', mimeType: 'image/png', buffer: PNG_1X1 });
  await generate(page);
  await expectAccessible(page, 'trabajo en curso');
  await expect(page.getByText('No se pudo generar el bordado')).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await expectAccessible(page, 'trabajo fallido');
});

test('trabajo cancelado', async ({ page }) => {
  await openProject(page, { name: 'logo.png', mimeType: 'image/png', buffer: PNG_1X1 });
  await generate(page);
  await page.getByRole('button', { name: 'Cancelar generación' }).click();
  await expect(page.getByText('Generación cancelada')).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await expectAccessible(page, 'trabajo cancelado');
});

test('resultado listo para prueba (con formulario de muestra y variantes)', async ({ page }) => {
  await openProject(page, { name: 'logo.png', mimeType: 'image/png', buffer: PNG_1X1 });
  await generate(page);
  await expect(page.getByText('Medidas del archivo generado')).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await expectAccessible(page, 'resultado listo');
  await page.getByRole('button', { name: 'Registrar muestra' }).click();
  await expect(page.getByText('Completá este dato.').first()).toBeVisible();
  await expectAccessible(page, 'resultado listo con errores de validación del formulario');
});

test('revisión localizada con archivos (14 incidencias)', async ({ page }) => {
  await openProject(page, { name: 'logo-completo.svg', mimeType: 'image/svg+xml', buffer: SVG });
  await generate(page);
  await expect(page.getByText('Hay un elemento que necesita revisión')).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await expectAccessible(page, 'revisión con archivos');
});

test('teclado: se crea un proyecto sin mouse y todo lo enfocable muestra el foco', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Nombre del proyecto').focus();
  await page.keyboard.type('Solo teclado');
  await page.keyboard.press('Enter');
  await expect(page.getByLabel('Elegir archivo')).toBeVisible();
  await expect(page).toHaveTitle('Solo teclado · Bordados con IA');

  // Recorremos con Tab: cada elemento enfocado debe tener un contorno visible (WCAG 2.4.7).
  await page.locator('body').click({ position: { x: 1, y: 1 } });
  const seen = new Set<string>();
  for (let i = 0; i < 25; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const style = getComputedStyle(el);
      return {
        id: `${el.tagName}:${el.getAttribute('aria-label') ?? el.textContent?.slice(0, 20) ?? ''}`,
        outline: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2,
      };
    });
    if (!info) continue;
    seen.add(info.id);
    expect(info.outline, `Sin foco visible en ${info.id}`).toBe(true);
  }
  expect(seen.size).toBeGreaterThan(5);
});

test('imagen para analizar: carga con aviso experimental y pantalla de análisis (H2)', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Nombre del proyecto').fill('Prueba a11y');
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
  const base64 = await page.evaluate(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 800;
    canvas.height = 600;
    canvas.getContext('2d')!.fillRect(0, 0, 800, 600);
    return canvas.toDataURL('image/png').split(',')[1];
  });
  await page.getByLabel('Elegir archivo').setInputFiles({ name: 'logo-ambiguo.png', mimeType: 'image/png', buffer: Buffer.from(base64, 'base64') });
  await expect(page.getByText('Función experimental')).toBeVisible();
  await expectAccessible(page, 'carga de imagen con proveedor experimental');
  await generate(page);
  await expect(page.getByText('Revisá el análisis de la imagen')).toBeVisible({ timeout: RUN_TIMEOUT_MS });
  await page.getByRole('checkbox', { name: /Zona difusa/ }).check();
  await expectAccessible(page, 'análisis visual con una región marcada');
});
