import type { JobResponse } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { VariantForm } from '../variants/VariantForm';
import { JobFiles } from './JobFiles';

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
  return (
    <>
      <Notice tone={NoticeTone.Success} title={es.result.readyTitle}>
        <p>{es.result.readyText}</p>
      </Notice>
      <JobFiles job={job} asset={asset} onJobChanged={onJobChanged} />
      <VariantForm job={job} />
    </>
  );
}
