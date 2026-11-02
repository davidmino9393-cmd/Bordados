import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../../api/ApiClient';
import { es } from '../../copy/es';

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/** Mensaje para el usuario; los errores de la API llevan además el código de incidencia. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} ${es.errors.incident(error.code, error.requestId)}`;
  return error instanceof Error && error.message ? error.message : es.errors.generic;
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    load()
      .then((result) => {
        if (!active) return;
        setData(result);
        setError(null);
      })
      .catch((e: unknown) => active && setError(errorMessage(e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, loading, reload };
}
