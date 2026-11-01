import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, screen } from '@testing-library/react';
import { createHttpApiClient } from './api/HttpApiClient';
import type { ApiClient } from './api/ApiClient';
import { createMockApiClient } from './mocks/MockApiClient';
import { advance, generateFrom, instrument, pngFile, renderApp, setupUser, svgFile } from './test-utils';

const FULL_RUN_MS = 8000;
const TTL_MS = 300_000;
const READY = 'Listo para prueba (digital)';

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('recorrido principal (cliente SIMULADO)', () => {
  it('muestra el aviso de datos simulados', () => {
    renderApp();
    expect(screen.getByRole('note')).toHaveTextContent('Datos simulados');
  });

  it('sigue el flujo inicial: proyecto, asset, revisión inicial (base null) y recién entonces el job', async () => {
    const user = setupUser();
    const { client, calls } = instrument();
    renderApp(client);
    await generateFrom(user, pngFile('logo.png'));

    const order = calls.map((c) => c.method).filter((m) => ['createProject', 'uploadAsset', 'createInitialRevision', 'createJob'].includes(m));
    expect(order).toEqual(['createProject', 'uploadAsset', 'createInitialRevision', 'createJob']);
    const revision = calls.find((c) => c.method === 'createInitialRevision')!.args[1] as { base_revision_id: null };
    expect(revision.base_revision_id).toBeNull();
    const job = calls.find((c) => c.method === 'createJob')!.args[1] as { revision_id: string; input_kind: string };
    expect(job.revision_id).toMatch(/^rev_sim_/);
    expect(job.input_kind).toBe('raster_image');
  });

  it('genera, muestra datos y distingue "listo para prueba" de muestra aprobada', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);

    expect((await screen.findAllByText(READY)).length).toBeGreaterThan(0);
    expect(screen.getByText('Sin probar en tela')).toBeInTheDocument();
    expect(screen.queryByText('Muestra física aprobada')).not.toBeInTheDocument();
    expect(screen.getByText('Medidas del archivo generado')).toBeInTheDocument();
    expect(screen.getByText(/ejecución en la máquina no está verificada/)).toBeInTheDocument();
    expect(screen.getByAltText('Original')).toBeInTheDocument();
    expect(screen.getByAltText('Vector')).toBeInTheDocument();
    expect(screen.getByAltText('Puntadas del archivo releído')).toBeInTheDocument();

    const downloads = screen.getAllByRole('link', { name: /Descargar/ });
    expect(downloads).toHaveLength(6);
    downloads.forEach((link) => expect(link.getAttribute('download')).toMatch(/^job_sim_\d+-/));
    expect(screen.getByRole('link', { name: /Descargar Archivo de bordado/ }).getAttribute('download')).toMatch(/-mock\.jef$/);
  });

  it('registra como omitidas las etapas de análisis y vectorización de un SVG preparado', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, svgFile('preparado.svg'));
    expect(screen.getAllByText('Omitida')).toHaveLength(2);
  });

  it('informa un fallo con etapa y causa, y no ofrece descargas', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo-fallo.png'));
    await advance(FULL_RUN_MS);

    expect(await screen.findByText('No se pudo generar el bordado')).toBeInTheDocument();
    expect(screen.getByText('Falló la exportación del bordado')).toBeInTheDocument();
    expect(screen.getByText(/Falló en la etapa: Generación de puntadas/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();
    expect(screen.queryByText(READY)).not.toBeInTheDocument();
  });

  it('reintentar crea un job nuevo sobre la misma revisión', async () => {
    const user = setupUser();
    const { client, calls } = instrument();
    renderApp(client);
    await generateFrom(user, pngFile('logo-fallo.png'));
    await advance(FULL_RUN_MS);
    await user.click(await screen.findByRole('button', { name: 'Reintentar con los mismos ajustes' }));
    await screen.findByRole('heading', { name: 'Generación del bordado' });

    const jobs = calls.filter((c) => c.method === 'createJob').map((c) => c.args[1] as { revision_id: string });
    expect(jobs).toHaveLength(2);
    expect(jobs[1].revision_id).toBe(jobs[0].revision_id);
    expect(calls.filter((c) => c.method === 'createInitialRevision')).toHaveLength(1);
  });

  it('cancelar solo solicita: se ve "cancelación solicitada" hasta que el servidor publica cancelled', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo.png'));
    await advance(1200);
    await user.click(screen.getByRole('button', { name: 'Cancelar generación' }));

    expect(await screen.findByText(/Cancelación solicitada/)).toBeInTheDocument();
    expect(screen.queryByText('Generación cancelada')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancelar generación' })).not.toBeInTheDocument();

    await advance(2000);
    expect(await screen.findByText('Generación cancelada')).toBeInTheDocument();
    await advance(FULL_RUN_MS);
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();
  });

  it('pide revisión localizada y regenera con una corrección', async () => {
    const user = setupUser();
    const { client, calls } = instrument();
    renderApp(client);
    await generateFrom(user, pngFile('logo-revision.png'));
    await advance(FULL_RUN_MS);

    expect(await screen.findByText('Hay un elemento que necesita revisión')).toBeInTheDocument();
    expect(screen.getAllByText(/No se pudo verificar la correspondencia/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/object_mock_satin/).length).toBeGreaterThan(0);
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Aplicar y regenerar' }));
    expect(screen.getByText('Elegí al menos una corrección para regenerar.')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/Qué querés hacer \(object_mock_satin\)/), 'Excluir del bordado');
    await user.click(screen.getByRole('button', { name: 'Aplicar y regenerar' }));
    await screen.findByRole('heading', { name: 'Generación del bordado' });
    const request = calls.find((c) => c.method === 'createDerivedRevision')!.args[1];
    expect(request).toMatchObject({
      kind: 'correction',
      corrections: [{ action: 'exclude_region', object_id: 'object_mock_satin' }],
    });
    await advance(FULL_RUN_MS);
    expect((await screen.findAllByText(READY)).length).toBeGreaterThan(0);
  });

  it('crea una variante de tamaño como trabajo nuevo y la enlaza al origen', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);
    await screen.findByText('Variante de tamaño');

    const width = screen.getByLabelText('Ancho máximo (mm)');
    await user.clear(width);
    await user.type(width, '90');
    await user.click(screen.getByRole('button', { name: 'Generar variante' }));
    await screen.findByRole('heading', { name: 'Generación del bordado' });
    await advance(FULL_RUN_MS);

    await user.click(await screen.findByRole('link', { name: /Prueba/ }));
    expect(await screen.findByText(/Derivado de otro trabajo/)).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Abrir' })).toHaveLength(2);
  });

  it('renueva los enlaces antes de que venzan (TTL de 300 s) sin conservarlos más allá de expires_at', async () => {
    const user = setupUser();
    const { client, count } = instrument();
    renderApp(client);
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);
    await screen.findByText('Medidas del archivo generado');
    expect(count('getArtifacts')).toBe(1);

    await advance(TTL_MS - 30_000);
    expect(count('getArtifacts')).toBe(1);
    await advance(30_000);
    expect(count('getArtifacts')).toBeGreaterThan(1);
  });

  it('si el enlace ya venció al descargar, vuelve a pedirlo y usa el nuevo', async () => {
    const user = setupUser();
    const base = createMockApiClient();
    let calls = 0;
    const client: ApiClient = {
      ...base,
      async getArtifacts(jobId) {
        const manifest = await base.getArtifacts(jobId);
        calls += 1;
        if (calls > 2) return manifest;
        // Las dos primeras respuestas simulan un enlace ya vencido (p. ej. pestaña dormida).
        const past = '2020-01-01T00:00:00Z';
        manifest.artifacts = manifest.artifacts.map((a) => ({
          ...a,
          download: { url: 'https://vencido.invalid/x', issued_at: past, expires_at: past },
        }));
        return manifest;
      },
    };
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(this.href);
    });
    const clicked: string[] = [];
    renderApp(client);
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);
    await screen.findByText('Medidas del archivo generado');

    await user.click(screen.getByRole('link', { name: /Descargar Archivo de bordado/ }));
    await advance(100);
    expect(calls).toBe(3);
    expect(click).toHaveBeenCalled();
    expect(clicked.at(-1)).toMatch(/^data:/);
    expect(clicked.at(-1)).not.toContain('vencido.invalid');
  });

  it('valida el tamaño antes de enviar y no crea trabajos', async () => {
    const user = setupUser();
    const { client, count } = instrument();
    renderApp(client);
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'P');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    await user.upload(await screen.findByLabelText('Elegir archivo'), pngFile('logo.png'));
    await screen.findByAltText('Imagen original: logo.png');

    const width = screen.getByLabelText('Ancho máximo (mm)');
    await user.clear(width);
    await user.type(width, '0');
    await user.click(screen.getByRole('button', { name: 'Generar bordado' }));
    expect(screen.getByText('Ingresá un número mayor que cero.')).toBeInTheDocument();
    expect(count('createInitialRevision')).toBe(0);
    expect(count('createJob')).toBe(0);
  });

  it('arma el bastidor desde el catálogo y avisa si el área lo excede', async () => {
    const user = setupUser();
    const { client, calls } = instrument();
    renderApp(client);
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'P');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    await user.upload(await screen.findByLabelText('Elegir archivo'), pngFile('logo.png'));
    await screen.findByAltText('Imagen original: logo.png');

    await user.selectOptions(screen.getByLabelText('Bastidor'), 'Bastidor chico (SIMULADO)');
    expect(screen.getByText(/mayor que el bastidor \(126 × 110 mm\)/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Generar bordado' }));
    await screen.findByRole('heading', { name: 'Generación del bordado' });
    const settings = (calls.find((c) => c.method === 'createInitialRevision')!.args[1] as { settings: { hoop: object; hoop_profile: string } }).settings;
    expect(settings.hoop_profile).toBe('sim_small');
    expect(settings.hoop).toMatchObject({ profile_id: 'sim_small', width_mm: 126, height_mm: 110, jef_hoop_code: 1 });
  });

  it('deshabilita el proveedor local no disponible y explica por qué', async () => {
    const user = setupUser();
    renderApp(createMockApiClient({ ollamaAvailable: false }));
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'P');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    await user.upload(await screen.findByLabelText('Elegir archivo'), pngFile('logo.png'));
    await screen.findByAltText('Imagen original: logo.png');
    expect(screen.getByRole('radio', { name: /Ollama/ })).toBeDisabled();
    expect(screen.getByText(/No se usará otro proveedor/)).toBeInTheDocument();
  });

  it('rechaza un formato no admitido sin llamar al servidor', async () => {
    const user = setupUser({ applyAccept: false });
    const { client, count } = instrument();
    renderApp(client);
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'P');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    await user.upload(await screen.findByLabelText('Elegir archivo'), new File(['x'], 'foto.gif', { type: 'image/gif' }));
    expect(await screen.findByText(/formato no está admitido/)).toBeInTheDocument();
    expect(count('uploadAsset')).toBe(0);
  });

  it('no muestra archivos que el servidor atribuya a otro trabajo', async () => {
    const user = setupUser();
    const base = createMockApiClient();
    renderApp({
      ...base,
      async getArtifacts(jobId) {
        const manifest = await base.getArtifacts(jobId);
        return { ...manifest, artifacts: manifest.artifacts.map((a) => ({ ...a, job_id: 'job_ajeno' })) };
      },
    });
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);

    expect(await screen.findByText(/no pertenecen a este trabajo/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();
  });
});

describe('cliente real (HttpApiClient)', () => {
  it('si el servidor aún responde 501 informa que la operación no está ofrecida y no marca datos simulados', async () => {
    const api = createHttpApiClient({ fetchImpl: (async () => new Response('', { status: 501 })) as unknown as typeof fetch });
    renderApp(api);
    expect(await screen.findByRole('alert')).toHaveTextContent('todavía no ofrece esta operación');
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });
});
