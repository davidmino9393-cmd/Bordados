import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import type { Job } from '../../contracts/job';
import { es, stageLabel } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { newIdempotencyKey } from '../../shared/utils/idempotency';

/** Reintento: crea un trabajo nuevo con la misma imagen y ajustes; no reutiliza el fallido. */
function RetryButton({ job }: { job: Job }) {
  const api = useApi();
  const navigate = useNavigate();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const retry = async () => {
    setBusy(true);
    setError(undefined);
    try {
      const next = await api.createJob(job.project_id, job.source_asset_id, job.settings, newIdempotencyKey());
      navigate(`/trabajos/${next.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <>
      <div className="row">
        <button type="button" onClick={retry} disabled={busy}>{es.result.retrySame}</button>
      </div>
      {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
    </>
  );
}

export function FailedNotice({ job }: { job: Job }) {
  const stage = job.failure ? stageLabel[job.failure.stage] ?? job.failure.stage : undefined;
  return (
    <>
      <Notice tone={NoticeTone.Error} title={es.result.failedTitle}>
        <p>{job.failure?.message}</p>
        {stage && <p>{es.result.failedAt(stage)}</p>}
      </Notice>
      <RetryButton job={job} />
    </>
  );
}

export function CancelledNotice({ job }: { job: Job }) {
  return (
    <>
      <Notice tone={NoticeTone.Info} title={es.result.cancelledTitle}>
        <p>{es.result.cancelledText}</p>
      </Notice>
      <RetryButton job={job} />
    </>
  );
}
