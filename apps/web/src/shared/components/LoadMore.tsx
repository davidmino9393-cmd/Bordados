import { es } from '../../copy/es';
import { Notice, NoticeTone } from './Notice';

interface LoadMoreProps {
  hasMore: boolean;
  loading: boolean;
  error: string | undefined;
  onLoadMore: () => void;
  /** Texto del botón, p. ej. «Ver más trabajos». */
  label: string;
}

/** Cierre de una lista paginada: el botón solo existe mientras haya otra página. */
export function LoadMore({ hasMore, loading, error, onLoadMore, label }: LoadMoreProps) {
  return (
    <>
      {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
      {hasMore && (
        <div className="row">
          <button type="button" className="secondary" onClick={onLoadMore} disabled={loading}>
            {loading ? es.loadingMore : label}
          </button>
        </div>
      )}
    </>
  );
}
