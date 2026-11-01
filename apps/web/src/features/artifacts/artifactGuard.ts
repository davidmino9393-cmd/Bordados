import type { Artifact, ArtifactManifest } from '../../contracts/artifacts';

export interface GuardedArtifacts {
  artifacts: Artifact[];
  /** true si el servidor devolvió archivos de otro trabajo (se descartan). */
  hadMismatch: boolean;
  metrics: ArtifactManifest['metrics'];
}

/** Nunca mostrar ni descargar archivos que no pertenezcan al trabajo abierto. */
export function guardArtifacts(manifest: ArtifactManifest, jobId: string): GuardedArtifacts {
  if (manifest.job_id !== jobId) {
    return { artifacts: [], hadMismatch: true, metrics: null };
  }
  const artifacts = manifest.artifacts.filter((a) => a.job_id === jobId);
  return {
    artifacts,
    hadMismatch: artifacts.length !== manifest.artifacts.length,
    metrics: manifest.metrics,
  };
}
