import type { JobResponse } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { ArtifactsPanel } from '../artifacts/ArtifactsPanel';
import { guardArtifacts } from '../artifacts/artifactGuard';
import { IssuesList } from '../artifacts/IssuesList';
import { MetricsPanel } from '../artifacts/MetricsPanel';
import { useArtifacts } from '../artifacts/useArtifacts';
import { ComparePanel } from '../compare/ComparePanel';

interface JobFilesProps {
  job: JobResponse;
  asset: SourceAsset | undefined;
  /** Falso cuando otra sección ya muestra las incidencias (revisión). */
  showIssues?: boolean;
}

/** Comparación, medidas releídas y descargas del trabajo; los enlaces (300 s) se renuevan solos. */
export function JobFiles({ job, asset, showIssues = true }: JobFilesProps) {
  const { manifest, error, refresh } = useArtifacts(job.job_id);
  const guarded = manifest ? guardArtifacts(manifest, job.job_id) : null;
  return (
    <>
      {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
      {guarded && (
        <>
          <ComparePanel asset={asset} artifacts={guarded.artifacts} />
          {guarded.metrics && <MetricsPanel metrics={guarded.metrics} />}
          {showIssues && <IssuesList issues={job.diagnostics ?? []} />}
          <ArtifactsPanel artifacts={guarded.artifacts} hadMismatch={guarded.hadMismatch} refresh={refresh} />
        </>
      )}
    </>
  );
}
