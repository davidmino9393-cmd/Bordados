import type { JobResponse } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { JobFiles } from '../job-progress/JobFiles';
import { PhysicalSewout } from '../sewout/PhysicalSewout';
import { ReviewPanel } from './ReviewPanel';

interface ReviewResultProps {
  job: JobResponse;
  asset: SourceAsset | undefined;
  onJobChanged: (job: JobResponse) => void;
}

/**
 * needs_review: incidencias por corregir y, si el servidor ya generó archivos, esos archivos
 * con un aviso claro de que NO están listos para prueba. La muestra física se puede
 * registrar igual (decisión del integrador); no cambia el estado digital.
 */
export function ReviewResult({ job, asset, onJobChanged }: ReviewResultProps) {
  return (
    <>
      <ReviewPanel job={job} asset={asset} />
      {job.artifact_manifest && (
        <>
          <Notice tone={NoticeTone.Warning} title={es.review.filesNotReadyTitle}>
            <p>{es.review.filesNotReadyText}</p>
          </Notice>
          <JobFiles job={job} asset={asset} onJobChanged={onJobChanged} showIssues={false} />
        </>
      )}
      <PhysicalSewout job={job} onJobChanged={onJobChanged} />
    </>
  );
}
