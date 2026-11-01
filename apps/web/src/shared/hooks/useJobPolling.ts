import { useCallback, useEffect, useState } from 'react';
import { isTransientError } from '../../api/ApiClient';
import { useApi } from '../../api/ApiProvider';
import { TERMINAL_STATUSES, type JobResponse } from '../../contracts/job';
import { errorMessage } from './useAsync';

export const JOB_POLL_INTERVAL_MS = 1000;

/** Consulta periódica del trabajo hasta un estado terminal (sin actualizaciones en vivo). */
export function useJobPolling(jobId: string) {
  const api = useApi();
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setJob(null);
    const tick = async () => {
      try {
        const next = await api.getJob(jobId);
        if (!active) return;
        setJob(next);
        setError(null);
        if (!TERMINAL_STATUSES.includes(next.status)) timer = setTimeout(tick, JOB_POLL_INTERVAL_MS);
      } catch (e) {
        if (!active) return;
        // Un corte de red o un 5xx puntual no corta el seguimiento; un 403/404 sí.
        setError(errorMessage(e));
        if (isTransientError(e)) timer = setTimeout(tick, JOB_POLL_INTERVAL_MS);
      }
    };
    void tick();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [api, jobId]);

  const replace = useCallback((next: JobResponse) => setJob(next), []);
  return { job, error, replace };
}
