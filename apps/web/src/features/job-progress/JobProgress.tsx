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
import { useRunningElapsed } from './useRunningElapsed';

const PERCENT = 100;
const MS_PER_SECOND = 1000;
const SECONDS_PER_MINUTE = 60;

/** 0:07, 1:42: el tiempo que lleva la etapa en curso. */
function formatClock(ms: number): string {
  const seconds = Math.floor(ms / MS_PER_SECOND);
  return `${Math.floor(seconds / SECONDS_PER_MINUTE)}:${String(seconds % SECONDS_PER_MINUTE).padStart(2, '0')}`;
}

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
  const running = active ? job.stages.find((s) => s.outcome === StageOutcome.Running) : undefined;
  const elapsed = useRunningElapsed(running ? `${job.job_id}:${running.stage}` : undefined);

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
                {s === running && <span className="working-dot" aria-hidden="true" />}
                {stageOutcomeLabel[s.outcome]}
                {s === running && elapsed !== undefined && (
                  <span className="field__hint"> · {es.progress.elapsed(formatClock(elapsed))}</span>
                )}
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
