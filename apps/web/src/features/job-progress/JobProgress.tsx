import { useState } from 'react';
import { useApi } from '../../api/ApiProvider';
import { CANCELLABLE_STATUSES, StageState, type Job } from '../../contracts/job';
import { es, stageLabel, stageStateLabel } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { JobStatusBadge } from '../../shared/components/Badges';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { formatSeconds } from '../../shared/utils/format';
import { summarizeProgress } from './progress';

const PERCENT = 100;

interface JobProgressProps {
  job: Job;
  onJobChanged: (job: Job) => void;
}

export function JobProgress({ job, onJobChanged }: JobProgressProps) {
  const api = useApi();
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string>();
  const { done, total } = summarizeProgress(job.stages);
  const cancellable = CANCELLABLE_STATUSES.includes(job.status);

  const cancel = async () => {
    setCancelling(true);
    setError(undefined);
    try {
      onJobChanged(await api.cancelJob(job.id));
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
            <li key={s.stage} className={`stage stage--${s.state}`}>
              <span>{stageLabel[s.stage]}</span>
              <span>
                {stageStateLabel[s.state]}
                {s.state === StageState.Done && s.duration_ms !== undefined && (
                  <span className="field__hint"> · {es.progress.stageDuration(formatSeconds(s.duration_ms))}</span>
                )}
              </span>
            </li>
          ))}
        </ol>
        {cancellable && job.estimated_remaining_s !== null && (
          <p className="field__hint">{es.progress.estimate(job.estimated_remaining_s)}</p>
        )}
        {cancellable && (
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
