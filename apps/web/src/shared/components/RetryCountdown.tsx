import { useEffect, useState } from 'react';
import { es } from '../../copy/es';

const TICK_MS = 1000;

/** «Reintentando en X s»: cuenta regresiva hasta el próximo intento (`retryAt`, en ms). */
export function RetryCountdown({ retryAt }: { retryAt: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, [retryAt]);
  const seconds = Math.max(0, Math.ceil((retryAt - now) / TICK_MS));
  return <span className="field__hint">{es.progress.retryingIn(seconds)}</span>;
}
