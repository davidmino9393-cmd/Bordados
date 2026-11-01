import { useState } from 'react';
import { useApi } from '../../api/ApiProvider';
import type { JobResponse } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { ArtifactsPanel } from '../artifacts/ArtifactsPanel';
import { guardArtifacts } from '../artifacts/artifactGuard';
import { IssuesList } from '../artifacts/IssuesList';
import { MetricsPanel } from '../artifacts/MetricsPanel';
import { useArtifacts } from '../artifacts/useArtifacts';
import { ComparePanel } from '../compare/ComparePanel';

interface JobFilesProps {
  job: JobResponse;
  asset: SourceAsset | undefined;
  /** Para publicar el trabajo reconsultado al reintentar. */
  onJobChanged: (job: JobResponse) => void;
  /** Falso cuando otra sección ya muestra las incidencias (revisión). */
  showIssues?: boolean;
}

/** Comparación, medidas releídas y descargas del trabajo; los enlaces (300 s) se renuevan solos. */
export function JobFiles({ job, asset, onJobChanged, showIssues = true }: JobFilesProps) {
  const api = useApi();
  const { manifest, error, refresh } = useArtifacts(job.job_id);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string>();
  const guarded = manifest ? guardArtifacts(manifest, job.job_id) : null;

  // Primero se reconsulta el trabajo (su estado pudo cambiar) y después los archivos.
  const retry = async () => {
    setRetrying(true);
    setRetryError(undefined);
    try {
      onJobChanged(await api.getJob(job.job_id));
      await refresh();
    } catch (e) {
      setRetryError(errorMessage(e));
    } finally {
      setRetrying(false);
    }
  };

  return (
    <>
      {(error || retryError) && (
        <Notice tone={NoticeTone.Error}>
          <p>{retryError ?? error}</p>
          <div className="row">
            <button type="button" className="secondary" onClick={retry} disabled={retrying}>
              {retrying ? es.result.retryingFiles : es.result.retryFiles}
            </button>
          </div>
        </Notice>
      )}
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
