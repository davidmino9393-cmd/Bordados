import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ArtifactKind, type Artifact, type DerivedFrom } from '../../contracts/artifacts';
import { ComparePanel } from './ComparePanel';

function artifact(kind: ArtifactKind, derived_from: DerivedFrom, url: string): Artifact {
  return {
    artifact_id: `a_${kind}`, job_id: 'job_1', kind, filename: `${kind}.bin`, media_type: 'image/png', sha256: 'a'.repeat(64),
    byte_size: 10, derived_from, download: { url, issued_at: '2026-11-09T00:00:00Z', expires_at: '2026-11-09T00:05:00Z' },
    download_url: url, expires_at: '2026-11-09T00:05:00Z',
  };
}

const ARTIFACTS = [
  artifact(ArtifactKind.EditableSvg, 'document', 'http://x/vector.svg'),
  artifact(ArtifactKind.Jef, 'export', 'http://x/d.jef'),
  artifact(ArtifactKind.PreviewPng, 'jef_reread', 'http://x/preview.png'),
];

describe('ComparePanel', () => {
  it('muestra el vector y el bordado, y amplía y cierra la vista que se toca', async () => {
    const user = userEvent.setup();
    render(<ComparePanel asset={undefined} artifacts={ARTIFACTS} />);
    expect(screen.getByAltText('Vector')).toHaveAttribute('src', 'http://x/vector.svg');
    expect(screen.queryByAltText('Ampliar: Vector')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Ampliar: Vector' }));
    expect(screen.getByAltText('Ampliar: Vector')).toHaveAttribute('src', 'http://x/vector.svg');
    expect(screen.getByRole('button', { name: 'Ampliar: Vector' })).toHaveAttribute('aria-pressed', 'true');

    await user.click(screen.getByRole('button', { name: 'Cerrar ampliación' }));
    expect(screen.queryByAltText('Ampliar: Vector')).not.toBeInTheDocument();
  });

  it('una vista sin archivo no se puede ampliar', () => {
    render(<ComparePanel asset={undefined} artifacts={ARTIFACTS} />);
    expect(screen.queryByRole('button', { name: 'Ampliar: Original' })).not.toBeInTheDocument();
  });
});
