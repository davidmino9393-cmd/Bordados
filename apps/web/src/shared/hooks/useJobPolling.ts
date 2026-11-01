import { useCallback, useEffect, useState } from 'react';
import { useApi } from '../../api/ApiProvider';
import { TERMINAL_STATUSES, type Job } from '../../contracts/job';
import { errorMessage } from './useAsync';

export const JOB_POLL_INTERVAL_MS = 1000;

/** Consulta periódica del trabajo hasta un estado terminal (sin actualizaciones en vivo). */
export function useJobPolling(jobId: string) {
  const api = useApi();
  const [job, setJob] = useState<Job | null>(null);
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
        if (active) setError(errorMessage(e));
      }
    };
    void tick();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [api, jobId]);

  const replace = useCallback((next: Job) => setJob(next), []);
  return { job, error, replace };
}
