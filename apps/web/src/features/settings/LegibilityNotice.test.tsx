import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiProvider } from '../../api/ApiProvider';
import type { ApiClient } from '../../api/ApiClient';
import type { LegibilityCheck } from '../../contracts/legibility';
import { createMockApiClient } from '../../mocks/MockApiClient';
import { LegibilityNotice } from './LegibilityNotice';

const WARNING = 'El 60% del trazo mide menos de 0,6 mm; a 111 mm las letras no van a quedar legibles. Para que el 80% del trazo supere 0,8 mm haría falta un dibujo de ~290 x 290 mm, que no entra en el bastidor (140 x 140 mm): no hay un tamaño útil para este dibujo.';

function check(over: Partial<LegibilityCheck> = {}): LegibilityCheck {
  return {
    schema_version: '0.1-legibility', requested_width_mm: 130, requested_height_mm: 120, ink_width_mm: 111, ink_height_mm: 111.6,
    thin_share_below_0_6_mm: 0.6, thin_share_below_0_8_mm: 0.8, ink_area_share_below_0_6_mm: 0.3, warn: true, message: WARNING,
    minimum_size: { already_legible: false, scale_factor: 2.6, ink_width_mm: 290, ink_height_mm: 290, fits_in_hoop: false, message: 'x' },
    margin_option: null, palette_cleaning_applied: true, inks: ['#ec0402'], method: 'm', ...over,
  };
}

function renderNotice(getLegibility: ApiClient['getLegibility']) {
  const client: ApiClient = { ...createMockApiClient(), getLegibility };
  return render(
    <ApiProvider client={client}>
      <LegibilityNotice projectId="p1" assetId="a1" widthMm={130} heightMm={120} colorLimit={3} hoop={{ width_mm: 140, height_mm: 140 } as never} />
    </ApiProvider>,
  );
}

describe('aviso de legibilidad antes de generar', () => {
  it('muestra el texto exacto con números, sin bloquear', async () => {
    const getLegibility = vi.fn(async () => check());
    renderNotice(getLegibility);
    expect(await screen.findByText(WARNING)).toBeInTheDocument();
    expect(screen.getByText(/no un bloqueo: podés generar igual/i)).toBeInTheDocument();
    expect(getLegibility).toHaveBeenCalledWith('p1', 'a1', { width_mm: 130, height_mm: 120, color_limit: 3, hoop_width_mm: 140, hoop_height_mm: 140 });
  });

  it('ofrece el recorte del margen con su número y aclara que no arregla las letras', async () => {
    const margin = {
      ink_bbox_px: [48, 22, 1207, 1187] as [number, number, number, number], gain_percent: 7.6, ink_width_mm_now: 111, ink_height_mm_now: 111.6,
      ink_width_mm_cropped: 119.4, ink_height_mm_cropped: 120, message: 'recortándolo pasaría de 111 a 119,4 mm (+7,6%). Es solo más tamaño: no resuelve el problema de las letras finas.',
    };
    renderNotice(async () => check({ warn: false, message: null, margin_option: margin, minimum_size: { ...check().minimum_size, already_legible: true } }));
    expect(await screen.findByText(/\+7,6%.*no resuelve el problema de las letras finas/)).toBeInTheDocument();
    expect(screen.queryByText('Aviso de legibilidad')).toBeNull();
  });

  it('si no avisa pero el 80% no llega a 0,8 mm informa el tamaño mínimo', async () => {
    renderNotice(async () => check({ warn: false, message: null, thin_share_below_0_6_mm: 0.14, minimum_size: { ...check().minimum_size, message: 'El tamaño mínimo es de ~122 x 122 mm.' } }));
    expect(await screen.findByText(/El 14% del trazo mide menos de 0,6 mm \(se avisa a partir del 30%\)\. El tamaño mínimo es de ~122 x 122 mm\./)).toBeInTheDocument();
  });

  it('si la medición falla lo dice y deja seguir', async () => {
    renderNotice(async () => { throw new Error('boom'); });
    expect(await screen.findByText(/No se pudo medir la legibilidad.*podés generar igual/)).toBeInTheDocument();
  });
});
