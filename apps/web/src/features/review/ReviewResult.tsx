import type { JobResponse } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { JobFiles } from '../job-progress/JobFiles';
import { PhysicalSewout } from '../sewout/PhysicalSewout';
import { VariantForm } from '../variants/VariantForm';
import { canCorrect, isGeometryOnly, isRasterWithJef } from './geometryOnly';
import { JefHero } from './JefHero';
import { ReviewPanel } from './ReviewPanel';

interface ReviewResultProps {
  job: JobResponse;
  asset: SourceAsset | undefined;
  onJobChanged: (job: JobResponse) => void;
}

/**
 * needs_review: incidencias por corregir y, si el servidor ya generó archivos, esos archivos
 * con un aviso claro de que NO están listos para prueba. La muestra física se puede
 * registrar igual (decisión del integrador); no cambia el estado digital. Si solo hay geometría (sin JEF)
 * no hay nada que coser ni puntadas que corregir: solo se informa y se ofrece el SVG.
 */
export function ReviewResult({ job, asset, onJobChanged }: ReviewResultProps) {
  const geometryOnly = isGeometryOnly(job);
  return (
    <>
      {isRasterWithJef(job) && <JefHero job={job} />}
      {/* Primero lo que la persona vino a ver (el archivo y la comparación); los avisos van después. */}
      {job.artifact_manifest && (
        <>
          <Notice
            tone={NoticeTone.Warning}
            title={geometryOnly ? es.review.geometryOnlyTitle : es.review.filesNotReadyTitle}
          >
            <p>{geometryOnly ? es.review.geometryOnlyText : es.review.filesNotReadyText}</p>
          </Notice>
          <JobFiles job={job} asset={asset} onJobChanged={onJobChanged} showIssues={false} />
        </>
      )}
      <ReviewPanel job={job} asset={asset} correctable={canCorrect(job)} />
      {job.artifact_manifest && <VariantForm job={job} />}
      {!geometryOnly && <PhysicalSewout job={job} onJobChanged={onJobChanged} />}
    </>
  );
}
