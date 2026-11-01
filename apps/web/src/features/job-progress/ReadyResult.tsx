import { useApi } from '../../api/ApiProvider';
import type { Job } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { SewoutBadge } from '../../shared/components/Badges';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { useAsync } from '../../shared/hooks/useAsync';
import { ArtifactsPanel } from '../artifacts/ArtifactsPanel';
import { guardArtifacts } from '../artifacts/artifactGuard';
import { IssuesList } from '../artifacts/IssuesList';
import { MetricsPanel } from '../artifacts/MetricsPanel';
import { ComparePanel } from '../compare/ComparePanel';
import { VariantForm } from '../variants/VariantForm';

/**
 * Resultado digital. "Listo para prueba" viene del estado del backend; la UI
 * nunca lo deduce ni lo envía, y la muestra física se informa por separado.
 */
export function ReadyResult({ job, asset }: { job: Job; asset: SourceAsset | undefined }) {
  const api = useApi();
  const manifest = useAsync(() => api.getArtifacts(job.id), [api, job.id]);
  const guarded = manifest.data ? guardArtifacts(manifest.data, job.id) : null;

  return (
    <>
      <Notice tone={NoticeTone.Success} title={es.result.readyTitle}>
        <p>{es.result.readyText}</p>
      </Notice>
      <Card>
        <Card.Header>{es.result.sewoutTitle}</Card.Header>
        <Card.Body>
          <SewoutBadge status={job.sewout_status} />
        </Card.Body>
      </Card>
      {manifest.error && <Notice tone={NoticeTone.Error}>{manifest.error}</Notice>}
      {guarded && (
        <>
          <ComparePanel asset={asset} artifacts={guarded.artifacts} />
          {guarded.metrics && <MetricsPanel metrics={guarded.metrics} />}
          <IssuesList issues={job.diagnostics} />
          <ArtifactsPanel artifacts={guarded.artifacts} hadMismatch={guarded.hadMismatch} />
        </>
      )}
      <VariantForm job={job} />
    </>
  );
}
