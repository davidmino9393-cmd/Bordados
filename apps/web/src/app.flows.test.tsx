import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { ApiError, ClientErrorCode } from './api/ApiClient';
import { createHttpApiClient } from './api/HttpApiClient';
import { ErrorCode } from './contracts/http';
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
    expect(screen.getByText('Código de incidencia: WORKER_EXPORT_FAILED')).toBeInTheDocument();
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
    await advance(600); // la renovación automática (2.ª respuesta) también llega vencida

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

describe('accesibilidad', () => {
  it('cada pantalla tiene un título descriptivo', async () => {
    const user = setupUser();
    renderApp();
    await screen.findByRole('heading', { name: 'Proyectos' });
    expect(document.title).toBe('Proyectos · Bordados con IA');
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'Mi logo');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    await screen.findByLabelText('Elegir archivo');
    expect(document.title).toBe('Mi logo · Bordados con IA');
    await user.upload(screen.getByLabelText('Elegir archivo'), pngFile('logo.png'));
    await screen.findByAltText('Imagen original: logo.png');
    await user.click(screen.getByRole('button', { name: 'Generar bordado' }));
    await screen.findByRole('heading', { name: 'Generación del bordado' });
    expect(document.title).toBe('Generación del bordado · Bordados con IA');
  });
});

describe('muestra física (POST /sewouts)', () => {
  const FORM = 'Registrar muestra física';
  const PAST = '2026-10-01T11:00';

  async function readyPage(client: ApiClient) {
    const user = setupUser();
    renderApp(client);
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);
    await screen.findByRole('heading', { name: FORM });
    return user;
  }
  async function fill(user: ReturnType<typeof setupUser>, result: string, date: string | null = PAST) {
    await user.click(screen.getByRole('radio', { name: result }));
    if (date) fireEvent.change(screen.getByLabelText('Fecha de la muestra'), { target: { value: date } });
    await user.type(screen.getByLabelText('Estabilizador'), 'Cut-away');
    await user.type(screen.getByLabelText('Hilo'), 'Poliéster 40');
    await user.type(screen.getByLabelText('Observaciones'), 'Sin arrugas.');
  }

  it('el formulario solo aparece con el trabajo en ready_for_sewout', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo.png'));
    expect(screen.queryByRole('heading', { name: FORM })).not.toBeInTheDocument();
    await advance(FULL_RUN_MS);
    expect(await screen.findByRole('heading', { name: FORM })).toBeInTheDocument();
  });

  it('no aparece si el trabajo falló', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo-fallo.png'));
    await advance(FULL_RUN_MS);
    await screen.findByText('No se pudo generar el bordado');
    expect(screen.queryByRole('heading', { name: FORM })).not.toBeInTheDocument();
  });

  it('no aparece si el trabajo se canceló', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo.png'));
    await advance(1200);
    await user.click(screen.getByRole('button', { name: 'Cancelar generación' }));
    await advance(2000);
    await screen.findByText('Generación cancelada');
    expect(screen.queryByRole('heading', { name: FORM })).not.toBeInTheDocument();
  });

  it('también aparece en needs_review (decisión del integrador) y no cambia el estado digital', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo-revision.png'));
    await advance(FULL_RUN_MS);
    await screen.findByText('Hay un elemento que necesita revisión');
    expect(screen.getByRole('heading', { name: FORM })).toBeInTheDocument();
    // Sin archivos generados no hay descargas ni aviso de archivos no aptos.
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/no están listos para prueba/)).not.toBeInTheDocument();
  });

  it('registra una muestra aprobada: cambia el estado físico y el digital queda igual', async () => {
    const { client, calls } = instrument();
    const user = await readyPage(client);
    expect(screen.getByText('Sin probar en tela')).toBeInTheDocument();

    await fill(user, 'Aprobada');
    await user.click(screen.getByRole('button', { name: 'Registrar muestra' }));

    expect(await screen.findByText(/Muestra registrada/)).toBeInTheDocument();
    expect(await screen.findByText('Muestra física aprobada')).toBeInTheDocument();
    expect(screen.queryByText('Sin probar en tela')).not.toBeInTheDocument();
    expect(screen.getAllByText(READY).length).toBeGreaterThan(0);
    expect(screen.getByText(/Sin arrugas\./)).toBeInTheDocument();

    const sent = calls.find((c) => c.method === 'recordSewout')!.args[1] as Record<string, unknown>;
    expect(sent).toMatchObject({
      status: 'approved',
      fabric_profile: 'gabardina_inicial',
      stabilizer: 'Cut-away',
      thread: 'Poliéster 40',
      observations: 'Sin arrugas.',
      photo_asset_ids: [],
    });
    expect(sent.tested_at).toBe(new Date(PAST).toISOString());
    const job = calls.find((c) => c.method === 'createJob')!.args[1] as { revision_id: string };
    expect(sent.revision_id).toBe(job.revision_id);
  });

  it('una muestra que requiere ajustes se refleja sin tocar el estado digital', async () => {
    const user = await readyPage(instrument().client);
    await fill(user, 'Requiere ajustes');
    await user.click(screen.getByRole('button', { name: 'Registrar muestra' }));
    expect(await screen.findByText('La muestra requiere ajustes')).toBeInTheDocument();
    expect(screen.getAllByText(READY).length).toBeGreaterThan(0);
  });

  it('"sin probar" no lleva fecha y se envía con tested_at null', async () => {
    const { client, calls } = instrument();
    const user = await readyPage(client);
    await user.click(screen.getByRole('radio', { name: /Sin probar \(solo dejar constancia\)/ }));
    expect(screen.getByLabelText('Fecha de la muestra')).toBeDisabled();
    await user.type(screen.getByLabelText('Estabilizador'), 'Tear-away');
    await user.type(screen.getByLabelText('Hilo'), 'Rayón');
    await user.type(screen.getByLabelText('Observaciones'), 'Todavía no se cosió.');
    await user.click(screen.getByRole('button', { name: 'Registrar muestra' }));
    await screen.findByText(/Muestra registrada/);
    expect((calls.find((c) => c.method === 'recordSewout')!.args[1] as { tested_at: null }).tested_at).toBeNull();
    expect(screen.getByText('Sin probar en tela')).toBeInTheDocument();
  });

  it('valida los datos antes de enviar y no llama al servidor', async () => {
    const { client, count } = instrument();
    const user = await readyPage(client);
    await user.click(screen.getByRole('button', { name: 'Registrar muestra' }));
    expect(screen.getAllByText('Completá este dato.').length).toBeGreaterThanOrEqual(4);

    await user.click(screen.getByRole('radio', { name: 'Aprobada' }));
    await user.type(screen.getByLabelText('Estabilizador'), 'a');
    await user.type(screen.getByLabelText('Hilo'), 'b');
    await user.type(screen.getByLabelText('Observaciones'), 'c');
    await user.click(screen.getByRole('button', { name: 'Registrar muestra' }));
    expect(screen.getAllByText('Completá este dato.')).toHaveLength(1); // la fecha

    fireEvent.change(screen.getByLabelText('Fecha de la muestra'), { target: { value: '2999-01-01T00:00' } });
    await user.click(screen.getByRole('button', { name: 'Registrar muestra' }));
    expect(screen.getByText('La fecha no puede ser futura.')).toBeInTheDocument();
    expect(count('recordSewout')).toBe(0);
  });

  it('si el servidor rechaza el registro lo informa con su código y el estado no cambia', async () => {
    const base = createMockApiClient();
    const client: ApiClient = {
      ...base,
      async recordSewout() {
        throw new ApiError('INVALID_REQUEST', 'El servidor no aceptó algunos datos. Revisá los ajustes.', 422);
      },
    };
    const user = await readyPage(client);
    await fill(user, 'Aprobada');
    await user.click(screen.getByRole('button', { name: 'Registrar muestra' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Código de incidencia: INVALID_REQUEST');
    expect(screen.getByText('Sin probar en tela')).toBeInTheDocument();
    expect(screen.queryByText(/Muestra registrada/)).not.toBeInTheDocument();
  });
});

describe('job completo con archivos pero en needs_review (SIMULADO, fixture job-completed-real)', () => {
  const FORM = 'Registrar muestra física';
  // Los 14 object_ids reales del backend (H0-04): cada uno de los 14 avisos los lista todos.
  const REAL_IDS = [
    'satin_A_descenso_0', 'satin_A_lazo_ascenso_0', 'satin_A_lazo_ascenso_2', 'satin_A_lazo_ascenso_4',
    'satin_SOCKS_C_0', 'satin_SOCKS_K_diagonales_0', 'satin_SOCKS_K_vertical_0', 'satin_SOCKS_O_0',
    'satin_SOCKS_S_1_0', 'satin_SOCKS_S_2_0', 'satin_e_0', 'satin_i_0', 'satin_m_0', 'satin_n_0',
  ];

  it('muestra las 14 incidencias con sus object_ids, el aviso de no apto, la muestra física y las descargas', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, svgFile('logo-completo.svg'));
    await advance(FULL_RUN_MS);

    expect(await screen.findByText('Hay un elemento que necesita revisión')).toBeInTheDocument();
    // 14 filas de incidencia (el aviso superior repite el título de la primera).
    const rows = screen.getAllByText(/Faltan guías en una columna de satén/).filter((el) => el.closest('.issue'));
    expect(rows).toHaveLength(14);
    for (const id of REAL_IDS) {
      expect(screen.getByLabelText(new RegExp(`Qué querés hacer \\(${id}\\)`))).toBeInTheDocument();
    }
    // Cada aviso lista las 14 columnas candidatas (el backend no las asigna una a una).
    for (const row of rows) {
      const text = row.closest('.issue')?.textContent ?? '';
      expect(REAL_IDS.every((id) => text.includes(id))).toBe(true);
    }

    // Estado digital: nunca "listo para prueba"; los archivos se avisan como no aptos.
    expect(screen.getAllByText('Necesita tu revisión').length).toBeGreaterThan(0);
    expect(screen.queryByText(READY)).not.toBeInTheDocument();
    expect(screen.getByText('Archivos para revisar: no están listos para prueba')).toBeInTheDocument();

    // Muestra física permitida en needs_review, con el estado físico aparte.
    expect(screen.getByRole('heading', { name: FORM })).toBeInTheDocument();
    expect(screen.getByText('Sin probar en tela')).toBeInTheDocument();

    // Medidas y archivos del fixture.
    expect(screen.getByText('150,0 × 142,8 mm')).toBeInTheDocument();
    expect(screen.getByText('6.789')).toBeInTheDocument();
    // El backend real no entrega original_download para un SVG: no hay vista previa ficticia.
    expect(screen.getByText('Original').closest('figure')?.querySelector('img')).toBeNull();
    const jef = screen.getByRole('link', { name: /Descargar Archivo de bordado/ });
    expect(jef.getAttribute('download')).toMatch(/-output\.jef$/);
    expect(jef.getAttribute('href')).toMatch(/^data:/);
    expect(screen.getByRole('link', { name: /Descargar SVG editable/ }).getAttribute('download')).toMatch(/-editable\.svg$/);
  });

  it('con los 14 avisos idénticos del backend real (todos con los mismos object_ids) los muestra todos sin claves repetidas', async () => {
    const user = setupUser();
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    const base = createMockApiClient();
    const client: ApiClient = {
      ...base,
      async getJob(jobId) {
        const job = await base.getJob(jobId);
        if (!job.review) return job;
        // Como el backend real: cada aviso lista todas las columnas candidatas y se repite el mismo texto.
        const all = job.review.object_ids;
        const same = job.issues.map((issue) => ({ ...issue, object_ids: all, description: 'Satin has no rungs' }));
        return { ...job, issues: same, diagnostics: same, review: { ...job.review, issues: same } };
      },
    };
    renderApp(client);
    await generateFrom(user, svgFile('logo-completo.svg'));
    await advance(FULL_RUN_MS);
    await screen.findByText('Hay un elemento que necesita revisión');
    const rows = screen.getAllByText(/Faltan guías en una columna de satén/).filter((el) => el.closest('.issue'));
    expect(rows).toHaveLength(14);
    expect(errors.mock.calls.filter((c) => String(c[0]).includes('same key'))).toEqual([]);
  });

  it('registrar una muestra aquí no cambia el estado digital', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, svgFile('logo-completo.svg'));
    await advance(FULL_RUN_MS);
    await screen.findByRole('heading', { name: FORM });
    await user.click(screen.getByRole('radio', { name: 'Requiere ajustes' }));
    fireEvent.change(screen.getByLabelText('Fecha de la muestra'), { target: { value: '2026-10-01T11:00' } });
    await user.type(screen.getByLabelText('Estabilizador'), 'Cut-away');
    await user.type(screen.getByLabelText('Hilo'), 'Poliéster 40');
    await user.type(screen.getByLabelText('Observaciones'), 'Satén fruncido.');
    await user.click(screen.getByRole('button', { name: 'Registrar muestra' }));
    expect(await screen.findByText('La muestra requiere ajustes')).toBeInTheDocument();
    expect(screen.getAllByText('Necesita tu revisión').length).toBeGreaterThan(0);
    expect(screen.queryByText(READY)).not.toBeInTheDocument();
  });

  it('con TTL de 1 s, si el enlace vence y la renovación automática falló, al descargar re-pide GET artifacts y usa el nuevo', async () => {
    const user = setupUser();
    const base = createMockApiClient({ downloadTtlMs: 1000 });
    let calls = 0;
    const client: ApiClient = {
      ...base,
      async getArtifacts(jobId) {
        calls += 1;
        // La 2.ª consulta (renovación automática) cae: el enlace queda vencido en pantalla.
        if (calls === 2) throw new ApiError(ClientErrorCode.Timeout, 'El servidor tardó demasiado en responder.');
        return base.getArtifacts(jobId);
      },
    };
    const clicked: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(this.href);
    });
    renderApp(client);
    await generateFrom(user, svgFile('logo-completo.svg'));
    await advance(FULL_RUN_MS);
    const first = (await screen.findByRole('link', { name: /Descargar Archivo de bordado/ })).getAttribute('href')!;
    expect(calls).toBeGreaterThanOrEqual(1);
    await advance(2000); // pasa el TTL de 1 s
    expect(await screen.findByText(/Código de incidencia: TIMEOUT/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Descargar Archivo de bordado/ }).getAttribute('href')).toBe(first);

    const before = calls;
    await user.click(screen.getByRole('link', { name: /Descargar Archivo de bordado/ }));
    await advance(100);
    expect(calls).toBe(before + 1);
    const stamp = (url: string) => Number(url.split('#issued=')[1]);
    expect(clicked).toHaveLength(1);
    expect(stamp(clicked[0])).toBeGreaterThan(stamp(first));
  });
});

describe('409 al pedir los archivos aunque el job traiga manifiesto', () => {
  const MESSAGE = /No se pudieron obtener los archivos\. Reintentá\./;
  const conflict = () => new ApiError(ErrorCode.ArtifactsUnavailable, 'Los archivos todavía no están disponibles.', 409, 'req_409');

  /** getArtifacts responde 409 mientras `state.blocked` sea true. */
  function withConflict(base: ApiClient, state: { blocked: boolean }): ApiClient {
    return {
      ...base,
      async getArtifacts(jobId) {
        if (state.blocked) throw conflict();
        return base.getArtifacts(jobId);
      },
    };
  }

  it.each([
    ['listo para prueba', pngFile('logo.png'), READY],
    ['en revisión, con archivos', svgFile('logo-completo.svg'), 'Hay un elemento que necesita revisión'],
  ])('%s: avisa, no bloquea el resto de la pantalla y reintenta reconsultando primero el job', async (_name, file, restOfScreen) => {
    const user = setupUser();
    const state = { blocked: true };
    const { client, calls } = instrument(withConflict(createMockApiClient(), state));
    renderApp(client);
    await generateFrom(user, file);
    await advance(FULL_RUN_MS);

    expect(await screen.findByText(MESSAGE)).toBeInTheDocument();
    expect(screen.getByText(/Código de incidencia: ARTIFACTS_UNAVAILABLE · solicitud req_409/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();
    // El resto sigue usable.
    expect((await screen.findAllByText(restOfScreen)).length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Registrar muestra física' })).toBeInTheDocument();

    state.blocked = false;
    calls.length = 0;
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    await advance(100);

    // Primero GET /jobs/{id}, después GET /jobs/{id}/artifacts.
    const order = calls.map((c) => c.method).filter((m) => m === 'getJob' || m === 'getArtifacts');
    expect(order.slice(0, 2)).toEqual(['getJob', 'getArtifacts']);
    expect(screen.queryByText(MESSAGE)).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Descargar/ }).length).toBeGreaterThan(0);
  });

  it('si el 409 persiste, el mensaje y el botón siguen disponibles', async () => {
    const user = setupUser();
    renderApp(withConflict(createMockApiClient(), { blocked: true }));
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);
    await screen.findByText(MESSAGE);

    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    await advance(100);
    expect(screen.getByText(MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeEnabled();
    expect(screen.getAllByText(READY).length).toBeGreaterThan(0);
  });

  it('si al reintentar falla la reconsulta del job, lo informa con su código y se puede volver a intentar', async () => {
    const user = setupUser();
    const state = { blocked: true };
    const base = createMockApiClient();
    let failJob = false;
    const client = withConflict(
      {
        ...base,
        async getJob(jobId) {
          if (failJob) throw new ApiError(ClientErrorCode.Timeout, 'El servidor tardó demasiado en responder.');
          return base.getJob(jobId);
        },
      },
      state,
    );
    renderApp(client);
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);
    await screen.findByText(MESSAGE);

    failJob = true;
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    await advance(100);
    expect(screen.getAllByText(/Código de incidencia: TIMEOUT/).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeEnabled();

    failJob = false;
    state.blocked = false;
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    await advance(100);
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Descargar/ }).length).toBeGreaterThan(0);
  });
});

describe('H2: imágenes y análisis visual (SIMULADO, operaciones propuestas)', () => {
  const ANALYSIS_TITLE = 'Revisá el análisis de la imagen';
  const ANALYSIS_MS = 2600; // 0,5 s en cola + 1,5 s de análisis

  /** Espera a que la pantalla de análisis desaparezca: ya se navegó al job nuevo. */
  const leaveAnalysis = () => waitFor(() => expect(screen.queryByText(ANALYSIS_TITLE)).not.toBeInTheDocument());
  async function openProject(user: ReturnType<typeof setupUser>) {
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'Imágenes');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    return screen.findByLabelText('Elegir archivo');
  }
  async function analysisPage(name: string, client: ApiClient = createMockApiClient()) {
    const user = setupUser();
    renderApp(client);
    await generateFrom(user, pngFile(name));
    await advance(ANALYSIS_MS);
    await screen.findByText(ANALYSIS_TITLE);
    return user;
  }

  it('distingue "SVG preparado" de "imagen para analizar" y avisa que el análisis con IA es experimental', async () => {
    const user = setupUser();
    renderApp();
    const input = await openProject(user);

    await user.upload(input, pngFile('logo.png'));
    await screen.findByText(/logo\.png · /);
    expect(screen.getByText('Imagen para analizar')).toBeInTheDocument();
    expect(screen.getByText('Función experimental')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /OpenAI/ })).toBeEnabled();
    expect(screen.getByRole('radio', { name: /Ollama/ })).toBeEnabled();
    expect(screen.getByAltText('Imagen original: logo.png')).toBeInTheDocument(); // vista previa de la imagen subida

    await user.upload(input, svgFile('preparado.svg'));
    await screen.findByText(/preparado\.svg · /);
    expect(screen.getByText('SVG preparado')).toBeInTheDocument();
    expect(screen.getByText('Va directo a la generación del bordado.')).toBeInTheDocument();
    expect(screen.queryByText('Función experimental')).not.toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: /OpenAI/ })).not.toBeInTheDocument();
  });

  it('sin proveedores de IA disponibles no deja generar una imagen, pero sí un SVG preparado', async () => {
    const user = setupUser();
    const base = createMockApiClient();
    renderApp({ ...base, async getProfiles() { return { ...(await base.getProfiles()), providers: [] }; } });
    const input = await openProject(user);

    await user.upload(input, pngFile('logo.png'));
    await screen.findByText(/logo\.png · /);
    expect(screen.getByText(/no tiene proveedores de IA disponibles/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generar bordado' })).toBeDisabled();

    await user.upload(input, svgFile('preparado.svg'));
    await screen.findByText(/preparado\.svg · /);
    expect(screen.getByRole('button', { name: 'Generar bordado' })).toBeEnabled();
  });

  it('muestra regiones, texto, colores y dudas del análisis, con la zona incierta señalada', async () => {
    await analysisPage('logo-analisis.png');
    expect(screen.getByText('La IA no está segura de 1 zona')).toBeInTheDocument();
    expect(screen.getByText(/Las cajas y los textos los estimó la IA y no están verificados/)).toBeInTheDocument();
    expect(screen.getByText(/Analizado con OpenAI \(nube\) \(modelo-nube-simulado\)/)).toBeInTheDocument();
    expect(document.querySelectorAll('li[data-region-id]')).toHaveLength(6);
    expect(screen.getByText(/ESTRELLA/)).toBeInTheDocument();
    expect(screen.getAllByText('#F2B705').length).toBeGreaterThan(0);
    expect(screen.getByText('Texto muy fino: puede perderse al bordar a este tamaño')).toBeInTheDocument();
    expect(screen.getAllByText('Incierta')).toHaveLength(1);
    // Solo el análisis: todavía no hay vector, ni archivos, ni formulario de muestra.
    expect(screen.queryByRole('heading', { name: 'Registrar muestra física' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();
  });

  it('aprobar el análisis continúa con un job nuevo que omite el análisis y llega a "listo para prueba"', async () => {
    const { client, calls } = instrument();
    const user = await analysisPage('logo-analisis.png', client);
    await user.click(screen.getByRole('button', { name: 'Aprobar el análisis y continuar' }));
    await leaveAnalysis();
    const decision = calls.find((c) => c.method === 'decideAnalysis')!.args[1];
    expect(decision).toEqual({ action: 'approve', flagged_region_ids: [] });
    expect(screen.queryByText(ANALYSIS_TITLE)).not.toBeInTheDocument();
    expect(screen.getByText('Omitida')).toBeInTheDocument();
    await advance(FULL_RUN_MS);
    expect((await screen.findAllByText(READY)).length).toBeGreaterThan(0);
  });

  it('con varias dudas: marca regiones para revisión manual y las envía al aprobar', async () => {
    const { client, calls } = instrument();
    const user = await analysisPage('logo-ambiguo.png', client);
    expect(screen.getByText('La IA no está segura de 3 zonas')).toBeInTheDocument();
    expect(screen.getAllByText('Incierta')).toHaveLength(3);
    expect(screen.getByText('0 zonas marcadas para revisión manual.')).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox', { name: /Zona difusa/ }));
    await user.click(screen.getByRole('checkbox', { name: /Texto secundario/ }));
    expect(screen.getByText('2 zonas marcadas para revisión manual.')).toBeInTheDocument();
    expect(document.querySelector('rect[data-region-id="region_6"]')?.getAttribute('stroke')).toBe('#a02828');
    expect(document.querySelector('rect[data-region-id="region_1"]')?.getAttribute('stroke')).toBe('#2f5d8a');

    await user.click(screen.getByRole('button', { name: 'Aprobar el análisis y continuar' }));
    await leaveAnalysis();
    expect(calls.find((c) => c.method === 'decideAnalysis')!.args[1]).toEqual({
      action: 'approve',
      flagged_region_ids: ['region_3', 'region_6'],
    });
  });

  it('regenerar con otro proveedor crea un job nuevo analizado por ese proveedor', async () => {
    const { client, calls } = instrument();
    const user = await analysisPage('logo-ambiguo.png', client);
    expect(screen.getByRole('combobox', { name: 'Probar con otro proveedor' })).toHaveValue('ollama');
    await user.click(screen.getByRole('button', { name: 'Regenerar con otro proveedor' }));
    await leaveAnalysis();
    expect(calls.find((c) => c.method === 'decideAnalysis')!.args[1]).toEqual({ action: 'change_provider', ai_provider: 'ollama' });

    await advance(ANALYSIS_MS);
    await screen.findByText(ANALYSIS_TITLE);
    expect(screen.getByText(/Analizado con Modelo local \(Ollama\) \(modelo-local-simulado\)/)).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Probar con otro proveedor' })).toHaveValue('openai');
  });

  it('si la decisión falla lo informa con su código y se puede reintentar', async () => {
    const base = createMockApiClient();
    let fail = true;
    const client: ApiClient = {
      ...base,
      async decideAnalysis(jobId, decision, key) {
        if (fail) throw new ApiError(ClientErrorCode.NotImplemented, 'El servidor todavía no ofrece esta operación.', 501);
        return base.decideAnalysis(jobId, decision, key);
      },
    };
    const user = await analysisPage('logo-analisis.png', client);
    await user.click(screen.getByRole('button', { name: 'Aprobar el análisis y continuar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Código de incidencia: NOT_IMPLEMENTED');
    expect(screen.getByText(ANALYSIS_TITLE)).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole('button', { name: 'Aprobar el análisis y continuar' }));
    await leaveAnalysis();
  });

  it('una revisión de geometría de una imagen y la de un SVG no usan la pantalla de análisis', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo-revision.png'));
    await advance(FULL_RUN_MS);
    await screen.findByText('Hay un elemento que necesita revisión');
    expect(screen.queryByText(ANALYSIS_TITLE)).not.toBeInTheDocument();
  });
});

describe('errores esperables al consultar un trabajo', () => {
  it('un corte transitorio no detiene el seguimiento: avisa con el código y se recupera', async () => {
    const user = setupUser();
    const base = createMockApiClient();
    let failures = 0;
    const client: ApiClient = {
      ...base,
      async getJob(jobId) {
        const job = await base.getJob(jobId);
        // Tras la primera consulta, las dos siguientes caen por timeout.
        if (job.status !== 'queued' && failures < 2) {
          failures += 1;
          throw new ApiError(ClientErrorCode.Timeout, 'El servidor tardó demasiado en responder.');
        }
        return job;
      },
    };
    renderApp(client);
    await generateFrom(user, pngFile('logo.png'));
    await advance(1500);
    expect(await screen.findByText(/Código de incidencia: TIMEOUT/)).toBeInTheDocument();
    await advance(FULL_RUN_MS);
    expect((await screen.findAllByText(READY)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Código de incidencia: TIMEOUT/)).not.toBeInTheDocument();
  });

  it('un 404 al consultar el trabajo se informa con su código y no se reintenta', async () => {
    const user = setupUser();
    const base = createMockApiClient();
    let failedCalls = 0;
    const client: ApiClient = {
      ...base,
      async getJob(jobId) {
        const job = await base.getJob(jobId);
        if (job.status === 'queued') return job;
        failedCalls += 1;
        throw new ApiError('NOT_FOUND', 'No encontramos lo que buscabas.', 404);
      },
    };
    renderApp(client);
    await generateFrom(user, pngFile('logo.png'));
    await advance(10_000);
    expect(failedCalls).toBe(1);
    expect(screen.getByText(/Código de incidencia: NOT_FOUND/)).toBeInTheDocument();
  });
});

describe('cliente real (HttpApiClient)', () => {
  it('si el servidor aún responde 501 informa que la operación no está ofrecida y no marca datos simulados', async () => {
    const api = createHttpApiClient({ fetchImpl: (async () => new Response('', { status: 501 })) as unknown as typeof fetch });
    renderApp(api);
    expect(await screen.findByRole('alert')).toHaveTextContent('todavía no ofrece esta operación');
    expect(screen.getByRole('alert')).toHaveTextContent('Código de incidencia: NOT_IMPLEMENTED');
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });
});
