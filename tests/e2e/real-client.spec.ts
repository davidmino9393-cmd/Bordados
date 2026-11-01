import { readFileSync } from 'node:fs';
import { expect, test, type Page, type Route } from '@playwright/test';

// Estas pruebas usan el cliente HTTP REAL de la web (sin VITE_USE_MOCKS). El servidor es un
// STUB dentro del test que responde con los fixtures de contratos-v0.1 (simulated=true).
// No prueban el backend: prueban que la web habla el protocolo congelado.
const fixture = (name: string) =>
  JSON.parse(readFileSync(new URL(`../../apps/web/mocks/${name}.json`, import.meta.url), 'utf-8')).payload;
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);
const TTL_MS = 300_000;
const JOB_ID = 'job_stub_1';

interface Recorded {
  method: string;
  path: string;
  idempotencyKey: string | undefined;
  body: unknown;
}

function stubBackend(page: Page, options: { jobsStatus: 202 | 501; result?: 'ready' | 'failed' }) {
  const recorded: Recorded[] = [];
  const project = { schema_version: '0.1', project_id: 'project_stub_1', name: 'Prueba real', created_at: '2026-11-01T10:00:00Z' };
  let asset: Record<string, unknown> | null = null;
  let settings: unknown = null;
  let jobCreated = false;

  const send = (route: Route, status: number, body: unknown) =>
    route.fulfill({
      status,
      contentType: 'application/json',
      headers: { 'X-Request-ID': 'req_stub', 'Cache-Control': 'no-store' },
      body: JSON.stringify(body),
    });
  const fresh = (url: string) => {
    const now = Date.now();
    return { url, issued_at: new Date(now).toISOString(), expires_at: new Date(now + TTL_MS).toISOString() };
  };
  const jobBase = (status: string) => {
    const ready = fixture('valid-result');
    return { ...ready, job_id: JOB_ID, project_id: project.project_id, revision_id: 'rev_stub_1', asset_id: 'asset_stub_1', settings_snapshot: settings, status };
  };
  const failedJob = () => ({
    ...fixture('failure'),
    job_id: JOB_ID,
    project_id: project.project_id,
    revision_id: 'rev_stub_1',
    asset_id: 'asset_stub_1',
    settings_snapshot: settings,
  });
  const readyJob = () => {
    if (options.result === 'failed') return failedJob();
    const job = jobBase('ready_for_sewout');
    job.artifact_manifest = { ...job.artifact_manifest, job_id: JOB_ID, revision_id: 'rev_stub_1', artifacts: job.artifact_manifest.artifacts.map((a: object) => ({ ...a, job_id: JOB_ID })) };
    job.validation_report = { ...job.validation_report, job_id: JOB_ID, revision_id: 'rev_stub_1' };
    return job;
  };

  return {
    recorded,
    install: () =>
      page.route('**/api/v1/**', async (route) => {
        const request = route.request();
        const path = new URL(request.url()).pathname.replace('/api/v1', '');
        const method = request.method();
        recorded.push({
          method,
          path,
          idempotencyKey: request.headers()['idempotency-key'],
          body: request.postData()?.startsWith('{') ? JSON.parse(request.postData()!) : undefined,
        });
        if (method === 'GET' && path === '/profiles') return send(route, 200, fixture('profiles'));
        if (method === 'GET' && path === '/projects') return send(route, 200, { schema_version: '0.1', items: [project], next_cursor: null });
        if (method === 'POST' && path === '/projects') return send(route, 201, project);
        if (method === 'GET' && path === `/projects/${project.project_id}`) {
          const assets = asset ? [{ ...asset, original_download: fresh('data:image/png;base64,' + PNG_1X1.toString('base64')) }] : [];
          const jobs = jobCreated ? [readyJob()] : [];
          return send(route, 200, { schema_version: '0.1', project, assets, jobs, assets_next_cursor: null, jobs_next_cursor: null });
        }
        if (method === 'POST' && path.endsWith('/assets')) {
          asset = {
            schema_version: '0.1', asset_id: 'asset_stub_1', project_id: project.project_id, sha256: 'a'.repeat(64),
            media_type: 'image/png', original_filename: 'logo.png', original_download: null,
            original_width_px: 1, original_height_px: 1, crop_px: null, original_preserved: true,
          };
          return send(route, 201, asset);
        }
        if (method === 'POST' && path.endsWith('/revisions')) {
          settings = (JSON.parse(request.postData()!) as { settings: unknown }).settings;
          return send(route, 201, {
            schema_version: '0.1', revision_id: 'rev_stub_1', project_id: project.project_id, base_revision_id: null,
            reason: 'Ajustes iniciales', created_at: '2026-11-01T10:00:00Z', kind: 'initial', parent_job_id: null, job_id: null,
          });
        }
        if (method === 'POST' && path.endsWith('/jobs')) {
          if (options.jobsStatus === 501) return route.fulfill({ status: 501, body: '' });
          jobCreated = true;
          return send(route, 202, { ...jobBase('queued'), stages: [], artifact_manifest: null, validation_report: null, diagnostics: [], issues: [] });
        }
        if (method === 'GET' && path === `/jobs/${JOB_ID}`) return send(route, 200, readyJob());
        if (method === 'GET' && path === `/jobs/${JOB_ID}/artifacts`) {
          const manifest = readyJob().artifact_manifest;
          manifest.artifacts = manifest.artifacts.map((a: { kind: string }) => {
            const download = fresh(`data:text/plain,${a.kind}`);
            return { ...a, download, download_url: download.url, expires_at: download.expires_at };
          });
          return send(route, 200, manifest);
        }
        return route.fulfill({ status: 404, body: '' });
      }),
  };
}

async function fillAndGenerate(page: Page) {
  await page.goto('/');
  await page.getByLabel('Nombre del proyecto').fill('Prueba real');
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
  await page.getByLabel('Elegir archivo').setInputFiles({ name: 'logo.png', mimeType: 'image/png', buffer: PNG_1X1 });
  await expect(page.getByAltText('Imagen original: logo.png')).toBeVisible();
  await page.getByRole('button', { name: 'Generar bordado' }).click();
}

test('sin datos simulados: el cliente real sigue el flujo inicial y tolera 501 en /jobs', async ({ page }) => {
  const backend = stubBackend(page, { jobsStatus: 501 });
  await backend.install();
  await fillAndGenerate(page);

  await expect(page.getByRole('note')).toHaveCount(0);
  await expect(page.getByText(/todavía no ofrece esta operación/)).toBeVisible();
  await expect(page.getByText(/Código de incidencia: NOT_IMPLEMENTED/)).toBeVisible();
  const posts = backend.recorded.filter((r) => r.method === 'POST');
  expect(posts.map((r) => r.path)).toEqual([
    '/projects',
    '/projects/project_stub_1/assets',
    '/projects/project_stub_1/revisions',
    '/projects/project_stub_1/jobs',
  ]);
  posts.forEach((r) => expect(r.idempotencyKey).toBeTruthy());
  const revision = posts[2].body as { base_revision_id: null; settings: { hoop_profile: string; hoop: { profile_id: string } } };
  expect(revision.base_revision_id).toBeNull();
  expect(revision.settings.hoop.profile_id).toBe(revision.settings.hoop_profile);
  const job = posts[3].body as { revision_id: string; asset_id: string };
  expect(job).toMatchObject({ revision_id: 'rev_stub_1', asset_id: 'asset_stub_1' });
});

test('con respuestas del contrato: muestra el resultado digital y descarga con URL emitida por GET artifacts', async ({ page }) => {
  const backend = stubBackend(page, { jobsStatus: 202 });
  await backend.install();
  await fillAndGenerate(page);

  await expect(page.getByText('Listo para prueba (digital)').first()).toBeVisible();
  await expect(page.getByText('Sin probar en tela')).toBeVisible();
  await expect(page.getByText('Muestra física aprobada')).toHaveCount(0);
  await expect(page.getByText('Medidas del archivo generado')).toBeVisible();
  expect(backend.recorded.some((r) => r.method === 'GET' && r.path === `/jobs/${JOB_ID}/artifacts`)).toBe(true);
  await expect(page.getByRole('link', { name: /Descargar\s*Archivo de bordado/ })).toHaveAttribute('href', 'data:text/plain,jef');
});

test('fallo del worker: muestra la etapa y el código de incidencia que informa el contrato', async ({ page }) => {
  const backend = stubBackend(page, { jobsStatus: 202, result: 'failed' });
  await backend.install();
  await fillAndGenerate(page);

  await expect(page.getByText('No se pudo generar el bordado')).toBeVisible();
  await expect(page.getByText('Código de incidencia: WORKER_EXPORT_FAILED')).toBeVisible();
  await expect(page.getByText(/Falló en la etapa: Generación de puntadas/)).toBeVisible();
  await expect(page.getByRole('link', { name: /Descargar/ })).toHaveCount(0);
  expect(backend.recorded.some((r) => r.path.endsWith('/artifacts'))).toBe(false);
});
