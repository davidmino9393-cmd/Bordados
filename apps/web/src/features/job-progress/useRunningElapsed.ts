import { useEffect, useState } from 'react';

const TICK_MS = 1000;

/**
 * Milisegundos desde que la etapa en curso empezó, medidos en el navegador (el contrato no trae hora de inicio por
 * etapa). Vuelve a cero cuando cambia la etapa; undefined si no hay ninguna en curso.
 */
export function useRunningElapsed(key: string | undefined): number | undefined {
  const [start, setStart] = useState<number>();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const at = Date.now();
    setStart(key ? at : undefined);
    setNow(at);
    if (!key) return;
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, [key]);
  return start === undefined ? undefined : Math.max(0, now - start);
}
