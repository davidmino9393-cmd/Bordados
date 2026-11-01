// Utilidades de prueba. Los flujos usan el cliente SIMULADO con reloj falso.
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { App } from './App';
import { ApiProvider } from './api/ApiProvider';
import type { ApiClient } from './api/ApiClient';
import { createMockApiClient } from './mocks/MockApiClient';

export function setupUser(options: { applyAccept?: boolean } = {}) {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi), ...options });
}

export function renderApp(client: ApiClient = createMockApiClient()) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <ApiProvider client={client}>
        <App />
      </ApiProvider>
    </MemoryRouter>,
  );
}

export async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

export const pngFile = (name: string) => new File(['x'], name, { type: 'image/png' });
export const svgFile = (name: string) => new File(['<svg/>'], name, { type: 'image/svg+xml' });

/** Recorre la UI: crea el proyecto, sube el archivo y pulsa "Generar bordado". */
export async function generateFrom(user: ReturnType<typeof setupUser>, file: File, projectName = 'Prueba') {
  await user.type(screen.getByLabelText('Nombre del proyecto'), projectName);
  await user.click(screen.getByRole('button', { name: 'Crear proyecto' }));
  const input = await screen.findByLabelText('Elegir archivo');
  await user.upload(input, file);
  await screen.findByAltText(`Imagen original: ${file.name}`);
  await user.click(screen.getByRole('button', { name: 'Generar bordado' }));
  await screen.findByRole('heading', { name: 'Progreso' });
}
