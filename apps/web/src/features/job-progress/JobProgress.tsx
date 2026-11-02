import { useState } from 'react';
import { useApi } from '../../api/ApiProvider';
import { ACTIVE_STATUSES, StageOutcome, type JobResponse } from '../../contracts/job';
import { es, jobStatusLabel, stageLabel, stageOutcomeLabel } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { JobStatusBadge } from '../../shared/components/Badges';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { formatSeconds } from '../../shared/utils/format';
import { newIdempotencyKey } from '../../shared/utils/idempotency';
import { summarizeProgress } from './progress';

const PERCENT = 100;

interface JobProgressProps {
  job: JobResponse;
  onJobChanged: (job: JobResponse) => void;
}

export function JobProgress({ job, onJobChanged }: JobProgressProps) {
  const api = useApi();
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string>();
  const { done, total } = summarizeProgress(job.stages);
  const active = ACTIVE_STATUSES.includes(job.status);

  const cancel = async () => {
    setCancelling(true);
    setError(undefined);
    try {
      // 202: solo registra la solicitud. El estado `cancelled` llega por la consulta periódica.
      onJobChanged(await api.cancelJob(job.job_id, newIdempotencyKey()));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setCancelling(false);
    }
  };

  return (
    <Card>
      <Card.Header>{es.progress.title}</Card.Header>
      <Card.Body>
        {/* Anuncia a lectores de pantalla cada cambio de estado del trabajo. */}
        <p className="visually-hidden" role="status">
          {jobStatusLabel[job.status]}
        </p>
        <div className="row">
          <JobStatusBadge status={job.status} />
          <span>{es.progress.summary(done, total)}</span>
        </div>
        <div
          className="progress-bar"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={done}
          aria-label={es.progress.title}
        >
          <span style={{ width: `${total ? (done / total) * PERCENT : 0}%` }} />
        </div>
        <ol className="stages">
          {job.stages.map((s) => (
            <li key={s.stage} className={`stage stage--${s.outcome}`}>
              <span>{stageLabel[s.stage]}</span>
              <span>
                {stageOutcomeLabel[s.outcome]}
                {s.outcome === StageOutcome.Completed && s.measured_duration_ms !== null && (
                  <span className="field__hint"> · {es.progress.stageDuration(formatSeconds(s.measured_duration_ms))}</span>
                )}
              </span>
            </li>
          ))}
        </ol>
        {active && job.estimated_remaining_s !== null && !job.cancellation_requested && (
          <p className="field__hint">{es.progress.estimate(job.estimated_remaining_s)}</p>
        )}
        {active && job.cancellation_requested && <Notice tone={NoticeTone.Info}>{es.progress.cancelRequested}</Notice>}
        {active && !job.cancellation_requested && (
          <div className="row">
            <button type="button" className="danger" onClick={cancel} disabled={cancelling}>
              {cancelling ? es.progress.cancelling : es.progress.cancel}
            </button>
          </div>
        )}
        {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
      </Card.Body>
    </Card>
  );
}
