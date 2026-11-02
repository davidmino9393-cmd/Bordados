import { useCallback, useEffect, useMemo, useState } from 'react';
import { errorMessage } from './useAsync';

export interface Page<T> {
  items: T[];
  next: string | null;
}

/**
 * Lista paginada por cursor: la primera página viene de la pantalla (y se renueva con ella) y las siguientes se piden
 * con «Ver más». Las páginas extra sobreviven a un `reload` de la primera; los repetidos se descartan por id.
 * `resetKey` (p. ej. el id del proyecto) descarta lo cargado de más al cambiar de lista.
 */
export function useLoadMore<T>(
  first: Page<T>,
  idOf: (item: T) => string,
  fetchPage: (cursor: string) => Promise<Page<T>>,
  resetKey: string,
) {
  const [extra, setExtra] = useState<T[]>([]);
  const [cursor, setCursor] = useState<string | null | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    setExtra([]);
    setCursor(undefined);
    setError(undefined);
  }, [resetKey]);

  const items = useMemo(() => {
    const seen = new Set<string>();
    return [...first.items, ...extra].filter((item) => {
      const id = idOf(item);
      if (seen.has(id)) return false;
      seen.add(id);
      return true;
    });
    // idOf es estable por uso; no entra en las dependencias.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [first.items, extra]);

  const next = cursor === undefined ? first.next : cursor;
  const loadMore = useCallback(async () => {
    if (next === null || loading) return;
    setLoading(true);
    setError(undefined);
    try {
      const page = await fetchPage(next);
      setExtra((previous) => [...previous, ...page.items]);
      setCursor(page.next);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [next, loading, fetchPage]);

  return { items, hasMore: next !== null, loading, error, loadMore };
}
