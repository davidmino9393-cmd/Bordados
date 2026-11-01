import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import type { JobResponse } from '../../contracts/job';
import { CONTRACT_SCHEMA_VERSION } from '../../contracts/version';
import { es, issueTitle, stageLabel } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { newIdempotencyKey } from '../../shared/utils/idempotency';

/**
 * Reintento = intento nuevo y separado (states.md): mismo asset, misma revisión y
 * mismos ajustes, con clave de idempotencia propia. No reanima el trabajo fallido.
 */
function RetryButton({ job }: { job: JobResponse }) {
  const api = useApi();
  const navigate = useNavigate();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const retry = async () => {
    setBusy(true);
    setError(undefined);
    try {
      const next = await api.createJob(
        job.project_id,
        {
          schema_version: CONTRACT_SCHEMA_VERSION,
          asset_id: job.asset_id,
          revision_id: job.revision_id,
          input_kind: job.input_kind,
          settings: job.settings_snapshot,
        },
        newIdempotencyKey(),
      );
      navigate(`/trabajos/${next.job_id}`);
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

export function FailedNotice({ job }: { job: JobResponse }) {
  const failure = job.failure;
  const stage = failure ? stageLabel[failure.stage] ?? failure.stage : undefined;
  const suggestion = job.diagnostics?.[0]?.suggested_correction;
  return (
    <>
      <Notice tone={NoticeTone.Error} title={es.result.failedTitle}>
        {failure && <p>{issueTitle(failure.code, failure.message)}</p>}
        {stage && <p>{es.result.failedAt(stage)}</p>}
        {suggestion && <p className="field__hint">{suggestion}</p>}
      </Notice>
      <RetryButton job={job} />
    </>
  );
}

export function CancelledNotice({ job }: { job: JobResponse }) {
  return (
    <>
      <Notice tone={NoticeTone.Info} title={es.result.cancelledTitle}>
        <p>{es.result.cancelledText}</p>
      </Notice>
      <RetryButton job={job} />
    </>
  );
}
