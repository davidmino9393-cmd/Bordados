import { ArtifactKind } from '../../contracts/artifacts';
import type { JobResponse } from '../../contracts/job';

/** H2: el servidor publicó la geometría (SVG editable) pero todavía no hay archivo de bordado (JEF). */
export function isGeometryOnly(job: JobResponse): boolean {
  const manifest = job.artifact_manifest;
  return !!manifest && !manifest.artifacts.some((a) => a.kind === ArtifactKind.Jef);
}
