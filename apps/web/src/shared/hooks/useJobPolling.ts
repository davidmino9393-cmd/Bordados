import { useCallback, useEffect, useState } from 'react';
import { isTransientError } from '../../api/ApiClient';
import { useApi } from '../../api/ApiProvider';
import { TERMINAL_STATUSES, type JobResponse } from '../../contracts/job';
import { backoffDelay } from '../utils/backoff';
import { errorMessage } from './useAsync';

export const JOB_POLL_INTERVAL_MS = 1000;

/**
 * Consulta periódica del trabajo hasta un estado terminal (sin actualizaciones en vivo).
 * Ante un error transitorio reintenta con backoff exponencial y jitter; `retryAt` indica
 * cuándo es el próximo intento. Un error permanente (400, 403, 404…) no se reintenta.
 * El contador de intentos se reinicia al tener una respuesta correcta o al cambiar de trabajo.
 */
export function useJobPolling(jobId: string) {
  const api = useApi();
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryAt, setRetryAt] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setJob(null);
    setError(null);
    setRetryAt(null);
    const tick = async () => {
      try {
        const next = await api.getJob(jobId);
        if (!active) return;
        attempt = 0;
        setJob(next);
        setError(null);
        setRetryAt(null);
        if (!TERMINAL_STATUSES.includes(next.status)) timer = setTimeout(tick, JOB_POLL_INTERVAL_MS);
      } catch (e) {
        if (!active) return;
        setError(errorMessage(e));
        if (!isTransientError(e)) {
          setRetryAt(null);
          return;
        }
        const delay = backoffDelay(attempt);
        attempt += 1;
        setRetryAt(Date.now() + delay);
        timer = setTimeout(tick, delay);
      }
    };
    void tick();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [api, jobId]);

  const replace = useCallback((next: JobResponse) => setJob(next), []);
  return { job, error, retryAt, replace };
}
