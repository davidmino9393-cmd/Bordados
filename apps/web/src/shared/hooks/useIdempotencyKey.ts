import { useRef } from 'react';
import { newIdempotencyKey } from '../utils/idempotency';

/**
 * Devuelve la misma clave mientras el contenido enviado no cambie (reintento seguro
 * de una conexión caída) y una nueva cuando cambia: reutilizarla con otros datos
 * provocaría IDEMPOTENCY_CONFLICT.
 */
export function useIdempotencyKey() {
  const last = useRef<{ fingerprint: string; key: string } | null>(null);
  return (payload: unknown): string => {
    const fingerprint = JSON.stringify(payload);
    if (last.current?.fingerprint !== fingerprint) {
      last.current = { fingerprint, key: newIdempotencyKey() };
    }
    return last.current.key;
  };
}
