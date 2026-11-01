import type { JobResponse } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { SewoutBadge } from '../../shared/components/Badges';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { ArtifactsPanel } from '../artifacts/ArtifactsPanel';
import { guardArtifacts } from '../artifacts/artifactGuard';
import { IssuesList } from '../artifacts/IssuesList';
import { MetricsPanel } from '../artifacts/MetricsPanel';
import { useArtifacts } from '../artifacts/useArtifacts';
import { ComparePanel } from '../compare/ComparePanel';
import { SewoutForm } from '../sewout/SewoutForm';
import { VariantForm } from '../variants/VariantForm';

interface ReadyResultProps {
  job: JobResponse;
  asset: SourceAsset | undefined;
  onJobChanged: (job: JobResponse) => void;
}

/**
 * Resultado digital. "Listo para prueba" viene del estado del backend; la UI
 * nunca lo deduce ni lo envía, y la muestra física se informa por separado.
 */
export function ReadyResult({ job, asset, onJobChanged }: ReadyResultProps) {
  const { manifest, error, refresh } = useArtifacts(job.job_id);
  const guarded = manifest ? guardArtifacts(manifest, job.job_id) : null;
  const record = job.sewout_record;

  return (
    <>
      <Notice tone={NoticeTone.Success} title={es.result.readyTitle}>
        <p>{es.result.readyText}</p>
      </Notice>
      <Card>
        <Card.Header>{es.result.sewoutTitle}</Card.Header>
        <Card.Body>
          <SewoutBadge status={job.sewout_status} />
          {record && (
            <p className="field__hint">
              {record.tested_at && `${es.result.sewoutTestedOn(new Date(record.tested_at).toLocaleDateString('es-AR'))} · `}
              {record.observations}
            </p>
          )}
        </Card.Body>
      </Card>
      <SewoutForm job={job} onJobChanged={onJobChanged} />
      {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
      {guarded && (
        <>
          <ComparePanel asset={asset} artifacts={guarded.artifacts} />
          {guarded.metrics && <MetricsPanel metrics={guarded.metrics} />}
          <IssuesList issues={job.diagnostics ?? []} />
          <ArtifactsPanel artifacts={guarded.artifacts} hadMismatch={guarded.hadMismatch} refresh={refresh} />
        </>
      )}
      <VariantForm job={job} />
    </>
  );
}
