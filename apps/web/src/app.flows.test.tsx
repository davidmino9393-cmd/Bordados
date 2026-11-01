import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, screen, within } from '@testing-library/react';
import { httpApiClient } from './api/HttpApiClient';
import { createMockApiClient } from './mocks/MockApiClient';
import { advance, generateFrom, pngFile, renderApp, setupUser, svgFile } from './test-utils';

const FULL_RUN_MS = 8000;

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('recorrido principal (cliente SIMULADO)', () => {
  it('muestra el aviso de datos simulados', () => {
    renderApp();
    expect(screen.getByRole('note')).toHaveTextContent('Datos simulados');
  });

  it('genera, muestra datos y distingue "listo para prueba" de muestra aprobada', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo.png'));
    await advance(FULL_RUN_MS);

    expect((await screen.findAllByText('Listo para prueba (digital)')).length).toBeGreaterThan(0);
    expect(screen.getByText('Sin probar en tela')).toBeInTheDocument();
    expect(screen.queryByText('Muestra física aprobada')).not.toBeInTheDocument();
    expect(screen.getByText('Medidas del archivo generado')).toBeInTheDocument();
    expect(screen.getByAltText('Original')).toBeInTheDocument();
    expect(screen.getByAltText('Vector')).toBeInTheDocument();
    expect(screen.getByAltText('Puntadas del archivo releído')).toBeInTheDocument();

    const downloads = screen.getAllByRole('link', { name: /Descargar/ });
    expect(downloads).toHaveLength(5);
    downloads.forEach((link) => expect(link.getAttribute('download')).toMatch(/^job_sim_\d+/));
  });

  it('registra como omitidas las etapas de análisis y vectorización de un SVG preparado', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, svgFile('preparado.svg'));
    const stages = within(screen.getByRole('list', { name: '' }) as HTMLElement);
    expect(stages.getAllByText('Omitida')).toHaveLength(2);
  });

  it('informa un fallo con etapa y causa, y no ofrece descargas', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo-fallo.png'));
    await advance(FULL_RUN_MS);

    expect(await screen.findByText('No se pudo generar el bordado')).toBeInTheDocument();
    expect(screen.getByText(/Falló en la etapa: Generación de puntadas/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar con los mismos ajustes' })).toBeEnabled();
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();
    expect(screen.queryByText('Listo para prueba (digital)')).not.toBeInTheDocument();
  });

  it('cancela una generación en curso sin dejar descargas', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo.png'));
    await advance(1200);
    await user.click(screen.getByRole('button', { name: 'Cancelar generación' }));

    expect(await screen.findByText('Generación cancelada')).toBeInTheDocument();
    await advance(FULL_RUN_MS);
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancelar generación' })).not.toBeInTheDocument();
  });

  it('pide revisión localizada y regenera con una corrección', async () => {
    const user = setupUser();
    renderApp();
    await generateFrom(user, pngFile('logo-revision.png'));
    await advance(FULL_RUN_MS);

    expect(await screen.findByText('Hay un elemento que necesita revisión')).toBeInTheDocument();
    expect(screen.getByText(/Una columna de satin es demasiado angosta/)).toBeInTheDocument();
    expect(screen.getByText(/Elementos: obj_007/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Descargar/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Aplicar y regenerar' }));
    expect(screen.getByText('Elegí al menos una corrección para regenerar.')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/Qué querés hacer \(obj_007\)/), 'Excluir del bordado');
    await user.click(screen.getByRole('button', { name: 'Aplicar y regenerar' }));
    await screen.findByRole('heading', { name: 'Progreso' });
    await advance(FULL_RUN_MS);
    expect((await screen.findAllByText('Listo para prueba (digital)')).length).toBeGreaterThan(0);
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
    await screen.findByRole('heading', { name: 'Progreso' });
    await advance(FULL_RUN_MS);

    await user.click(await screen.findByRole('link', { name: /Prueba/ }));
    expect(await screen.findByText(/Derivado de otro trabajo/)).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Abrir' })).toHaveLength(2);
  });

  it('valida el tamaño antes de enviar y no crea trabajos', async () => {
    const user = setupUser();
    renderApp();
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'P');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    await user.upload(await screen.findByLabelText('Elegir archivo'), pngFile('logo.png'));
    await screen.findByAltText('Imagen original: logo.png');

    const width = screen.getByLabelText('Ancho máximo (mm)');
    await user.clear(width);
    await user.type(width, '0');
    await user.click(screen.getByRole('button', { name: 'Generar bordado' }));
    expect(screen.getByText('Ingresá un número mayor que cero.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Progreso' })).not.toBeInTheDocument();
  });

  it('deshabilita el proveedor local no disponible y explica por qué', async () => {
    const user = setupUser();
    renderApp(createMockApiClient({ ollamaAvailable: false }));
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'P');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    await screen.findByLabelText('Elegir archivo');
    expect(screen.getByRole('radio', { name: /Ollama/ })).toBeDisabled();
    expect(screen.getByText(/No se usará otro proveedor/)).toBeInTheDocument();
  });

  it('rechaza un formato no admitido sin llamar al servidor', async () => {
    const user = setupUser({ applyAccept: false });
    renderApp();
    await user.type(screen.getByLabelText('Nombre del proyecto'), 'P');
    await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
    const input = await screen.findByLabelText('Elegir archivo');
    await user.upload(input, new File(['x'], 'foto.gif', { type: 'image/gif' }));
    expect(await screen.findByText(/formato no está admitido/)).toBeInTheDocument();
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

  it('con el cliente real bloqueado informa que los contratos no están congelados', async () => {
    renderApp(httpApiClient);
    expect(await screen.findByRole('alert')).toHaveTextContent('contratos v0.1 no están congelados');
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });
});
