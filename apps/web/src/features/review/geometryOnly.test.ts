import { describe, expect, it } from 'vitest';
import { ArtifactKind } from '../../contracts/artifacts';
import type { JobResponse } from '../../contracts/job';
import { canCorrect, isGeometryOnly, isRasterWithJef } from './geometryOnly';

function job(inputKind: JobResponse['input_kind'], kinds: ArtifactKind[] | null): JobResponse {
  return {
    input_kind: inputKind,
    artifact_manifest: kinds && { artifacts: kinds.map((kind) => ({ kind })) },
  } as unknown as JobResponse;
}

describe('qué se puede hacer con un trabajo en revisión', () => {
  it('una imagen con JEF no admite correcciones y muestra el JEF arriba', () => {
    const value = job('raster_image', [ArtifactKind.Jef, ArtifactKind.EditableSvg]);
    expect(isRasterWithJef(value)).toBe(true);
    expect(canCorrect(value)).toBe(false);
    expect(isGeometryOnly(value)).toBe(false);
  });

  it('una imagen sin JEF es solo geometría: sin correcciones y sin JEF arriba', () => {
    const value = job('raster_image', [ArtifactKind.EditableSvg]);
    expect([isGeometryOnly(value), canCorrect(value), isRasterWithJef(value)]).toEqual([true, false, false]);
  });

  it('un SVG preparado con JEF conserva las correcciones y no usa el aviso de parámetros de referencia', () => {
    const value = job('prepared_svg', [ArtifactKind.Jef]);
    expect([canCorrect(value), isRasterWithJef(value)]).toEqual([true, false]);
  });

  it('un trabajo sin manifiesto no es solo geometría ni tiene JEF', () => {
    const value = job('raster_image', null);
    expect([isGeometryOnly(value), isRasterWithJef(value)]).toEqual([false, false]);
  });
});
