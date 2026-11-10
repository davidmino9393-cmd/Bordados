import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { ApiClient } from '../../api/ApiClient';
import { ApiProvider } from '../../api/ApiProvider';
import { InscriptionLayout, type InscriptionReport } from '../../contracts/inscriptions';
import { createMockApiClient } from '../../mocks/MockApiClient';
import { InscriptionNotice } from './InscriptionNotice';

const SIZE = { width_mm: 100, height_mm: 100 };

function report(over: Partial<InscriptionReport> = {}): InscriptionReport {
  return {
    schema_version: '0.1-inscriptions', available: true, unavailable_reason: null, small_below_mm: 5, duration_ms: 12, method: 'm',
    inscriptions: [
      { inscription_id: 'inscription_1', text: 'MUNICIPALIDAD DE EL FORTIN', confidence: 0.998, layout: InscriptionLayout.Curved,
        bounds_px: [0, 0, 600, 600], letter_height_px: 50, letter_height_mm: 1.7, small: true, confirmed_text: null },
      { inscription_id: 'inscription_2', text: 'TALLER', confidence: 0.97, layout: InscriptionLayout.Straight,
        bounds_px: [0, 700, 300, 90], letter_height_px: 200, letter_height_mm: 6.8, small: false, confirmed_text: null },
    ],
    ...over,
  };
}

function renderNotice(overrides: Partial<ApiClient>, onSubmit = vi.fn((e: Event) => e.preventDefault())) {
  const client: ApiClient = { ...createMockApiClient(), ...overrides };
  render(
    <ApiProvider client={client}>
      <form onSubmit={(e) => onSubmit(e.nativeEvent)}>
        <InscriptionNotice projectId="p1" assetId="a1" widthMm={100} heightMm={100} />
      </form>
    </ApiProvider>,
  );
  return onSubmit;
}

describe('texto encontrado en la imagen (guía 1.3)', () => {
  it('muestra cada frase con su altura de letra y avisa las que quedan chicas', async () => {
    const getInscriptions = vi.fn(async () => report());
    renderNotice({ getInscriptions });
    const curved = await screen.findByLabelText('Texto en curva (letras de ~1,7 mm de alto)');
    expect(curved).toHaveValue('MUNICIPALIDAD DE EL FORTIN');
    expect(screen.getByLabelText('Texto (letras de ~6,8 mm de alto)')).toHaveValue('TALLER');
    expect(screen.getByText(/Las letras de menos de 5,0 mm se pierden al trazarlas.*Leído con 100% de confianza\./)).toBeInTheDocument();
    expect(getInscriptions).toHaveBeenCalledWith('p1', 'a1', SIZE);
  });

  it('guarda la frase corregida y avisa que quedó guardada', async () => {
    const confirmInscriptions = vi.fn(async () => report());
    renderNotice({ getInscriptions: async () => report(), confirmInscriptions });
    const field = await screen.findByLabelText(/Texto en curva/);
    await userEvent.clear(field);
    await userEvent.type(field, 'Municipalidad de El Fortín');
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar frases' }));
    expect(await screen.findByText('Frases confirmadas y guardadas con la imagen.')).toBeInTheDocument();
    expect(confirmInscriptions).toHaveBeenCalledWith('p1', 'a1', [
      { inscription_id: 'inscription_1', text: 'Municipalidad de El Fortín' },
      { inscription_id: 'inscription_2', text: 'TALLER' },
    ], SIZE);
  });

  it('Enter en una frase la confirma y no envía el formulario de ajustes', async () => {
    const confirmInscriptions = vi.fn(async () => report());
    const onSubmit = renderNotice({ getInscriptions: async () => report(), confirmInscriptions });
    fireEvent.keyDown(await screen.findByLabelText(/Texto en curva/), { key: 'Enter' });
    expect(await screen.findByText('Frases confirmadas y guardadas con la imagen.')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('sin lector en el servidor lo dice', async () => {
    renderNotice({ getInscriptions: async () => report({ available: false, unavailable_reason: 'x', inscriptions: [] }) });
    expect(await screen.findByText('La búsqueda de texto no está instalada en este servidor.')).toBeInTheDocument();
  });

  it('si la búsqueda falla lo dice sin bloquear', async () => {
    renderNotice({ getInscriptions: async () => { throw new Error('boom'); } });
    expect(await screen.findByText(/No se pudo buscar texto en la imagen.*podés generar igual/)).toBeInTheDocument();
  });
});
