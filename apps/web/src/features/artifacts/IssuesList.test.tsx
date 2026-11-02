import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Issue } from '../../contracts/validation';
import { IssuesList } from './IssuesList';

afterEach(() => vi.restoreAllMocks());

/** Forma observada en el backend real: 14 avisos idénticos, cada uno con TODOS los object_ids candidatos. */
function unmappedWarnings(count: number): Issue[] {
  const ids = Array.from({ length: count }, (_, i) => `satin_${i}`);
  return ids.map(() => ({
    code: 'SATIN_RUNG_WARNING',
    severity: 'review_required' as const,
    stage: 'satin',
    object_ids: ids,
    region_ids: [],
    description: 'Satin has no rungs',
    evidence: { localization: 'candidate columns, native warning unmapped', source_object_mapping_verified: false },
    suggested_correction: 'Revisar la evidencia de este trabajo.',
  }));
}

describe('IssuesList con avisos idénticos del backend real', () => {
  it('muestra todos los avisos sin claves repetidas ni ocultar ninguno', () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { container } = render(<IssuesList issues={unmappedWarnings(14)} />);
    expect(container.querySelectorAll('.issue')).toHaveLength(14);
    expect(screen.getAllByText(/Faltan guías en una columna de satén/)).toHaveLength(14);
    const duplicateKeyWarnings = errors.mock.calls.filter((call) => String(call[0]).includes('same key'));
    expect(duplicateKeyWarnings).toEqual([]);
  });
});
