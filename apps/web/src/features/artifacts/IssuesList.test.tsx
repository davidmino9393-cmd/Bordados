import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Issue } from '../../contracts/validation';
import { IssuesList } from './IssuesList';

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
  it('agrupa los avisos internos en una indicación para revisar el diseño', () => {
    render(<IssuesList issues={unmappedWarnings(14)} />);
    expect(screen.getByText('Revisá el diseño en la vista de puntadas.')).toBeInTheDocument();
    expect(screen.queryByText(/satin_0|SATIN_RUNG_WARNING|Satin has no rungs|Faltan guías/)).not.toBeInTheDocument();
  });

  it('conserva una descripción legible de cada problema público aunque el motor lo repita', () => {
    const internal = unmappedWarnings(1)[0];
    const tooLarge = { ...internal, code: 'DIMENSIONS_EXCEEDED' };
    const mismatch = { ...internal, code: 'VISUAL_MISMATCH' };
    render(<IssuesList issues={[internal, tooLarge, tooLarge, mismatch]} />);
    expect(screen.getByText(/La medida real supera el tamaño pedido/)).toBeInTheDocument();
    expect(screen.getByText(/El bordado no es idéntico a tu imagen/)).toBeInTheDocument();
    expect(screen.queryByText(/satin_0|Satin has no rungs/)).not.toBeInTheDocument();
  });
});
