import { describe, expect, it } from 'vitest';
import sewoutFixture from '../../../mocks/physical-sewout.json';
import { toSewoutRequest, validateSewout, type SewoutFormValues } from './validateSewout';

const NOW = Date.parse('2026-11-01T15:00:00Z');
const valid: SewoutFormValues = {
  status: 'approved',
  tested_at: '2026-11-01T11:00',
  fabric_profile: 'gabardina_inicial',
  stabilizer: 'Cut-away',
  thread: 'Poliéster 40',
  observations: 'Sin arrugas.',
};

describe('validateSewout', () => {
  it('acepta un registro completo', () => {
    expect(validateSewout(valid, NOW)).toEqual({});
  });

  it('exige resultado, tela, estabilizador, hilo y observaciones', () => {
    const errors = validateSewout({ ...valid, status: '', fabric_profile: '', stabilizer: ' ', thread: '', observations: '' }, NOW);
    expect(errors).toEqual({
      status: 'required',
      fabric_profile: 'required',
      stabilizer: 'required',
      thread: 'required',
      observations: 'required',
    });
  });

  it('un resultado físico exige fecha y no admite una futura', () => {
    expect(validateSewout({ ...valid, tested_at: '' }, NOW)).toEqual({ tested_at: 'required' });
    expect(validateSewout({ ...valid, status: 'needs_adjustment', tested_at: '' }, NOW)).toEqual({ tested_at: 'required' });
    expect(validateSewout({ ...valid, tested_at: '2999-01-01T00:00' }, NOW)).toEqual({ tested_at: 'future' });
  });

  it('"sin probar" no necesita fecha', () => {
    expect(validateSewout({ ...valid, status: 'untested', tested_at: '' }, NOW)).toEqual({});
  });

  it('rechaza textos más largos que el contrato', () => {
    expect(validateSewout({ ...valid, observations: 'x'.repeat(2001) }, NOW)).toEqual({ observations: 'tooLong' });
  });
});

describe('toSewoutRequest', () => {
  it('arma el SewoutRecord con las mismas claves que el fixture del contrato', () => {
    const request = toSewoutRequest(valid, 'rev_1');
    expect(Object.keys(request).sort()).toEqual(Object.keys(sewoutFixture.payload).sort());
    expect(request).toMatchObject({
      schema_version: '0.1',
      revision_id: 'rev_1',
      status: 'approved',
      fabric_profile: 'gabardina_inicial',
      photo_asset_ids: [],
    });
  });

  it('envía la fecha en UTC con zona explícita (AwareDatetime)', () => {
    const request = toSewoutRequest(valid, 'rev_1');
    expect(request.tested_at).toBe(new Date('2026-11-01T11:00').toISOString());
    expect(request.tested_at).toMatch(/Z$/);
  });

  it('"sin probar" va con tested_at null y los textos recortados', () => {
    const request = toSewoutRequest({ ...valid, status: 'untested', tested_at: '2026-11-01T11:00', stabilizer: '  Tear-away ' }, 'rev_1');
    expect(request.tested_at).toBeNull();
    expect(request.stabilizer).toBe('Tear-away');
  });
});
