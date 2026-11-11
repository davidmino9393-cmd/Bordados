import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ApiProvider } from '../../api/ApiProvider';
import type { ApiClient } from '../../api/ApiClient';
import type { AuthorizedArtifactManifest } from '../../contracts/artifacts';
import type { JobResponse } from '../../contracts/job';
import { createMockApiClient } from '../../mocks/MockApiClient';
import { JefHero } from './JefHero';

const NOW = Date.now();
const MANIFEST = {
  job_id: 'job_1',
  artifacts: [{
    artifact_id: 'job_1_jef', job_id: 'job_1', kind: 'jef', filename: 'logo.jef', media_type: 'application/octet-stream', sha256: 'a'.repeat(64),
    byte_size: 16780, derived_from: 'export', download_url: null, expires_at: null,
    download: { url: 'https://example.invalid/jef', issued_at: new Date(NOW).toISOString(), expires_at: new Date(NOW + 300_000).toISOString() },
  }],
} as unknown as AuthorizedArtifactManifest;

const CHECKS = [
  { kind: 'file', outcome: 'passed', method: 'relectura' },
  { kind: 'geometry', outcome: 'not_run', method: 'not implemented in H0-04' },
  { kind: 'satin', outcome: 'not_run', method: 'not implemented in H0-04' },
];

function job(over: Partial<JobResponse> = {}): JobResponse {
  return {
    job_id: 'job_1', sewout_status: 'untested', issues: [],
    validation_report: { checks: CHECKS, digital_checks_passed: false },
    ...over,
  } as unknown as JobResponse;
}

function renderHero(value: JobResponse) {
  const client: ApiClient = { ...createMockApiClient(), getArtifacts: async () => MANIFEST };
  return render(<ApiProvider client={client}><JefHero job={value} /></ApiProvider>);
}

describe('JEF con controles pendientes', () => {
  it('muestra los not_run y el estado digital y físico, y nunca dice listo para coser', async () => {
    renderHero(job());
    expect(await screen.findByText(/todavía no está validado para coser/)).toBeInTheDocument();
    expect(screen.getByText('Controles digitales: NO pasaron.')).toBeInTheDocument();
    expect(screen.getByText(/Aprobación física: sin probar/)).toBeInTheDocument();
    expect(screen.getAllByText('NO SE EJECUTÓ')).toHaveLength(2);
    expect(screen.queryByText(/listo para coser/i, { selector: 'h1,h2,h3,strong,button,a' })).toBeNull();
  });

  it('la descarga está bloqueada hasta confirmar y la confirmación lista los controles pendientes', async () => {
    const user = userEvent.setup();
    renderHero(job());
    const button = await screen.findByRole('button', { name: 'Descargar JEF (con avisos)' });
    expect(button).toBeDisabled();
    expect(screen.queryByRole('link', { name: /Descargar JEF/ })).toBeNull();
    const confirm = screen.getByRole('checkbox', { name: /Geometría: NO SE EJECUTÓ; Satén: NO SE EJECUTÓ/ });
    await user.click(confirm);
    const link = await screen.findByRole('link', { name: 'Descargar JEF (con avisos)' });
    expect(link).toHaveAttribute('href', 'https://example.invalid/jef');
    expect(screen.queryByRole('button', { name: /Descargar JEF/ })).toBeNull();
  });

  it('muestra la incidencia LEGIBILITY_RISK y avisa que la técnica por objeto no viene en esta versión del motor', async () => {
    const risk = { code: 'LEGIBILITY_RISK', severity: 'review_required', stage: 'digitizing', object_ids: ['obj_1'], region_ids: [], description: 'El 60% del trazo es más fino que 0,6 mm.', evidence: {}, suggested_correction: '' };
    renderHero(job({ issues: [risk] as unknown as JobResponse['issues'] }));
    expect(await screen.findByText('Riesgo de legibilidad')).toBeInTheDocument();
    expect(screen.getByText('El 60% del trazo es más fino que 0,6 mm.')).toBeInTheDocument();
    expect(screen.getByText(/todavía no informa la técnica de cada objeto/)).toBeInTheDocument();
  });

  it('con la técnica en la evidencia la lista por objeto', async () => {
    const risk = { code: 'LEGIBILITY_RISK', severity: 'review_required', stage: 'digitizing', object_ids: ['obj_1'], region_ids: [], description: 'd', evidence: { technique_by_object: { obj_1: 'running' } }, suggested_correction: '' };
    renderHero(job({ issues: [risk] as unknown as JobResponse['issues'] }));
    expect(await screen.findByText(/obj_1 → running/)).toBeInTheDocument();
  });

  it('sin informe de controles lo dice y también pide confirmación', async () => {
    renderHero(job({ validation_report: null }));
    expect(await screen.findByText(/no hay informe, así que no se puede afirmar que pasaron/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Descargar JEF/ })).toBeDisabled();
  });

  it('con controles pasados y muestra aprobada se descarga directo', async () => {
    const passed = CHECKS.map((c) => ({ ...c, outcome: 'passed' }));
    renderHero(job({ validation_report: { checks: passed, digital_checks_passed: true } as unknown as JobResponse['validation_report'], sewout_status: 'approved' }));
    expect(await screen.findByRole('link', { name: 'Descargar JEF (con avisos)' })).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).toBeNull();
  });
});
