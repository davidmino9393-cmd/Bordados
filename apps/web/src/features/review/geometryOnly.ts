import { ArtifactKind } from '../../contracts/artifacts';
import type { JobResponse } from '../../contracts/job';

/** H2: el servidor publicó la geometría (SVG editable) pero todavía no hay archivo de bordado (JEF). */
export function isGeometryOnly(job: JobResponse): boolean {
  const manifest = job.artifact_manifest;
  return !!manifest && !manifest.artifacts.some((a) => a.kind === ArtifactKind.Jef);
}

/**
 * Las correcciones crean una revisión derivada: el servidor solo las admite para un SVG preparado. Una imagen se
 * corrige subiendo otra imagen o cambiando el tamaño; con JEF o sin él, aquí no hay nada que aplicar.
 */
export function canCorrect(job: JobResponse): boolean {
  return job.input_kind !== 'raster_image' && !isGeometryOnly(job);
}

/** Una imagen que ya tiene JEF: sus parámetros de puntada son los de referencia del servidor, no los de la persona. */
export function isRasterWithJef(job: JobResponse): boolean {
  return job.input_kind === 'raster_image' && !!job.artifact_manifest?.artifacts.some((a) => a.kind === ArtifactKind.Jef);
}
