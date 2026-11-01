import type { JobResponse } from '../../contracts/job';
import { es } from '../../copy/es';
import { SewoutBadge } from '../../shared/components/Badges';
import { Card } from '../../shared/components/Card';
import { SewoutForm } from './SewoutForm';

interface PhysicalSewoutProps {
  job: JobResponse;
  onJobChanged: (job: JobResponse) => void;
}

/**
 * Estado de la muestra física (proyección del servidor) y formulario para registrar una.
 * Es independiente del estado digital: registrar una muestra nunca lo modifica.
 */
export function PhysicalSewout({ job, onJobChanged }: PhysicalSewoutProps) {
  const record = job.sewout_record;
  return (
    <>
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
    </>
  );
}
